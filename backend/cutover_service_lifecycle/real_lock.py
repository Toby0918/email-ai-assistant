"""Real Issue #58 lifecycle construction remains locked before Issue #39."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.cutover_contracts import (
    AuthorizationValidationStatus,
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    RecoveryAuthorizationV1,
    TestSandboxAuthorizationV1,
    validate_real_host_authorization,
)

from .canonical import is_fingerprint

_MASTER = "dcb53169f7c8e73b6bf5387a02b18d4e6741d6ee"


class LifecycleConstructorStatus(str, Enum):
    BLOCKED_EXECUTION_AUTHORIZATION_MISSING = (
        "BLOCKED_EXECUTION_AUTHORIZATION_MISSING"
    )
    BLOCKED_RECOVERY_AUTHORIZATION_MISSING = (
        "BLOCKED_RECOVERY_AUTHORIZATION_MISSING"
    )
    BLOCKED_TEST_AUTHORIZATION = "BLOCKED_TEST_AUTHORIZATION"
    BLOCKED_AUTHORIZATION_INVALID = "BLOCKED_AUTHORIZATION_INVALID"
    BLOCKED_NO_APPROVED_COMMAND = "BLOCKED_NO_APPROVED_COMMAND"


@dataclass(frozen=True, slots=True)
class LifecycleConstructorResult:
    status: LifecycleConstructorStatus
    blocked: int
    constructed: int


def locked_real_service_lifecycle_constructor(
    **context: object,
) -> LifecycleConstructorResult:
    if set(context) != _CONTEXT_FIELDS:
        return _blocked(
            LifecycleConstructorStatus.BLOCKED_AUTHORIZATION_INVALID
        )
    try:
        early_status = _early_status(context)
    except Exception:
        return _blocked(
            LifecycleConstructorStatus.BLOCKED_AUTHORIZATION_INVALID
        )
    if early_status is not None:
        return _blocked(early_status)
    if not _both_authorizations_valid(context):
        return _blocked(
            LifecycleConstructorStatus.BLOCKED_AUTHORIZATION_INVALID
        )
    return _blocked(
        LifecycleConstructorStatus.BLOCKED_NO_APPROVED_COMMAND
    )


_CONTEXT_FIELDS = {
    "profile",
    "execution_authorization",
    "recovery_authorization",
    "operation_fingerprint",
    "observed_at_epoch",
}


def _early_status(context: dict[str, object]):
    execution = context["execution_authorization"]
    recovery = context["recovery_authorization"]
    if execution is None:
        return (
            LifecycleConstructorStatus
            .BLOCKED_EXECUTION_AUTHORIZATION_MISSING
        )
    if recovery is None:
        return (
            LifecycleConstructorStatus
            .BLOCKED_RECOVERY_AUTHORIZATION_MISSING
        )
    if (
        type(execution) is TestSandboxAuthorizationV1
        or type(recovery) is TestSandboxAuthorizationV1
    ):
        return LifecycleConstructorStatus.BLOCKED_TEST_AUTHORIZATION
    if (
        type(execution) is not CutoverExecutionAuthorizationV1
        or type(recovery) is not RecoveryAuthorizationV1
        or type(context["profile"]) is not CutoverProfileV1
        or context["profile"].governing_master_commit != _MASTER
        or not is_fingerprint(context["operation_fingerprint"])
        or type(context["observed_at_epoch"]) is not int
        or context["observed_at_epoch"] < 0
    ):
        return LifecycleConstructorStatus.BLOCKED_AUTHORIZATION_INVALID
    return None


def _both_authorizations_valid(context: dict[str, object]) -> bool:
    profile = context["profile"]
    operation = context["operation_fingerprint"]
    observed = context["observed_at_epoch"]
    try:
        execution_result = validate_real_host_authorization(
            context["execution_authorization"],
            profile=profile,
            expected_operation="cutover_execution",
            expected_operation_fingerprint=operation,
            expected_phase="execute",
            expected_operator_fingerprint=profile.operator_fingerprint,
            observed_at_epoch=observed,
        )
        recovery_result = validate_real_host_authorization(
            context["recovery_authorization"],
            profile=profile,
            expected_operation="recovery",
            expected_operation_fingerprint=operation,
            expected_phase="rollback",
            expected_operator_fingerprint=profile.operator_fingerprint,
            observed_at_epoch=observed,
        )
    except Exception:
        return False
    return (
        execution_result.status
        is AuthorizationValidationStatus.AUTHORIZED
        and recovery_result.status
        is AuthorizationValidationStatus.AUTHORIZED
    )


def _blocked(status: LifecycleConstructorStatus) -> LifecycleConstructorResult:
    return LifecycleConstructorResult(
        status=status, blocked=1, constructed=0
    )
