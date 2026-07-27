"""Pure binding checks for real and test-sandbox preflight authorization."""

from __future__ import annotations

from .canonical import fingerprint, is_fingerprint
from .contracts_bridge import (
    AuthorizationValidationStatus,
    CutoverProfileV1,
    RealPreflightAuthorizationV1,
    TestSandboxAuthorizationV1,
    validate_real_host_authorization,
)


def require_preflight_authorization(
    authorization: object,
    *,
    profile: CutoverProfileV1,
    operation_fingerprint: str,
    phase: str,
    observed_at_epoch: int,
) -> tuple[str, int]:
    """Return only an opaque binding and bounded expiry."""

    _require_context(profile, operation_fingerprint, observed_at_epoch)
    if type(authorization) is TestSandboxAuthorizationV1:
        return _require_sandbox_authorization(
            authorization,
            profile,
            operation_fingerprint,
            phase,
            observed_at_epoch,
        )
    if type(authorization) is RealPreflightAuthorizationV1:
        validation = validate_real_host_authorization(
            authorization,
            profile=profile,
            expected_operation="real_preflight",
            expected_operation_fingerprint=operation_fingerprint,
            expected_phase=phase,
            expected_operator_fingerprint=profile.operator_fingerprint,
            observed_at_epoch=observed_at_epoch,
        )
        if validation.status is not AuthorizationValidationStatus.AUTHORIZED:
            raise ValueError("REAL_HOST_AUTHORIZATION_REJECTED")
        return (
            authorization.authorization_fingerprint,
            authorization.expires_at_epoch,
        )
    raise ValueError("REAL_HOST_AUTHORIZATION_REJECTED")


def _require_context(
    profile: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> None:
    try:
        intact = (
            type(profile) is CutoverProfileV1
            and CutoverProfileV1.from_mapping(profile.to_mapping()) == profile
        )
    except Exception:
        intact = False
    if (
        not intact
        or not is_fingerprint(operation_fingerprint)
        or type(observed_at_epoch) is not int
        or not 0 <= observed_at_epoch < 2**63
    ):
        raise ValueError("REAL_HOST_AUTHORIZATION_REJECTED")


def _require_sandbox_authorization(
    authorization: TestSandboxAuthorizationV1,
    profile: CutoverProfileV1,
    operation_fingerprint: str,
    phase: str,
    observed_at_epoch: int,
) -> tuple[str, int]:
    if (
        authorization.profile_fingerprint != profile.profile_fingerprint
        or authorization.operation_fingerprint != operation_fingerprint
        or authorization.phase != phase
        or observed_at_epoch >= authorization.expires_at_epoch
    ):
        raise ValueError("REAL_HOST_AUTHORIZATION_REJECTED")
    binding = fingerprint(
        "test-sandbox-authorization-v1",
        {
            "expires_at_epoch": authorization.expires_at_epoch,
            "operation_fingerprint": authorization.operation_fingerprint,
            "phase": authorization.phase,
            "profile_fingerprint": authorization.profile_fingerprint,
        },
    )
    return binding, authorization.expires_at_epoch
