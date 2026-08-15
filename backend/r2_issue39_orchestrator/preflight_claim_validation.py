"""Live-consumption and historical validation for preflight claims."""

from __future__ import annotations

from dataclasses import dataclass

from backend.r2_production_binding.claim import (
    _begin_execution_confirmation_append_v1,
    _complete_execution_confirmation_append_v1,
    _consume_execution_confirmation_attempt_v1,
    validate_new_execution_confirmation_claim,
    validate_reconstructed_execution_confirmation_claim,
)


def validate_and_begin(ledger, claim, observed_at_epoch, observed_monotonic_ns):
    _begin_execution_confirmation_append_v1(claim)
    validate_new_execution_confirmation_claim(
        binding=ledger.binding,
        candidate=claim,
        durable_claims=durable_claims(ledger),
        observed_at_epoch=observed_at_epoch,
        observed_monotonic_ns=observed_monotonic_ns,
        expected_prior_journal_head_fingerprint=ledger.head,
    )


def complete_and_consume(ledger, claim):
    _complete_execution_confirmation_append_v1(
        claim, _claim_append_view(ledger, claim)
    )
    _consume_execution_confirmation_attempt_v1(claim)


def validate_history(ledger):
    durable = []
    for record in ledger.records:
        if record.kind != "claim":
            continue
        validate_reconstructed_execution_confirmation_claim(
            binding=ledger.binding,
            candidate=record.claim,
            durable_claims=tuple(durable),
            expected_prior_journal_head_fingerprint=record.predecessor_fingerprint,
        )
        durable.append(record.claim)


def durable_claims(ledger):
    return tuple(item.claim for item in ledger.records if item.kind == "claim")


class _AuthorityKind:
    value = "AUTHORITY_CLAIM"


@dataclass(frozen=True, slots=True)
class _ClaimRecordView:
    record_type: object
    execution_confirmation_claim: object
    predecessor_head_fingerprint: str
    transition_instance_fingerprint: str
    journal_owner_fingerprint: str
    head_fingerprint: str


@dataclass(frozen=True, slots=True)
class _ClaimAppendView:
    records: tuple
    execution_confirmation_claims: tuple
    current_head_fingerprint: str


def _claim_append_view(ledger, claim):
    record = ledger.records[-1]
    view = _ClaimRecordView(
        _AuthorityKind(), claim, record.predecessor_fingerprint,
        record.transition_fingerprint, ledger.owner_fingerprint,
        record.record_fingerprint,
    )
    return _ClaimAppendView(
        (view,), (*durable_claims(ledger)[:-1], claim),
        record.record_fingerprint,
    )
