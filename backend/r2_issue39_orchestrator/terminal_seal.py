"""Fresh-audit terminal seals for the fixed Issue #39 transaction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from backend.r2_production_binding import (
    ExecutionConfirmationClaimV1,
    ProductionCommandV2,
)
from backend.r2_transaction_journal_v2.vocabulary import (
    JournalRecordTypeV2,
    TerminalStateV2,
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39TerminalAuditV1:
    validation_receipt_fingerprint: str = field(repr=False)
    minimal_state_fingerprint: str = field(repr=False)
    minimal_read_count: int
    audit_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("Issue39TerminalAuditV1 requires create()")

    @classmethod
    def create(cls, *, catalog, journal_head_fingerprint,
               validation_receipt_fingerprint,
               first_read_fingerprint, second_read_fingerprint):
        if (
            not _fingerprint(journal_head_fingerprint)
            or
            not _fingerprint(validation_receipt_fingerprint)
            or not _fingerprint(first_read_fingerprint)
            or first_read_fingerprint != second_read_fingerprint
        ):
            raise ValueError("R2_ISSUE39_TERMINAL_AUDIT_INVALID")
        value = object.__new__(cls)
        object.__setattr__(
            value, "validation_receipt_fingerprint",
            validation_receipt_fingerprint,
        )
        object.__setattr__(value, "minimal_state_fingerprint", first_read_fingerprint)
        object.__setattr__(value, "minimal_read_count", 2)
        object.__setattr__(
            value, "audit_fingerprint",
            _hash(
                b"r2-issue39-terminal-audit-v1\0",
                catalog.catalog_fingerprint,
                journal_head_fingerprint,
                validation_receipt_fingerprint,
                first_read_fingerprint,
            ),
        )
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39LegacyAuditV1:
    legacy_topology_fingerprint: str = field(repr=False)
    minimal_read_count: int
    audit_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("Issue39LegacyAuditV1 requires create()")

    @classmethod
    def create(cls, *, catalog, journal_head_fingerprint,
               first_read_fingerprint,
               second_read_fingerprint):
        if (
            not _fingerprint(journal_head_fingerprint)
            or not _fingerprint(first_read_fingerprint)
            or first_read_fingerprint != second_read_fingerprint
        ):
            raise ValueError("R2_ISSUE39_LEGACY_AUDIT_INVALID")
        value = object.__new__(cls)
        object.__setattr__(value, "legacy_topology_fingerprint", first_read_fingerprint)
        object.__setattr__(value, "minimal_read_count", 2)
        object.__setattr__(
            value, "audit_fingerprint",
            _hash(
                b"r2-issue39-legacy-audit-v1\0",
                catalog.catalog_fingerprint,
                journal_head_fingerprint,
                first_read_fingerprint,
            ),
        )
        return value


def terminal_transition(catalog, state=TerminalStateV2.CUTOVER_SUCCESS):
    return _hash(
        b"r2-issue39-terminal-transition-v2\0",
        catalog.catalog_fingerprint,
        _enum_fingerprint(state),
    )


def terminal_confirmation_action(catalog, journal, audit, state):
    return _hash(
        b"r2-issue39-terminal-confirmation-v2\0",
        catalog.catalog_fingerprint,
        journal.current_head_fingerprint,
        terminal_transition(catalog, state),
        audit.audit_fingerprint,
    )


def require_terminal_claim(catalog, journal, claim, audit, state):
    command = _command(state)
    transition = terminal_transition(catalog, state)
    if (
        type(claim) is not ExecutionConfirmationClaimV1
        or claim.command is not command
        or claim.prior_journal_head_fingerprint != journal.current_head_fingerprint
        or claim.transition_instance_fingerprint != transition
        or claim.remaining_reverse_plan_fingerprint != "0" * 64
        or claim.claim_sequence != len(journal.execution_confirmation_claims) + 1
        or claim.action_fingerprint
        != terminal_confirmation_action(catalog, journal, audit, state)
    ):
        raise ValueError("R2_ISSUE39_TERMINAL_CONFIRMATION_INVALID")


def terminal_claim_pending(catalog, journal):
    if not journal.records:
        return None
    record = journal.records[-1]
    if record.record_type is not JournalRecordTypeV2.AUTHORITY_CLAIM:
        return None
    for state in TerminalStateV2:
        if (
            record.transition_instance_fingerprint
            == terminal_transition(catalog, state)
            and record.execution_confirmation_claim.command is _command(state)
        ):
            return state
    return None


def append_terminal(catalog, journal, audit, state):
    pending = terminal_claim_pending(catalog, journal)
    if pending is not state:
        raise ValueError("R2_ISSUE39_TERMINAL_CONFIRMATION_INVALID")
    claim = journal.records[-1].execution_confirmation_claim
    if claim.action_fingerprint != _confirmation_for_prior_head(
        catalog, claim.prior_journal_head_fingerprint, audit, state
    ):
        raise ValueError("R2_ISSUE39_TERMINAL_CONFIRMATION_INVALID")
    final_state = (
        catalog.actions[-1].post_state_fingerprint
        if state is TerminalStateV2.CUTOVER_SUCCESS
        else audit.legacy_topology_fingerprint
    )
    return journal.append_terminal_state(
        transition_instance_fingerprint=terminal_transition(catalog, state),
        final_state_fingerprint=final_state,
        terminal_state=state,
        terminal_evidence_fingerprint=audit.audit_fingerprint,
    )


def terminal_complete(catalog, journal, ports):
    if not journal.records:
        return None
    record = journal.records[-1]
    if record.record_type is not JournalRecordTypeV2.TERMINAL_STATE:
        return None
    if len(journal.records) < 2:
        raise ValueError("R2_ISSUE39_TERMINAL_INVALID")
    claim_record = journal.records[-2]
    state = record.terminal_state
    if (
        state not in set(TerminalStateV2)
        or claim_record.record_type is not JournalRecordTypeV2.AUTHORITY_CLAIM
    ):
        raise ValueError("R2_ISSUE39_TERMINAL_INVALID")
    prior_head = claim_record.predecessor_head_fingerprint
    audit = (
        ports.terminal_audit(catalog, prior_head)
        if state is TerminalStateV2.CUTOVER_SUCCESS
        else ports.legacy_audit(catalog, prior_head)
    )
    expected_final = (
        catalog.actions[-1].post_state_fingerprint
        if state is TerminalStateV2.CUTOVER_SUCCESS
        else audit.legacy_topology_fingerprint
    )
    if (
        claim_record.transition_instance_fingerprint
        != terminal_transition(catalog, state)
        or record.transition_instance_fingerprint != terminal_transition(catalog, state)
        or claim_record.execution_confirmation_claim.command is not _command(state)
        or record.terminal_evidence_fingerprint != audit.audit_fingerprint
        or record.observed_state_fingerprint != expected_final
        or claim_record.execution_confirmation_claim.action_fingerprint
        != _confirmation_for_prior_head(catalog, prior_head, audit, state)
    ):
        raise ValueError("R2_ISSUE39_TERMINAL_INVALID")
    return state


def _confirmation_for_prior_head(catalog, prior_head, audit, state):
    return _hash(
        b"r2-issue39-terminal-confirmation-v2\0",
        catalog.catalog_fingerprint,
        prior_head,
        terminal_transition(catalog, state),
        audit.audit_fingerprint,
    )


def _command(state):
    return (
        ProductionCommandV2.RESUME
        if state is TerminalStateV2.CUTOVER_SUCCESS
        else ProductionCommandV2.ROLLBACK
    )


def _enum_fingerprint(state):
    return hashlib.sha256(state.value.encode("ascii")).hexdigest()


def _fingerprint(value):
    return type(value) is str and len(value) == 64 and all(
        item in "0123456789abcdef" for item in value
    )


def _hash(domain, *values):
    return hashlib.sha256(
        domain + b"".join(bytes.fromhex(value) for value in values)
    ).hexdigest()
