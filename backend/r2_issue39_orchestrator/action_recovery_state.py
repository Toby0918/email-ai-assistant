"""Pure catalog and journal state projections for recovery."""

from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2

from .action_fingerprints import reverse_transition


def transition_context(catalog, transition):
    matches = []
    for action in catalog.actions:
        if transition == action.action_fingerprint:
            matches.append((action, "forward"))
        if transition == reverse_transition(action):
            matches.append((action, "rollback"))
    if len(matches) != 1:
        raise ValueError
    return matches[0]


def states(action, direction):
    if direction == "forward":
        return action.pre_state_fingerprint, action.post_state_fingerprint
    if direction == "rollback":
        return action.post_state_fingerprint, action.pre_state_fingerprint
    raise ValueError


def reversed_actions(catalog, journal):
    reverse = {reverse_transition(action): action for action in catalog.actions}
    return tuple(
        reverse[record.transition_instance_fingerprint]
        for record in journal.records
        if record.record_type is JournalRecordTypeV2.COMMIT
        and record.transition_instance_fingerprint in reverse
    )


def has_reverse_activity(catalog, journal):
    transitions = {reverse_transition(action) for action in catalog.actions}
    return any(
        record.transition_instance_fingerprint in transitions
        for record in journal.records
    )
