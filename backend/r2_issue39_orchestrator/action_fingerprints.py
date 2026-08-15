"""Content-free action, recovery, and confirmation fingerprints."""

import hashlib

from backend.r2_production_binding import ProductionCommandV2
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2


def inspection_fingerprint(action, observed):
    return hashlib.sha256(
        b"r2-issue39-stable-inspection-v1\0"
        + bytes.fromhex(action.action_fingerprint) + bytes.fromhex(observed)
    ).hexdigest()


def reverse_transition(action):
    return hashlib.sha256(
        b"r2-issue39-reverse-transition-v1\0"
        + bytes.fromhex(action.action_fingerprint)
    ).hexdigest()


def confirmation_action_fingerprint(
    action, journal, command, transition=None, remaining=None
):
    transition = transition or action.action_fingerprint
    remaining = remaining or "0" * 64
    return hashlib.sha256(
        b"r2-issue39-action-confirmation-v1\0"
        + bytes.fromhex(action.action_fingerprint)
        + bytes.fromhex(journal.current_head_fingerprint)
        + command.value.encode("ascii")
        + bytes.fromhex(transition) + bytes.fromhex(remaining)
    ).hexdigest()


def confirmation_context(catalog, action, journal, command):
    if command is ProductionCommandV2.RESUME:
        transition = journal.records[-1].transition_instance_fingerprint
        return transition, _remaining_plan(catalog, journal, transition)
    if command is ProductionCommandV2.ROLLBACK:
        transition = reverse_transition(action)
        return transition, _remaining_plan(catalog, journal, transition)
    return action.action_fingerprint, "0" * 64


def _remaining_plan(catalog, journal, transition):
    if catalog is None or transition not in {
        reverse_transition(item) for item in catalog.actions
    }:
        return "0" * 64
    from .action_runner_support import committed_actions

    committed = committed_actions(catalog, journal)
    reverse = {reverse_transition(item) for item in catalog.actions}
    done = {
        record.transition_instance_fingerprint for record in journal.records
        if record.record_type is JournalRecordTypeV2.COMMIT
        and record.transition_instance_fingerprint in reverse
    }
    pending = tuple(
        reverse_transition(item) for item in reversed(committed)
        if item.host_effect and reverse_transition(item) not in done
    )
    if transition not in pending:
        raise ValueError
    return hashlib.sha256(
        b"r2-issue39-remaining-reverse-plan-v1\0"
        + b"".join(bytes.fromhex(item) for item in pending)
    ).hexdigest()
