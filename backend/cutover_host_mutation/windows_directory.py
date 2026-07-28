"""Journal-gated create-only Windows directory primitive."""

from __future__ import annotations

from pathlib import Path

from backend.cutover_contracts import CutoverProfileV1

from .canonical import fingerprint
from .errors import CutoverHostMutationError
from .filesystem_contracts import (
    FilesystemMutationExpectationV1,
    FilesystemMutationObservationV1,
)
from .filesystem_state import (
    DirectoryPrimitiveState,
    NewDirectoryClaim,
    directory_primitive_state,
    register_directory_primitive,
    register_new_directory,
)
from .journal_intent import consumed_filesystem_intent
from .roles import FilesystemMutationKind
from .windows_filesystem_common import (
    ZERO_FINGERPRINT,
    authorization_fingerprint,
    close_handles,
    fail,
    map_native_failure,
    observe_existing,
    require_absent,
    validate_scope,
)
from .windows_handles import (
    ERROR_ALREADY_EXISTS,
    ERROR_FILE_EXISTS,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    WindowsHandleApi,
    _NativeWindowsFailure,
)


class CreateOnlyDirectoryPrimitive:
    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("directory primitive requires validated construction")

    @property
    def expectation(self) -> FilesystemMutationExpectationV1:
        return _state(self).expectation

    def create_directory(
        self,
        *,
        intent: object,
        durable_permit: object,
    ) -> FilesystemMutationObservationV1:
        state = _state(self)
        api = WindowsHandleApi()
        _require_scope(api, state)
        handle, parent = _open_parent(api, state)
        try:
            target = _effect(
                api, state, handle, parent, intent, durable_permit
            )
            observation = _observation(state, target, intent)
            _register_claim(state, observation, target)
            return observation
        except CutoverHostMutationError:
            raise
        except _NativeWindowsFailure as error:
            map_native_failure(error)
        except Exception:
            fail("internal_error")
        finally:
            close_handles(api, handle)


def _create_test_directory_primitive(
    *,
    root: Path,
    marker: Path,
    authorization: object,
    profile: CutoverProfileV1,
    parent: Path,
    target: Path,
    observed_at_epoch: int,
) -> CreateOnlyDirectoryPrimitive:
    validate_scope(
        root=root,
        marker=marker,
        authorization=authorization,
        profile=profile,
        parent=parent,
        target=target,
        observed_at_epoch=observed_at_epoch,
    )
    try:
        state = _build_state(
            root, marker, authorization, profile, parent, target
        )
        primitive = object.__new__(CreateOnlyDirectoryPrimitive)
        register_directory_primitive(primitive, state)
        return primitive
    except CutoverHostMutationError:
        raise
    except Exception:
        fail("filesystem_scope_invalid")


def _build_state(
    root: Path,
    marker: Path,
    authorization: object,
    profile: CutoverProfileV1,
    parent: Path,
    target: Path,
) -> DirectoryPrimitiveState:
    api = WindowsHandleApi()
    root_value = observe_existing(api, root)
    marker_value = observe_existing(api, marker)
    parent_value = observe_existing(api, parent)
    if root_value.volume_fingerprint != parent_value.volume_fingerprint:
        fail("filesystem_volume_mismatch")
    auth = authorization_fingerprint(authorization)
    body = _binding_body(profile, target, parent_value, auth)
    expectation = _expectation(body)
    return DirectoryPrimitiveState(
        root, marker, parent, target, profile.profile_fingerprint, auth,
        root_value.object_identity_fingerprint,
        marker_value.object_identity_fingerprint,
        parent_value.object_identity_fingerprint,
        parent_value.volume_fingerprint,
        expectation,
    )


def _binding_body(profile, target, parent, auth) -> dict[str, object]:
    from backend.real_host_preflight.windows_paths import expected_final_path
    import hashlib

    return {
        "authorization_fingerprint": auth,
        "kind": FilesystemMutationKind.CREATE_DIRECTORY.value,
        "normalized_target_fingerprint": hashlib.sha256(
            expected_final_path(target).casefold().encode("utf-8")
        ).hexdigest(),
        "parent_identity_fingerprint": parent.object_identity_fingerprint,
        "profile_fingerprint": profile.profile_fingerprint,
        "volume_fingerprint": parent.volume_fingerprint,
    }


def _expectation(body: dict[str, object]):
    binding = fingerprint(
        "filesystem-mutation-binding-v1",
        body,
        code="filesystem_contract_invalid",
    )
    return FilesystemMutationExpectationV1.create(
        kind=FilesystemMutationKind.CREATE_DIRECTORY,
        binding_fingerprint=binding,
        before_fingerprint=fingerprint(
            "create-directory-absent-v1",
            body,
            code="filesystem_contract_invalid",
        ),
        expected_after_fingerprint=fingerprint(
            "create-directory-present-v1",
            body,
            code="filesystem_contract_invalid",
        ),
    )


def _require_scope(api, state: DirectoryPrimitiveState) -> None:
    root = observe_existing(api, state.root)
    marker = observe_existing(api, state.marker)
    if (
        root.object_identity_fingerprint != state.root_identity
        or marker.object_identity_fingerprint != state.marker_identity
    ):
        fail("filesystem_identity_changed")


def _open_parent(api, state: DirectoryPrimitiveState):
    handle = api.open_existing(state.parent, access=FILE_READ_ATTRIBUTES)
    try:
        parent = api.observe(handle)
        if parent.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            fail("filesystem_reparse_rejected")
        if (
            parent.object_identity_fingerprint != state.parent_identity
            or parent.volume_fingerprint != state.volume_fingerprint
        ):
            fail("filesystem_identity_changed")
        api.require_stable(handle, parent, state.parent)
        return handle, parent
    except Exception:
        close_handles(api, handle)
        raise


def _effect(api, state, handle, parent, intent, permit):
    require_absent(api, state.target)
    with consumed_filesystem_intent(
        intent=intent,
        durable_permit=permit,
        expectation=state.expectation,
    ):
        try:
            api.create_directory(state.target)
        except _NativeWindowsFailure as error:
            if error.code in {ERROR_FILE_EXISTS, ERROR_ALREADY_EXISTS}:
                fail("filesystem_no_clobber_rejected")
            raise
        api.require_stable(handle, parent, state.parent)
        target = observe_existing(api, state.target)
        if target.volume_fingerprint != state.volume_fingerprint:
            fail("filesystem_volume_mismatch")
        return target


def _observation(state, target, intent):
    return FilesystemMutationObservationV1.create(
        kind=FilesystemMutationKind.CREATE_DIRECTORY,
        journal_intent_fingerprint=intent.record_hash,
        journal_effect_fingerprint=(
            state.expectation.expected_after_fingerprint
        ),
        source_identity_fingerprint=ZERO_FINGERPRINT,
        target_identity_fingerprint=target.object_identity_fingerprint,
        parent_identity_fingerprint=state.parent_identity,
        volume_fingerprint=state.volume_fingerprint,
        same_identity=False,
        no_replace=True,
        reparse_free=True,
    )


def _register_claim(state, observation, target) -> None:
    register_new_directory(
        observation,
        NewDirectoryClaim(
            target=state.target,
            object_identity=target.object_identity_fingerprint,
            parent_identity=state.parent_identity,
            volume_fingerprint=state.volume_fingerprint,
            profile_fingerprint=state.profile_fingerprint,
        ),
    )


def _state(primitive) -> DirectoryPrimitiveState:
    try:
        return directory_primitive_state(primitive)
    except LookupError:
        fail("filesystem_authorization_rejected")
