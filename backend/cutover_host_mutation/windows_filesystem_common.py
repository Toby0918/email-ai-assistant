"""Shared validation for test-sandbox-owned Windows filesystem effects."""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.real_host_preflight.windows_paths import is_absolute_local_path

from .canonical import fingerprint
from .errors import CutoverHostMutationError
from .windows_handles import (
    ERROR_ALREADY_EXISTS,
    ERROR_FILE_EXISTS,
    ERROR_FILE_NOT_FOUND,
    ERROR_PATH_NOT_FOUND,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    WindowsHandleApi,
    _NativeWindowsFailure,
)


MARKER_NAME = ".codex-cutover-mutation-test-sandbox"
ZERO_FINGERPRINT = "0" * 64


def validate_scope(
    *,
    root: object,
    marker: object,
    authorization: object,
    profile: object,
    parent: object,
    target: object,
    observed_at_epoch: object,
) -> None:
    paths = (root, marker, parent, target)
    valid_paths = all(
        type(path) is type(Path()) and is_absolute_local_path(path)
        for path in paths
    )
    if (
        not valid_paths
        or marker.parent != root
        or marker.name != MARKER_NAME
        or parent != target.parent
        or (parent != root and root not in parent.parents)
        or type(profile) is not CutoverProfileV1
        or type(authorization) is not TestSandboxAuthorizationV1
        or authorization.profile_fingerprint != profile.profile_fingerprint
        or authorization.phase != "execute"
        or type(observed_at_epoch) is not int
        or observed_at_epoch >= authorization.expires_at_epoch
    ):
        fail("filesystem_authorization_rejected")
    _require_exact_authorization(authorization)


def authorization_fingerprint(
    authorization: TestSandboxAuthorizationV1,
) -> str:
    return fingerprint(
        "issue55-test-sandbox-authorization-v1",
        {
            "expires_at_epoch": authorization.expires_at_epoch,
            "operation_fingerprint": authorization.operation_fingerprint,
            "phase": authorization.phase,
            "profile_fingerprint": authorization.profile_fingerprint,
        },
        code="filesystem_contract_invalid",
    )


def observe_existing(api: WindowsHandleApi, path: Path):
    handle = api.open_existing(path, access=FILE_READ_ATTRIBUTES)
    try:
        observed = api.observe(handle)
        if observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            fail("filesystem_reparse_rejected")
        api.require_stable(handle, observed, path)
        return observed
    finally:
        api.close(handle)


def open_bound_scope(
    api: WindowsHandleApi,
    *,
    root: Path,
    marker: Path,
    root_identity: str,
    marker_identity: str,
):
    root_handle = api.open_existing(root, access=FILE_READ_ATTRIBUTES)
    try:
        marker_handle = api.open_existing(
            marker,
            access=FILE_READ_ATTRIBUTES,
        )
    except Exception:
        close_handles(api, root_handle)
        raise
    try:
        root_value = api.observe(root_handle)
        marker_value = api.observe(marker_handle)
        if (
            root_value.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
            or marker_value.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
            or root_value.object_identity_fingerprint != root_identity
            or marker_value.object_identity_fingerprint != marker_identity
            or root_value.volume_fingerprint
            != marker_value.volume_fingerprint
        ):
            fail("filesystem_identity_changed")
        api.require_stable(root_handle, root_value, root)
        api.require_stable(marker_handle, marker_value, marker)
        return root_handle, marker_handle
    except Exception:
        close_handles(api, marker_handle, root_handle)
        raise


def require_absent(api: WindowsHandleApi, target: Path) -> None:
    try:
        handle = api.open_existing(target, access=FILE_READ_ATTRIBUTES)
    except _NativeWindowsFailure as error:
        if error.code in {ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND}:
            return
        map_native_failure(error)
    try:
        api.close(handle)
    except _NativeWindowsFailure:
        fail("filesystem_identity_changed")
    fail("filesystem_no_clobber_rejected")


def binding_target_name(target: Path) -> str:
    return hashlib.sha256(
        target.name.casefold().encode("utf-8")
    ).hexdigest()


def close_handles(api: WindowsHandleApi, *handles: int) -> None:
    for handle in handles:
        try:
            api.close(handle)
        except _NativeWindowsFailure:
            fail("filesystem_identity_changed")


def map_native_failure(error: _NativeWindowsFailure) -> None:
    if error.code in {ERROR_FILE_EXISTS, ERROR_ALREADY_EXISTS}:
        fail("filesystem_no_clobber_rejected")
    fail("filesystem_scope_invalid")


def fail(code: str) -> None:
    raise CutoverHostMutationError(code) from None


def _require_exact_authorization(
    authorization: TestSandboxAuthorizationV1,
) -> None:
    rebuilt = TestSandboxAuthorizationV1.create(
        profile_fingerprint=authorization.profile_fingerprint,
        operation_fingerprint=authorization.operation_fingerprint,
        phase=authorization.phase,
        expires_at_epoch=authorization.expires_at_epoch,
    )
    if rebuilt != authorization:
        fail("filesystem_authorization_rejected")
