"""Closed, content-free contracts for the two independent R2 audits."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from enum import Enum

from backend.cutover_composition_contracts.canonical import is_fingerprint


class AuditKind(str, Enum):
    STOPPED_LAYOUT = "stopped_layout"
    FINAL_RUNNING_HEALTH = "final_running_health"


class AuditDisposition(str, Enum):
    ATTESTED = "ATTESTED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    INCIDENT_STOP = "INCIDENT_STOP"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class IndependentAuditObservationV1:
    audit_kind: AuditKind
    operation_fingerprint: str = field(repr=False)
    approved_binding_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    approved_identities_fingerprint: str = field(repr=False)
    health_evidence_fingerprint: str = field(repr=False)
    observed_at_epoch: int
    unambiguous: bool

    def __post_init__(self) -> None:
        valid = (
            type(self.audit_kind) is AuditKind
            and all(
                is_fingerprint(value)
                for value in (
                    self.operation_fingerprint,
                    self.approved_binding_fingerprint,
                    self.journal_head_fingerprint,
                    self.approved_identities_fingerprint,
                    self.health_evidence_fingerprint,
                )
            )
            and type(self.observed_at_epoch) is int
            and self.observed_at_epoch >= 0
            and type(self.unambiguous) is bool
        )
        if not valid:
            raise ValueError("R2_INDEPENDENT_AUDIT_OBSERVATION_INVALID")


@dataclass(frozen=True, slots=True, init=False)
class IndependentStoppedLayoutAuditReceiptV1:
    attestation_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    approved_identities_fingerprint: str = field(repr=False)
    health_evidence_fingerprint: str = field(repr=False)
    observed_at_epoch: int
    expires_at_epoch: int
    process_id: int = field(repr=False)
    _issuance_nonce: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("IndependentStoppedLayoutAuditReceiptV1 is nominal")

    def __reduce__(self):
        raise TypeError("INDEPENDENT_AUDIT_RECEIPT_NOT_SERIALIZABLE")


@dataclass(frozen=True, slots=True, init=False)
class IndependentFinalRunningHealthReceiptV1:
    attestation_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    approved_identities_fingerprint: str = field(repr=False)
    health_evidence_fingerprint: str = field(repr=False)
    observed_at_epoch: int
    expires_at_epoch: int
    process_id: int = field(repr=False)
    _issuance_nonce: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("IndependentFinalRunningHealthReceiptV1 is nominal")

    def __reduce__(self):
        raise TypeError("INDEPENDENT_AUDIT_RECEIPT_NOT_SERIALIZABLE")


@dataclass(frozen=True, slots=True)
class IndependentAuditResult:
    disposition: AuditDisposition
    receipt: (
        IndependentStoppedLayoutAuditReceiptV1
        | IndependentFinalRunningHealthReceiptV1
        | None
    ) = field(repr=False)


_ISSUED_RECEIPTS: dict[str, object] = {}


def is_issued_audit_receipt(value: object) -> bool:
    receipt_types = (
        IndependentStoppedLayoutAuditReceiptV1,
        IndependentFinalRunningHealthReceiptV1,
    )
    return (
        type(value) in receipt_types
        and type(value._issuance_nonce) is str
        and _ISSUED_RECEIPTS.get(value._issuance_nonce) is value
    )


def _issue_receipt(receipt_type, values):
    if receipt_type not in {
        IndependentStoppedLayoutAuditReceiptV1,
        IndependentFinalRunningHealthReceiptV1,
    }:
        raise TypeError("INDEPENDENT_AUDIT_RECEIPT_TYPE_INVALID")
    nonce = secrets.token_hex(32)
    receipt = object.__new__(receipt_type)
    for name, value in {**values, "_issuance_nonce": nonce}.items():
        object.__setattr__(receipt, name, value)
    _ISSUED_RECEIPTS[nonce] = receipt
    return receipt
