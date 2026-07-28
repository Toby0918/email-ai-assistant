"""Default-locked real mutation construction before Issue #39."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.cutover_contracts import (
    AuthorizationValidationStatus,
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
    validate_real_host_authorization,
)


class MutationConstructorStatus(str, Enum):
    BLOCKED_AUTHORIZATION_MISSING = "BLOCKED_AUTHORIZATION_MISSING"
    BLOCKED_TEST_AUTHORIZATION = "BLOCKED_TEST_AUTHORIZATION"
    BLOCKED_AUTHORIZATION_INVALID = "BLOCKED_AUTHORIZATION_INVALID"
    BLOCKED_NO_APPROVED_COMMAND = "BLOCKED_NO_APPROVED_COMMAND"


@dataclass(frozen=True, slots=True)
class MutationConstructorResult:
    status: MutationConstructorStatus
    blocked: int
    constructed: int


def locked_real_mutation_constructor(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
) -> MutationConstructorResult:
    if authorization is None:
        return _blocked(
            MutationConstructorStatus.BLOCKED_AUTHORIZATION_MISSING
        )
    if type(authorization) is TestSandboxAuthorizationV1:
        return _blocked(
            MutationConstructorStatus.BLOCKED_TEST_AUTHORIZATION
        )
    if type(authorization) is not CutoverExecutionAuthorizationV1:
        return _blocked(
            MutationConstructorStatus.BLOCKED_AUTHORIZATION_INVALID
        )
    validation = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation="cutover_execution",
        expected_operation_fingerprint=operation_fingerprint,
        expected_phase="execute",
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )
    if validation.status is not AuthorizationValidationStatus.AUTHORIZED:
        return _blocked(
            MutationConstructorStatus.BLOCKED_AUTHORIZATION_INVALID
        )
    return _blocked(
        MutationConstructorStatus.BLOCKED_NO_APPROVED_COMMAND
    )


def _blocked(
    status: MutationConstructorStatus,
) -> MutationConstructorResult:
    return MutationConstructorResult(
        status=status,
        blocked=1,
        constructed=0,
    )
