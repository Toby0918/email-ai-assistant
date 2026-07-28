"""Fixed operations of the test-sandbox-owned Windows ACL adapter."""
from __future__ import annotations
from functools import wraps
from .acl_journal import consumed_acl_intent
from .acl_state import (
    AppliedAclState,
    BaselineState,
    adapter_state,
    applied_state,
    baseline_state,
    register_applied,
    register_baseline,
)
from .canonical import fingerprint
from .errors import CutoverHostMutationError
from .filesystem_state import claim_new_directory, new_directory_claim
from .acl_receipt_factory import (
    apply_receipt,
    baseline_receipt,
    compatibility_receipt,
    post_receipt,
    rejected_compare,
)
from .receipts import AclBaselineReceiptV1
from .roles import AclFailureCode, AclRole
from .source_acl_compatibility import observe_source_tree
from .windows_acl_apply import (
    WindowsAclWriter,
    exact_container_policy,
    exact_inherited_policy,
)
from .windows_handles import (
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    READ_CONTROL,
    WindowsHandleApi,
)
from .windows_security import WindowsSecurityApi
_DESCRIPTOR_ROLES = frozenset({AclRole.PARENT, AclRole.FINANCE})


def _fixed_acl_boundary(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except CutoverHostMutationError:
            raise
        except Exception:
            raise CutoverHostMutationError(
                "acl_descriptor_invalid"
            ) from None

    return guarded


class WindowsAclAdapter:
    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("WindowsAclAdapter requires validated construction")

    @_fixed_acl_boundary
    def capture(self, role: AclRole):
        if type(role) is not AclRole:
            raise CutoverHostMutationError("acl_descriptor_invalid")
        state = _state(self)
        if role is AclRole.SOURCE_TREE:
            return _capture_source_tree(state)
        if role not in _DESCRIPTOR_ROLES:
            raise CutoverHostMutationError("acl_descriptor_invalid")
        captured = _capture_descriptor(state, role)
        receipt = baseline_receipt(state, captured)
        register_baseline(
            receipt,
            BaselineState(self, role, captured.observation),
        )
        return receipt

    @_fixed_acl_boundary
    def compare(self, baseline: AclBaselineReceiptV1):
        state = _state(self)
        try:
            saved = baseline_state(baseline)
        except LookupError:
            return rejected_compare(state, AclFailureCode.SCOPE_INVALID)
        if saved.adapter is not self or saved.role not in _DESCRIPTOR_ROLES:
            return rejected_compare(state, AclFailureCode.SCOPE_INVALID)
        current = _capture_descriptor(state, saved.role).observation
        if current != saved.observation:
            return rejected_compare(state, AclFailureCode.IDENTITY_CHANGED)
        return post_receipt(state, current.observation_fingerprint, 1)

    @_fixed_acl_boundary
    def apply_new_container_policy(
        self,
        *,
        created_container: object,
        intent: object,
        durable_permit: object,
    ):
        state = _state(self)
        claim = _claim_for_apply(state, created_container)
        _require_scope_intact(state)
        proof = _apply_claim(
            state, created_container, claim, intent, durable_permit
        )
        register_applied(
            self,
            AppliedAclState(
                claim.object_identity,
                proof.principal_sids,
                proof.after.observation.observation_fingerprint,
            ),
        )
        return apply_receipt(
            state, proof.after.observation.observation_fingerprint
        )

    @_fixed_acl_boundary
    def verify_fixed_zone_inheritance(self):
        state = _state(self)
        try:
            applied = applied_state(self)
        except LookupError:
            raise CutoverHostMutationError(
                "acl_inheritance_rejected"
            ) from None
        _require_scope_intact(state)
        container, observations = _observe_fixed_zones(state, applied)
        aggregate = fingerprint(
            "acl-fixed-zone-post-verify-v1",
            {
                "container": container.observation.observation_fingerprint,
                "zones": observations,
            },
            code="acl_contract_invalid",
        )
        return post_receipt(state, aggregate, len(observations))


def _observe_fixed_zones(state, applied):
    api = WindowsHandleApi()
    handle = api.open_existing(
        state.paths.project_container,
        access=FILE_READ_ATTRIBUTES | READ_CONTROL,
    )
    try:
        security = WindowsSecurityApi()
        container = security.capture_handle(
            handle,
            path=state.paths.project_container,
            role=AclRole.PROJECT_CONTAINER,
        )
        _validate_container(container, applied)
        observations = _verify_zones(state, container, applied)
        after = security.capture_handle(
            handle,
            path=state.paths.project_container,
            role=AclRole.PROJECT_CONTAINER,
        )
        _validate_container(after, applied)
        if after.observation != container.observation:
            raise CutoverHostMutationError("acl_inheritance_rejected")
        return container, observations
    finally:
        api.close(handle)


def _claim_for_apply(state, created_container):
    try:
        claim = new_directory_claim(created_container)
    except LookupError:
        raise CutoverHostMutationError("acl_policy_rejected") from None
    if (
        claim.target != state.paths.project_container
        or claim.profile_fingerprint != state.profile_fingerprint
        or claim.parent_identity != state.root_identity
        or claim.guarded_container is not True
        or claim.resource is None
    ):
        raise CutoverHostMutationError("acl_policy_rejected")
    return claim


def _apply_claim(state, created, claim, intent, permit):
    with consumed_acl_intent(
        intent=intent,
        durable_permit=permit,
        before_fingerprint=created.observation_fingerprint,
        expected_after_fingerprint=state.policy.policy_fingerprint,
    ):
        try:
            consumed = claim_new_directory(created)
        except LookupError:
            raise CutoverHostMutationError("acl_policy_rejected") from None
        if consumed != claim:
            raise CutoverHostMutationError("acl_policy_rejected")
        try:
            return WindowsAclWriter().apply_new_container(
                state.paths.project_container,
                expected_identity=claim.object_identity,
                expected_parent_identity=claim.parent_identity,
                parent_path=state.paths.parent,
                operator_sid=state.operator_sid,
                resource=claim.resource,
                child_race_barrier=state.child_race_barrier,
            )
        finally:
            claim.resource.close()


def _validate_container(container, applied) -> None:
    if (
        container.observation.object_identity_fingerprint
        != applied.container_identity
        or container.native_identity.file_attributes
        & FILE_ATTRIBUTE_REPARSE_POINT
        or not exact_container_policy(container, applied.principal_sids)
    ):
        raise CutoverHostMutationError("acl_inheritance_rejected")


def _verify_zones(state, container, applied) -> list[str]:
    security = WindowsSecurityApi()
    observations = []
    for role, path in _fixed_zones(state.paths):
        captured = security.capture(
            path,
            role=role,
            _allow_reparse=True,
        )
        if (
            captured.native_identity.volume_fingerprint
            != container.native_identity.volume_fingerprint
            or captured.native_identity.file_attributes
            & FILE_ATTRIBUTE_REPARSE_POINT
            or not exact_inherited_policy(captured, applied.principal_sids)
        ):
            raise CutoverHostMutationError("acl_inheritance_rejected")
        observations.append(captured.observation.observation_fingerprint)
    return observations


def _capture_descriptor(state, role):
    _require_scope_intact(state)
    path = state.paths.parent if role is AclRole.PARENT else state.paths.finance
    try:
        return WindowsSecurityApi().capture(path, role=role)
    except CutoverHostMutationError:
        raise
    except Exception:
        raise CutoverHostMutationError("acl_descriptor_invalid") from None


def _capture_source_tree(state):
    _require_scope_intact(state)
    try:
        observation, compatible = observe_source_tree(
            state.paths.source_tree,
            policy=state.policy,
        )
    except CutoverHostMutationError:
        raise
    except Exception:
        raise CutoverHostMutationError("acl_descriptor_invalid") from None
    return compatibility_receipt(state, observation, compatible)


def _require_scope_intact(state) -> None:
    security = WindowsSecurityApi()
    root = security.capture(state.root, role=AclRole.PARENT)
    from .windows_acl_factory import marker_identity

    if (
        root.observation.object_identity_fingerprint != state.root_identity
        or marker_identity(state.marker) != state.marker_identity
    ):
        raise CutoverHostMutationError("acl_identity_changed")


def _fixed_zones(paths):
    return (
        (AclRole.RUNTIMES, paths.runtimes),
        (AclRole.LOCAL_DATA, paths.local_data),
        (AclRole.RUNTIME_TEMP, paths.runtime_temp),
        (AclRole.LOGS, paths.logs),
        (AclRole.ARTIFACTS, paths.artifacts),
        (AclRole.WORKTREES, paths.worktrees),
        (AclRole.CONFIG, paths.config),
        (AclRole.OPERATOR_PRIVATE, paths.operator_private),
    )


def _state(adapter):
    try:
        return adapter_state(adapter)
    except LookupError:
        raise CutoverHostMutationError("acl_authorization_rejected") from None
