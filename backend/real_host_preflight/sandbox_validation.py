"""Pure exact validation for test-sandbox authorization and local paths."""

from __future__ import annotations

from .contracts_bridge import TestSandboxAuthorizationV1
from .errors import RealHostPreflightError
from .windows_paths import is_absolute_local_path


def validate_sandbox_authorization(
    authorization: object,
    observed_at_epoch: object,
) -> None:
    if type(authorization) is not TestSandboxAuthorizationV1:
        _fail("sandbox_authorization_invalid")
    if type(observed_at_epoch) is not int or not 0 <= observed_at_epoch < 2**63:
        _fail("sandbox_authorization_invalid")
    try:
        rebuilt = TestSandboxAuthorizationV1.create(
            profile_fingerprint=authorization.profile_fingerprint,
            operation_fingerprint=authorization.operation_fingerprint,
            phase=authorization.phase,
            expires_at_epoch=authorization.expires_at_epoch,
        )
    except Exception:
        _fail("sandbox_authorization_invalid")
    if rebuilt != authorization:
        _fail("sandbox_authorization_invalid")
    if observed_at_epoch >= authorization.expires_at_epoch:
        _fail("sandbox_authorization_expired")


def require_absolute_local_path(path: object) -> None:
    if not is_absolute_local_path(path):
        _fail("host_scope_invalid")


def _fail(code: str) -> None:
    raise RealHostPreflightError(code) from None
