"""Validated construction and scope identity for WindowsAclAdapter."""

from __future__ import annotations

import threading
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.real_host_preflight.windows_paths import is_absolute_local_path

from .acl_contracts import AclCompatibilityPolicyV1
from .acl_paths import AclRolePaths
from .acl_state import AclAdapterState, register_adapter
from .canonical import fingerprint
from .errors import CutoverHostMutationError
from .roles import AclRole
from .windows_acl_adapter import WindowsAclAdapter
from .windows_handles import FILE_READ_ATTRIBUTES, WindowsHandleApi
from .windows_security import (
    WindowsSecurityApi,
    current_operator_sid_fingerprint,
)


_MARKER_NAME = ".codex-cutover-mutation-test-sandbox"


def create_test_windows_acl_adapter(
    *,
    root: Path,
    marker: Path,
    authorization: object,
    profile: CutoverProfileV1,
    compatibility_policy: AclCompatibilityPolicyV1,
    role_paths: AclRolePaths,
    observed_at_epoch: int,
    _child_race_barrier: object | None = None,
) -> WindowsAclAdapter:
    try:
        _validate_inputs(
            root, marker, authorization, profile,
            compatibility_policy, role_paths, observed_at_epoch,
            _child_race_barrier,
        )
        state = _build_state(
            root, marker, authorization, profile,
            compatibility_policy, role_paths, _child_race_barrier,
        )
        adapter = object.__new__(WindowsAclAdapter)
        register_adapter(adapter, state)
        return adapter
    except CutoverHostMutationError:
        raise
    except Exception:
        raise CutoverHostMutationError("acl_descriptor_invalid") from None


def current_operator_fingerprint() -> str:
    return current_operator_sid_fingerprint()


def marker_identity(marker: Path) -> str:
    api = WindowsHandleApi()
    handle = api.open_existing(marker, access=FILE_READ_ATTRIBUTES)
    try:
        native = api.observe(handle)
        api.require_stable(handle, native, marker)
        return native.object_identity_fingerprint
    finally:
        api.close(handle)


def _build_state(
    root, marker, authorization, profile, policy, paths, barrier
):
    security = WindowsSecurityApi()
    operator_sid = security.current_token_sid()
    if current_operator_sid_fingerprint() != profile.operator_fingerprint:
        raise CutoverHostMutationError("acl_authorization_rejected")
    root_capture = security.capture(root, role=AclRole.PARENT)
    return AclAdapterState(
        paths=paths,
        profile_fingerprint=profile.profile_fingerprint,
        authorization_fingerprint=_authorization_fingerprint(authorization),
        policy=policy,
        operator_sid=operator_sid,
        root=root,
        marker=marker,
        root_identity=root_capture.observation.object_identity_fingerprint,
        marker_identity=marker_identity(marker),
        child_race_barrier=barrier,
    )


def _validate_inputs(
    root, marker, authorization, profile, policy, paths, observed_at,
    barrier,
) -> None:
    if not _valid_fixed_inputs(
        root, marker, authorization, profile, policy, paths, observed_at
    ):
        raise CutoverHostMutationError("acl_authorization_rejected")
    _require_exact_authorization(authorization)
    if barrier is not None and type(barrier) is not threading.Barrier:
        raise CutoverHostMutationError("acl_authorization_rejected")
    if any(not _path_in_scope(root, path) for path in _all_paths(paths)):
        raise CutoverHostMutationError("acl_authorization_rejected")


def _valid_fixed_inputs(
    root, marker, authorization, profile, policy, paths, observed_at,
) -> bool:
    return (
        type(root) is type(Path())
        and type(marker) is type(Path())
        and is_absolute_local_path(root)
        and is_absolute_local_path(marker)
        and marker.parent == root
        and marker.name == _MARKER_NAME
        and type(profile) is CutoverProfileV1
        and type(policy) is AclCompatibilityPolicyV1
        and type(paths) is AclRolePaths
        and type(authorization) is TestSandboxAuthorizationV1
        and type(observed_at) is int
        and authorization.phase == "execute"
        and authorization.profile_fingerprint == profile.profile_fingerprint
        and observed_at < authorization.expires_at_epoch
        and profile.to_mapping()["acl_policy"]["policy_fingerprint"]
        == policy.policy_fingerprint
        and paths.parent == root
        and _fixed_container_paths(paths, root)
    )


def _require_exact_authorization(authorization) -> None:
    rebuilt = TestSandboxAuthorizationV1.create(
        profile_fingerprint=authorization.profile_fingerprint,
        operation_fingerprint=authorization.operation_fingerprint,
        phase=authorization.phase,
        expires_at_epoch=authorization.expires_at_epoch,
    )
    if rebuilt != authorization:
        raise CutoverHostMutationError("acl_authorization_rejected")


def _all_paths(paths):
    return (
        paths.source_tree,
        paths.parent,
        paths.finance,
        paths.project_container,
        paths.runtimes,
        paths.local_data,
        paths.runtime_temp,
        paths.logs,
        paths.artifacts,
        paths.worktrees,
        paths.config,
        paths.operator_private,
    )


def _fixed_container_paths(paths, root) -> bool:
    container = paths.project_container
    expected = (
        ("Runtimes", paths.runtimes),
        ("LocalData", paths.local_data),
        ("RuntimeTemp", paths.runtime_temp),
        ("Logs", paths.logs),
        ("Artifacts", paths.artifacts),
        ("Worktrees", paths.worktrees),
        ("Config", paths.config),
        ("OperatorPrivate", paths.operator_private),
    )
    return (
        container.parent == root
        and container.name == "Container"
        and all(path == container / name for name, path in expected)
    )


def _path_in_scope(root, path) -> bool:
    return (
        type(path) is type(Path())
        and is_absolute_local_path(path)
        and (path == root or root in path.parents)
    )


def _authorization_fingerprint(authorization) -> str:
    return fingerprint(
        "issue55-test-sandbox-authorization-v1",
        {
            "expires_at_epoch": authorization.expires_at_epoch,
            "operation_fingerprint": authorization.operation_fingerprint,
            "phase": authorization.phase,
            "profile_fingerprint": authorization.profile_fingerprint,
        },
        code="acl_contract_invalid",
    )
