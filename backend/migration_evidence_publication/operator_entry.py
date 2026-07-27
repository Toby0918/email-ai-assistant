"""Default-locked real Migration Evidence operator entries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .contracts_bridge import (
    AuthorizationValidationStatus,
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
    validate_real_host_authorization,
)


class EvidenceOperatorEntryStatus(str, Enum):
    """Fixed content-free reasons that execution remains blocked."""

    BLOCKED_NO_APPROVED_COMMAND = "BLOCKED_NO_APPROVED_COMMAND"
    BLOCKED_AUTHORIZATION_MISSING = "BLOCKED_AUTHORIZATION_MISSING"
    BLOCKED_AUTHORIZATION_WRONG_PHASE = "BLOCKED_AUTHORIZATION_WRONG_PHASE"
    BLOCKED_TEST_AUTHORIZATION = "BLOCKED_TEST_AUTHORIZATION"
    BLOCKED_AUTHORIZATION_INVALID = "BLOCKED_AUTHORIZATION_INVALID"


@dataclass(frozen=True, slots=True)
class EvidenceOperatorEntryResult:
    status: EvidenceOperatorEntryStatus
    blocked: int
    executed: int


def locked_evidence_review_entry(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
) -> EvidenceOperatorEntryResult:
    return _locked_entry(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
        operation="real_preflight",
        phase="evidence_review",
    )


def locked_evidence_publication_entry(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
) -> EvidenceOperatorEntryResult:
    return _locked_entry(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
        operation="evidence_publication",
        phase="evidence_publication",
    )


def locked_evidence_verification_entry(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
) -> EvidenceOperatorEntryResult:
    return _locked_entry(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
        operation="real_preflight",
        phase="evidence_verification",
    )


def _locked_entry(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
    operation: str,
    phase: str,
) -> EvidenceOperatorEntryResult:
    if authorization is None:
        return _blocked(
            EvidenceOperatorEntryStatus.BLOCKED_AUTHORIZATION_MISSING
        )
    if type(authorization) is TestSandboxAuthorizationV1:
        return _blocked(
            EvidenceOperatorEntryStatus.BLOCKED_TEST_AUTHORIZATION
        )
    validation = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation=operation,
        expected_operation_fingerprint=operation_fingerprint,
        expected_phase=phase,
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )
    if validation.status is AuthorizationValidationStatus.AUTHORIZED:
        return _blocked(
            EvidenceOperatorEntryStatus.BLOCKED_NO_APPROVED_COMMAND
        )
    if validation.status is AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_PHASE:
        return _blocked(
            EvidenceOperatorEntryStatus.BLOCKED_AUTHORIZATION_WRONG_PHASE
        )
    return _blocked(
        EvidenceOperatorEntryStatus.BLOCKED_AUTHORIZATION_INVALID
    )


def _blocked(
    status: EvidenceOperatorEntryStatus,
) -> EvidenceOperatorEntryResult:
    return EvidenceOperatorEntryResult(status=status, blocked=1, executed=0)
