"""All real Issue #57 constructors remain locked before Issue #39."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.cutover_contracts import (
    AuthorizationValidationStatus,
    CutoverExecutionAuthorizationV1,
    TestSandboxAuthorizationV1,
    validate_real_host_authorization,
)

_MASTER = "7bd2eb16bf10d847a4fbd3d691256e6ad13ad6cd"


class ManagedConstructorStatus(str, Enum):
    BLOCKED_AUTHORIZATION_MISSING = "BLOCKED_AUTHORIZATION_MISSING"
    BLOCKED_TEST_AUTHORIZATION = "BLOCKED_TEST_AUTHORIZATION"
    BLOCKED_AUTHORIZATION_INVALID = "BLOCKED_AUTHORIZATION_INVALID"
    BLOCKED_NO_APPROVED_COMMAND = "BLOCKED_NO_APPROVED_COMMAND"


@dataclass(frozen=True, slots=True)
class ManagedConstructorResult:
    status: ManagedConstructorStatus
    blocked: int
    constructed: int


def locked_real_runtime_builder_constructor(**context):
    return _locked(context)


def locked_real_database_copier_constructor(**context):
    return _locked(context)


def locked_real_artifact_publisher_constructor(**context):
    return _locked(context)


def locked_real_config_publisher_constructor(**context):
    return _locked(context)


def _locked(context: dict[str, object]) -> ManagedConstructorResult:
    expected = {
        "profile",
        "authorization",
        "operation_fingerprint",
        "observed_at_epoch",
    }
    if set(context) != expected:
        return _blocked(ManagedConstructorStatus.BLOCKED_AUTHORIZATION_INVALID)
    profile = context["profile"]
    authorization = context["authorization"]
    if authorization is None:
        return _blocked(ManagedConstructorStatus.BLOCKED_AUTHORIZATION_MISSING)
    if type(authorization) is TestSandboxAuthorizationV1:
        return _blocked(ManagedConstructorStatus.BLOCKED_TEST_AUTHORIZATION)
    if (
        type(authorization) is not CutoverExecutionAuthorizationV1
        or getattr(profile, "governing_master_commit", None) != _MASTER
    ):
        return _blocked(ManagedConstructorStatus.BLOCKED_AUTHORIZATION_INVALID)
    validation = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation="cutover_execution",
        expected_operation_fingerprint=context["operation_fingerprint"],
        expected_phase="execute",
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=context["observed_at_epoch"],
    )
    if validation.status is not AuthorizationValidationStatus.AUTHORIZED:
        return _blocked(ManagedConstructorStatus.BLOCKED_AUTHORIZATION_INVALID)
    return _blocked(ManagedConstructorStatus.BLOCKED_NO_APPROVED_COMMAND)


def _blocked(status: ManagedConstructorStatus) -> ManagedConstructorResult:
    return ManagedConstructorResult(status=status, blocked=1, constructed=0)
