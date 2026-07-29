"""Validated construction for handle-relative directory primitives."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from backend.cutover_contracts import CutoverProfileV1
from backend.real_host_preflight.windows_paths import expected_final_path

from .canonical import fingerprint
from .errors import CutoverHostMutationError
from .filesystem_contracts import FilesystemMutationExpectationV1
from .filesystem_state import (
    DirectoryPrimitiveState,
    register_directory_primitive,
)
from .roles import FilesystemMutationKind
from .windows_directory import CreateOnlyDirectoryPrimitive
from .windows_filesystem_common import (
    authorization_fingerprint,
    fail,
    observe_existing,
    validate_scope,
)
from .windows_handles import WindowsHandleApi


def _create_test_directory_primitive(
    *,
    root: Path,
    marker: Path,
    authorization: object,
    profile: CutoverProfileV1,
    parent: Path,
    target: Path,
    observed_at_epoch: int,
    _target_race_barrier: object | None = None,
) -> CreateOnlyDirectoryPrimitive:
    return _create_test_primitive(
        root=root,
        marker=marker,
        authorization=authorization,
        profile=profile,
        parent=parent,
        target=target,
        observed_at_epoch=observed_at_epoch,
        guarded_container=False,
        target_race_barrier=_target_race_barrier,
    )


def _create_test_guarded_container_primitive(
    *,
    root: Path,
    marker: Path,
    authorization: object,
    profile: CutoverProfileV1,
    parent: Path,
    target: Path,
    observed_at_epoch: int,
) -> CreateOnlyDirectoryPrimitive:
    return _create_test_primitive(
        root=root,
        marker=marker,
        authorization=authorization,
        profile=profile,
        parent=parent,
        target=target,
        observed_at_epoch=observed_at_epoch,
        guarded_container=True,
        target_race_barrier=None,
    )


def _create_test_primitive(
    *,
    root,
    marker,
    authorization,
    profile,
    parent,
    target,
    observed_at_epoch,
    guarded_container,
    target_race_barrier,
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
    if type(guarded_container) is not bool:
        fail("filesystem_authorization_rejected")
    if (
        target_race_barrier is not None
        and type(target_race_barrier) is not threading.Barrier
    ):
        fail("filesystem_authorization_rejected")
    try:
        state = _build_state(
            root, marker, authorization, profile, parent, target,
            guarded_container, target_race_barrier,
        )
        primitive = object.__new__(CreateOnlyDirectoryPrimitive)
        register_directory_primitive(primitive, state)
        return primitive
    except CutoverHostMutationError:
        raise
    except Exception:
        fail("filesystem_scope_invalid")


def _build_state(
    root,
    marker,
    authorization,
    profile,
    parent,
    target,
    guarded_container,
    target_race_barrier,
) -> DirectoryPrimitiveState:
    api = WindowsHandleApi()
    root_value = observe_existing(api, root)
    marker_value = observe_existing(api, marker)
    parent_value = observe_existing(api, parent)
    if root_value.volume_fingerprint != parent_value.volume_fingerprint:
        fail("filesystem_volume_mismatch")
    auth = authorization_fingerprint(authorization)
    body = _binding_body(
        profile, target, parent_value, auth, guarded_container
    )
    return DirectoryPrimitiveState(
        root, marker, parent, target, profile.profile_fingerprint,
        profile.operator_fingerprint, auth,
        root_value.object_identity_fingerprint,
        marker_value.object_identity_fingerprint,
        parent_value.object_identity_fingerprint,
        parent_value.volume_fingerprint,
        _expectation(body),
        guarded_container,
        target_race_barrier,
    )


def _binding_body(
    profile, target, parent, auth, guarded_container
) -> dict[str, object]:
    return {
        "authorization_fingerprint": auth,
        "guarded_container": guarded_container,
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
