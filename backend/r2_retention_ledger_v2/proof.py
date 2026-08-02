"""Closed reconciliation proof for one deterministic retention ledger."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import ApprovedCutoverBindingV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_transaction_journal_v2._canonical import canonical_json, fingerprint, strict_json_object

from .errors import RetentionLedgerError
from .ledger import R2RetentionEntryV2, R2RetentionLedgerV2


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2RetentionProofV2:
    proof_type: str
    binding_fingerprint: str = field(repr=False)
    ledger_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    reconciled_entry_count: int
    untracked_artifact_count: int
    deletion_capability_count: int
    overwrite_capability_count: int
    prune_capability_count: int
    automatic_expiry_capability_count: int
    private_payload_field_count: int
    proof_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2RetentionProofV2 requires create()")

    @classmethod
    def create(cls, *, binding, ledger, journal):
        try:
            _require(binding, ledger, journal)
            body = {"proof_type": "R2RetentionProofV2", "binding_fingerprint": binding.binding_fingerprint, "ledger_fingerprint": ledger.ledger_fingerprint, "journal_head_fingerprint": journal.current_head_fingerprint, "reconciled_entry_count": ledger.entry_count, "untracked_artifact_count": 0, "deletion_capability_count": 0, "overwrite_capability_count": 0, "prune_capability_count": 0, "automatic_expiry_capability_count": 0, "private_payload_field_count": 0}
            return _construct(body)
        except RetentionLedgerError:
            raise
        except Exception:
            raise RetentionLedgerError() from None

    @classmethod
    def from_json(cls, payload, *, binding, ledger, journal):
        try:
            source = strict_json_object(payload)
            result = cls.create(binding=binding, ledger=ledger, journal=journal)
            if canonical_json(source) != payload or source != result.to_mapping():
                raise RetentionLedgerError()
            return result
        except RetentionLedgerError:
            raise
        except Exception:
            raise RetentionLedgerError() from None

    def to_mapping(self):
        body = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "proof_fingerprint"}
        return {**body, "proof_fingerprint": self.proof_fingerprint}

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _require(binding, ledger, journal):
    zero_fields = ("untracked_artifact_count", "deletion_capability_count", "overwrite_capability_count", "prune_capability_count", "automatic_expiry_capability_count", "private_payload_field_count")
    if type(binding) is not ApprovedCutoverBindingV2 or type(ledger) is not R2RetentionLedgerV2 or type(journal) is not R2TransactionJournalV2 or ledger.binding_fingerprint != binding.binding_fingerprint or ledger.journal_head_fingerprint != journal.current_head_fingerprint or ledger.journal_record_count != journal.record_count or ledger.entry_count != len(ledger.entries) or sum(ledger.kind_counts.values()) != ledger.entry_count:
        raise RetentionLedgerError()
    if any(getattr(ledger, name) != 0 for name in zero_fields) or len({item.entry_fingerprint for item in ledger.entries}) != ledger.entry_count:
        raise RetentionLedgerError()
    if any(type(item) is not R2RetentionEntryV2 or item.retention_required is not True or item.destructive_capability_count != 0 or item.private_payload_field_count != 0 for item in ledger.entries):
        raise RetentionLedgerError()


def _construct(body):
    value = object.__new__(R2RetentionProofV2)
    for name, item in body.items():
        object.__setattr__(value, name, item)
    object.__setattr__(value, "proof_fingerprint", fingerprint("r2-retention-proof-v2", body))
    return value
