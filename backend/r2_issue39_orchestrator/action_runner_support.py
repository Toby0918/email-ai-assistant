"""Shared validation and durable helpers for the Issue #39 runner."""

import hashlib

from backend.r2_production_binding import ExecutionConfirmationClaimV1
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2

from .action_fingerprints import (
    confirmation_action_fingerprint,
    confirmation_context,
)
from .durable_ledger import Issue39LedgerStatusV1, _append_issue39_journal_v1


def persist(location, binding, previous, current):
    result = _append_issue39_journal_v1(
        location=location, binding=binding, previous=previous, journal=current
    )
    if result.status is not Issue39LedgerStatusV1.APPENDED:
        raise ValueError


def stable_observation(ports, action):
    first = ports.observe(action)
    second = ports.observe(action)
    if first != second or not fingerprint(first):
        raise ValueError
    return first


def effect_evidence(ports, action, direction, observed):
    callback = ports.evidence
    if callback is None:
        value = hashlib.sha256(
            b"r2-issue39-synthetic-effect-evidence-v1\0"
            + bytes.fromhex(action.action_fingerprint)
            + direction.encode("ascii") + b"\0"
            + bytes.fromhex(observed)
        ).hexdigest()
    else:
        value = callback(action, direction, observed)
    if not fingerprint(value):
        raise ValueError
    return value


def committed_actions(catalog, journal):
    forward = {item.action_fingerprint: item for item in catalog.actions}
    values = tuple(
        forward[item.transition_instance_fingerprint]
        for item in journal.records
        if item.record_type is JournalRecordTypeV2.COMMIT
        and item.transition_instance_fingerprint in forward
    )
    if values != catalog.actions[: len(values)]:
        raise ValueError
    return values


def require_confirmation_claim(
    *, catalog, action, binding, journal, command, claim
):
    transition, remaining = confirmation_context(catalog, action, journal, command)
    if (
        type(claim) is not ExecutionConfirmationClaimV1
        or claim.production_binding_fingerprint != binding.binding_fingerprint
        or claim.command is not command
        or claim.prior_journal_head_fingerprint != journal.current_head_fingerprint
        or claim.transition_instance_fingerprint != transition
        or claim.remaining_reverse_plan_fingerprint != remaining
        or claim.claim_sequence != len(journal.execution_confirmation_claims) + 1
        or claim.action_fingerprint != confirmation_action_fingerprint(
            action, journal, command, transition, remaining
        )
    ):
        raise ValueError


def attempt_token(journal):
    if (
        len(journal.records) < 2
        or journal.records[-1].record_type is not JournalRecordTypeV2.INTENT
        or journal.records[-2].record_type is not JournalRecordTypeV2.AUTHORITY_CLAIM
    ):
        raise ValueError
    return journal.records[-2].execution_confirmation_claim.claim_fingerprint


def fingerprint(value):
    return type(value) is str and len(value) == 64 and all(
        item in "0123456789abcdef" for item in value
    )
