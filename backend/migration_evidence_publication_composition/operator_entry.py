"""Default-locked evidence entry."""

from __future__ import annotations

from .contracts_bridge import (
    EvidencePublicationAuthorizationV1,
    OperatorEntryResult,
    locked_operator_entry,
)


def locked_migration_evidence_publication_composition_constructor(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> OperatorEntryResult:
    return locked_evidence_publication_entry(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )


def locked_evidence_publication_entry(
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
        authorization_type=EvidencePublicationAuthorizationV1,
        operation="evidence_publication",
        phase="evidence_publication",
    )
