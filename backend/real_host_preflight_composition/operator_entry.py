"""Default-locked preflight entries."""

from __future__ import annotations

from .contracts_bridge import (
    OperatorEntryResult,
    RealPreflightAuthorizationV1,
    locked_operator_entry,
)


def locked_real_host_preflight_composition_constructor(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return locked_current_topology_entry(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )


def locked_current_topology_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return _entry(
        "current_topology_preflight",
        profile,
        authorization,
        operation_fingerprint,
        observed_at_epoch,
    )


def locked_host_baseline_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return _entry(
        "host_baseline",
        profile,
        authorization,
        operation_fingerprint,
        observed_at_epoch,
    )


def locked_evidence_review_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return _entry(
        "evidence_review",
        profile,
        authorization,
        operation_fingerprint,
        observed_at_epoch,
    )


def locked_evidence_verification_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return _entry(
        "evidence_verification",
        profile,
        authorization,
        operation_fingerprint,
        observed_at_epoch,
    )


def locked_final_audit_readiness_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return _entry(
        "final_audit_readiness",
        profile,
        authorization,
        operation_fingerprint,
        observed_at_epoch,
    )


def locked_recovery_inspection_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return _entry(
        "recovery_inspection",
        profile,
        authorization,
        operation_fingerprint,
        observed_at_epoch,
    )


def _entry(
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
        authorization_type=RealPreflightAuthorizationV1,
        operation="real_preflight",
        phase=phase,
    )
