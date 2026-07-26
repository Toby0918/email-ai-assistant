"""Pure authorization validation that grants no executable capability."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .authorization import REAL_AUTHORIZATION_TYPES
from .authorization_schema import spec_for_operation
from .errors import CutoverContractError
from .profile import CutoverProfileV1
from .profile_schema import _is_fingerprint


class AuthorizationValidationStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    BLOCKED_AUTHORIZATION_MISSING = "BLOCKED_AUTHORIZATION_MISSING"
    BLOCKED_AUTHORIZATION_WRONG_TYPE = "BLOCKED_AUTHORIZATION_WRONG_TYPE"
    BLOCKED_AUTHORIZATION_NOT_YET_VALID = (
        "BLOCKED_AUTHORIZATION_NOT_YET_VALID"
    )
    BLOCKED_AUTHORIZATION_EXPIRED = "BLOCKED_AUTHORIZATION_EXPIRED"
    BLOCKED_AUTHORIZATION_WRONG_PROFILE = (
        "BLOCKED_AUTHORIZATION_WRONG_PROFILE"
    )
    BLOCKED_AUTHORIZATION_WRONG_MASTER = "BLOCKED_AUTHORIZATION_WRONG_MASTER"
    BLOCKED_AUTHORIZATION_WRONG_OPERATION = (
        "BLOCKED_AUTHORIZATION_WRONG_OPERATION"
    )
    BLOCKED_AUTHORIZATION_WRONG_OPERATOR = (
        "BLOCKED_AUTHORIZATION_WRONG_OPERATOR"
    )
    BLOCKED_AUTHORIZATION_WRONG_PHASE = "BLOCKED_AUTHORIZATION_WRONG_PHASE"
    BLOCKED_AUTHORIZATION_INVALID = "BLOCKED_AUTHORIZATION_INVALID"


@dataclass(frozen=True, slots=True)
class AuthorizationValidationResult:
    status: AuthorizationValidationStatus
    accepted: int
    rejected: int


@dataclass(frozen=True, slots=True, init=False)
class TestSandboxAuthorizationV1:
    profile_fingerprint: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    phase: str = field(repr=False)
    expires_at_epoch: int = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("test authorization requires synthetic construction")

    @classmethod
    def create(
        cls,
        *,
        profile_fingerprint: str,
        operation_fingerprint: str,
        phase: str,
        expires_at_epoch: int,
    ) -> TestSandboxAuthorizationV1:
        if (
            not _is_fingerprint(profile_fingerprint)
            or not _is_fingerprint(operation_fingerprint)
            or type(phase) is not str
            or phase not in _all_phases()
            or type(expires_at_epoch) is not int
            or not 0 <= expires_at_epoch < 2**63
        ):
            raise CutoverContractError("TEST_AUTHORIZATION_INVALID")
        value = object.__new__(cls)
        object.__setattr__(value, "profile_fingerprint", profile_fingerprint)
        object.__setattr__(value, "operation_fingerprint", operation_fingerprint)
        object.__setattr__(value, "phase", phase)
        object.__setattr__(value, "expires_at_epoch", expires_at_epoch)
        return value


def validate_real_host_authorization(
    authorization: object,
    *,
    profile: CutoverProfileV1,
    expected_operation: str,
    expected_operation_fingerprint: str,
    expected_phase: str,
    expected_operator_fingerprint: str,
    observed_at_epoch: int,
) -> AuthorizationValidationResult:
    if not _profile_is_intact(profile) or not _valid_context(
        profile,
        expected_operation,
        expected_operation_fingerprint,
        expected_phase,
        expected_operator_fingerprint,
        observed_at_epoch,
    ):
        return _blocked(AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_INVALID)
    if authorization is None:
        return _blocked(AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_MISSING)
    if type(authorization) not in REAL_AUTHORIZATION_TYPES:
        return _blocked(AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_TYPE)
    if not _authorization_is_intact(authorization):
        return _blocked(AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_INVALID)
    status = _binding_status(
        authorization,
        profile,
        expected_operation,
        expected_operation_fingerprint,
        expected_phase,
        expected_operator_fingerprint,
    )
    if status is not None:
        return _blocked(status)
    if observed_at_epoch < authorization.not_before_epoch:
        return _blocked(
            AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_NOT_YET_VALID
        )
    if observed_at_epoch >= authorization.expires_at_epoch:
        return _blocked(
            AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_EXPIRED
        )
    return AuthorizationValidationResult(
        status=AuthorizationValidationStatus.AUTHORIZED,
        accepted=1,
        rejected=0,
    )


def _profile_is_intact(profile: object) -> bool:
    if type(profile) is not CutoverProfileV1:
        return False
    try:
        CutoverProfileV1.from_mapping(profile.to_mapping())
    except Exception:
        return False
    return True


def _authorization_is_intact(authorization: object) -> bool:
    try:
        type(authorization).from_mapping(authorization.to_mapping())
    except Exception:
        return False
    return True


def _binding_status(
    authorization: object,
    profile: CutoverProfileV1,
    operation: str,
    operation_fingerprint: str,
    phase: str,
    operator_fingerprint: str,
) -> AuthorizationValidationStatus | None:
    if authorization.profile_fingerprint != profile.profile_fingerprint:
        return AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_PROFILE
    if authorization.governing_master_commit != profile.governing_master_commit:
        return AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_MASTER
    if (
        authorization.operation != operation
        or authorization.operation_fingerprint != operation_fingerprint
    ):
        return AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_OPERATION
    if authorization.operator_fingerprint != operator_fingerprint:
        return AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_OPERATOR
    if authorization.phase != phase:
        return AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_PHASE
    return None


def _valid_context(
    profile: object,
    operation: object,
    operation_fingerprint: object,
    phase: object,
    operator_fingerprint: object,
    observed_at_epoch: object,
) -> bool:
    spec = spec_for_operation(operation)
    return (
        type(profile) is CutoverProfileV1
        and spec is not None
        and type(phase) is str
        and phase in spec.phases
        and _is_fingerprint(operation_fingerprint)
        and _is_fingerprint(operator_fingerprint)
        and operator_fingerprint == profile.operator_fingerprint
        and type(observed_at_epoch) is int
        and 0 <= observed_at_epoch < 2**63
    )


def _blocked(
    status: AuthorizationValidationStatus,
) -> AuthorizationValidationResult:
    return AuthorizationValidationResult(
        status=status,
        accepted=0,
        rejected=1,
    )


def _all_phases() -> tuple[str, ...]:
    operations = (
        "real_preflight",
        "evidence_publication",
        "cutover_execution",
        "recovery",
    )
    return tuple(
        phase
        for operation in operations
        for phase in spec_for_operation(operation).phases
    )
