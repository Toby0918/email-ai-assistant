"""Fixed operations of the test-sandbox-owned Windows ACL adapter."""
from __future__ import annotations
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
from .receipts import (
    AclApplyReceiptV1,
    AclBaselineReceiptV1,
    AclCompatibilityReceiptV1,
    AclPostVerifyReceiptV1,
)
from .roles import AclFailureCode, AclReceiptStatus, AclRole
from .source_acl_compatibility import observe_source_tree
from .windows_acl_apply import (
    WindowsAclWriter,
    exact_container_policy,
    exact_inherited_policy,
)
from .windows_security import WindowsSecurityApi
_DESCRIPTOR_ROLES = frozenset({AclRole.PARENT, AclRole.FINANCE})


class WindowsAclAdapter:
    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("WindowsAclAdapter requires validated construction")

    def capture(self, role: AclRole):
        if type(role) is not AclRole:
            raise CutoverHostMutationError("acl_descriptor_invalid")
        state = _state(self)
        if role is AclRole.SOURCE_TREE:
            return _capture_source_tree(state)
        if role not in _DESCRIPTOR_ROLES:
            raise CutoverHostMutationError("acl_descriptor_invalid")
        captured = _capture_descriptor(state, role)
        receipt = _baseline_receipt(state, captured)
        register_baseline(
            receipt,
            BaselineState(self, role, captured.observation),
        )
        return receipt

    def compare(self, baseline: AclBaselineReceiptV1):
        state = _state(self)
        try:
            saved = baseline_state(baseline)
        except LookupError:
            return _rejected_compare(state, AclFailureCode.SCOPE_INVALID)
        if saved.adapter is not self or saved.role not in _DESCRIPTOR_ROLES:
            return _rejected_compare(state, AclFailureCode.SCOPE_INVALID)
        current = _capture_descriptor(state, saved.role).observation
        if current != saved.observation:
            return _rejected_compare(state, AclFailureCode.IDENTITY_CHANGED)
        return _post_receipt(state, current.observation_fingerprint, 1)

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
        return _apply_receipt(
            state, proof.after.observation.observation_fingerprint
        )

    def verify_fixed_zone_inheritance(self):
        state = _state(self)
        try:
            applied = applied_state(self)
        except LookupError:
            raise CutoverHostMutationError(
                "acl_inheritance_rejected"
            ) from None
        _require_scope_intact(state)
        container = WindowsSecurityApi().capture(
            state.paths.project_container,
            role=AclRole.PROJECT_CONTAINER,
        )
        _validate_container(container, applied)
        observations = _verify_zones(state, container, applied)
        aggregate = fingerprint(
            "acl-fixed-zone-post-verify-v1",
            {
                "container": container.observation.observation_fingerprint,
                "zones": observations,
            },
            code="acl_contract_invalid",
        )
        return _post_receipt(state, aggregate, len(observations))


def _claim_for_apply(state, created_container):
    try:
        claim = new_directory_claim(created_container)
    except LookupError:
        raise CutoverHostMutationError("acl_policy_rejected") from None
    if (
        claim.target != state.paths.project_container
        or claim.profile_fingerprint != state.profile_fingerprint
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
        return WindowsAclWriter().apply_new_container(
            state.paths.project_container,
            expected_identity=claim.object_identity,
            operator_sid=state.operator_sid,
        )


def _validate_container(container, applied) -> None:
    if (
        container.observation.object_identity_fingerprint
        != applied.container_identity
        or not exact_container_policy(container, applied.principal_sids)
    ):
        raise CutoverHostMutationError("acl_inheritance_rejected")


def _verify_zones(state, container, applied) -> list[str]:
    security = WindowsSecurityApi()
    observations = []
    for role, path in _fixed_zones(state.paths):
        captured = security.capture(path, role=role)
        if (
            captured.native_identity.volume_fingerprint
            != container.native_identity.volume_fingerprint
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
    return _compatibility_receipt(state, observation, compatible)


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


def _baseline_receipt(state, captured):
    return AclBaselineReceiptV1.create(
        status=AclReceiptStatus.ACCEPTED,
        failure_code=AclFailureCode.NONE,
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=captured.observation.observation_fingerprint,
        accepted=1,
        rejected=0,
        observed_objects=1,
    )


def _compatibility_receipt(state, observation, compatible):
    return AclCompatibilityReceiptV1.create(
        status=AclReceiptStatus.ACCEPTED if compatible else AclReceiptStatus.REJECTED,
        failure_code=AclFailureCode.NONE if compatible else AclFailureCode.COMPATIBILITY_REJECTED,
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=observation.observation_fingerprint,
        accepted=1 if compatible else 0,
        rejected=0 if compatible else 1,
        observed_objects=observation.descriptors_observed,
    )


def _apply_receipt(state, observation):
    return AclApplyReceiptV1.create(
        status=AclReceiptStatus.ACCEPTED,
        failure_code=AclFailureCode.NONE,
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=observation,
        accepted=1,
        rejected=0,
        observed_objects=1,
    )


def _post_receipt(state, observation, count):
    return AclPostVerifyReceiptV1.create(
        status=AclReceiptStatus.ACCEPTED,
        failure_code=AclFailureCode.NONE,
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=observation,
        accepted=1,
        rejected=0,
        observed_objects=count,
    )


def _rejected_compare(state, failure):
    return AclPostVerifyReceiptV1.create(
        status=AclReceiptStatus.REJECTED,
        failure_code=failure,
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=state.root_identity,
        accepted=0,
        rejected=1,
        observed_objects=0,
    )


def _state(adapter):
    try:
        return adapter_state(adapter)
    except LookupError:
        raise CutoverHostMutationError("acl_authorization_rejected") from None
