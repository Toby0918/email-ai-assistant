"""Default-locked transaction entries."""

from __future__ import annotations

from .contracts_bridge import (
    CutoverExecutionAuthorizationV1,
    OperatorEntryResult,
    RecoveryAuthorizationV1,
    locked_operator_entry,
)


def locked_cutover_transaction_composition_constructor(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return locked_execute_entry(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )


def locked_execute_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return _execution_entry(
        "execute",
        profile,
        authorization,
        operation_fingerprint,
        observed_at_epoch,
    )


def locked_resume_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return _execution_entry(
        "resume",
        profile,
        authorization,
        operation_fingerprint,
        observed_at_epoch,
    )


def locked_rollback_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return locked_operator_entry(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
        authorization_type=RecoveryAuthorizationV1,
        operation="recovery",
        phase="rollback",
    )


def _execution_entry(
    phase: str,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return locked_operator_entry(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
        authorization_type=CutoverExecutionAuthorizationV1,
        operation="cutover_execution",
        phase=phase,
    )
