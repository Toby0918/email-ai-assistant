"""Durable restart classification and LIFO recovery for Issue #39."""

from __future__ import annotations

from backend.r2_production_binding import (
    ExecutionConfirmationClaimV1,
    ProductionCommandV2,
)
from backend.r2_transaction_journal_v2 import EffectClassificationV2
from backend.r2_transaction_journal_v2.vocabulary import (
    JournalRecordTypeV2,
    TerminalStateV2,
)
from .action_recovery_state import (
    has_reverse_activity as _has_reverse_activity,
    reversed_actions as _reversed_actions,
    states as _states,
    transition_context as _transition_context,
)


def _resolve_pending(catalog, binding, location, ports, journal):
    legal = journal.next_legal_action
    if legal == "READ_ONLY_INSPECTION":
        journal = _classify_pending(catalog, binding, location, ports, journal)
        return _resume_classified(catalog, binding, location, ports, journal)
    if legal == "CLAIM_FRESH_EXECUTION_CONFIRMATION" and journal.records and (
        journal.records[-1].record_type
        in {
            JournalRecordTypeV2.RECOVERY_CLASSIFICATION,
            JournalRecordTypeV2.EFFECT_OBSERVATION,
        }
    ):
        return _resume_classified(catalog, binding, location, ports, journal)
    if legal == "APPEND_INTENT":
        return _continue_claim(catalog, binding, location, ports, journal)
    if legal == "INCIDENT_STOP":
        raise ValueError
    return journal


def _classify_pending(catalog, binding, location, ports, journal):
    from .action_runner import _persist, _stable_observation
    from .action_runner_support import effect_evidence

    intent = journal.records[-1]
    action, direction = _transition_context(
        catalog, intent.transition_instance_fingerprint
    )
    observed = _stable_observation(ports, action)
    evidence = effect_evidence(ports, action, direction, observed)
    if observed == intent.pre_state_fingerprint:
        classification = EffectClassificationV2.EFFECT_ABSENT_EXACT
    elif observed == intent.post_state_fingerprint:
        classification = EffectClassificationV2.EFFECT_PRESENT_EXACT
    elif ports.partial(action, direction, observed):
        classification = EffectClassificationV2.EFFECT_PARTIAL_RESUMABLE
    else:
        classification = EffectClassificationV2.EFFECT_AMBIGUOUS
    classified = journal.append_recovery_classification(
        transition_instance_fingerprint=intent.transition_instance_fingerprint,
        observed_state_fingerprint=observed,
        classification=classification,
        inspection_receipt_fingerprint=evidence,
    )
    _persist(location, binding, journal, classified)
    if classification is EffectClassificationV2.EFFECT_AMBIGUOUS:
        raise ValueError
    return classified


def _resume_classified(catalog, binding, location, ports, journal):
    from .action_runner import _persist, _require_confirmation_claim

    classified = journal.records[-1]
    transition = classified.transition_instance_fingerprint
    action, _direction = _transition_context(catalog, transition)
    command = ProductionCommandV2.RESUME
    claim = ports.confirm(action, journal, command)
    _require_confirmation_claim(
        catalog=catalog, action=action, binding=binding, journal=journal,
        command=command, claim=claim,
    )
    claimed = journal.append_execution_confirmation_claim(
        claim=claim,
        transition_instance_fingerprint=transition,
        **ports.clock(),
    )
    _persist(location, binding, journal, claimed)
    return _continue_claim(catalog, binding, location, ports, claimed)


def _continue_claim(catalog, binding, location, ports, journal):
    from .action_runner import _persist

    claim = journal.records[-1]
    if claim.record_type is not JournalRecordTypeV2.AUTHORITY_CLAIM:
        raise ValueError
    classified = journal.records[-2] if len(journal.records) >= 2 else None
    if classified is None or classified.record_type not in {
        JournalRecordTypeV2.RECOVERY_CLASSIFICATION,
        JournalRecordTypeV2.EFFECT_OBSERVATION,
    }:
        action, direction = _transition_context(
            catalog, claim.transition_instance_fingerprint
        )
        pre_state, post_state = _states(action, direction)
        pending = journal.append_intent(
            transition_instance_fingerprint=claim.transition_instance_fingerprint,
            pre_state_fingerprint=pre_state,
            post_state_fingerprint=post_state,
        )
        _persist(location, binding, journal, pending)
        return _apply_pending(
            action, direction, binding, location, ports, pending
        )
    if classified.transition_instance_fingerprint != claim.transition_instance_fingerprint:
        raise ValueError
    if classified.effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT:
        return _commit_observed(catalog, binding, location, journal)
    action, direction = _transition_context(
        catalog, classified.transition_instance_fingerprint
    )
    pre_state, post_state = _states(action, direction)
    pending = journal.append_intent(
        transition_instance_fingerprint=classified.transition_instance_fingerprint,
        pre_state_fingerprint=pre_state,
        post_state_fingerprint=post_state,
    )
    _persist(location, binding, journal, pending)
    return _apply_pending(
        action, direction, binding, location, ports, pending,
        allow_partial=(
            classified.effect_classification
            is EffectClassificationV2.EFFECT_PARTIAL_RESUMABLE
        ),
    )


def _apply_pending(
    action, direction, binding, location, ports, journal, *, allow_partial=False
):
    from .action_runner import _persist, _stable_observation
    from .action_runner_support import effect_evidence

    pre_state, post_state = _states(action, direction)
    ports.reverify(action, direction)
    observed = _stable_observation(ports, action)
    if observed != pre_state and not (
        allow_partial and ports.partial(action, direction, observed)
    ):
        raise ValueError
    from .action_runner import _attempt_token

    applied = ports.apply(action, direction, _attempt_token(journal))
    if action.host_effect:
        if _stable_observation(ports, action) != post_state:
            raise ValueError
    elif direction != "forward" or applied != post_state:
        raise ValueError
    transition = journal.records[-1].transition_instance_fingerprint
    evidence = effect_evidence(ports, action, direction, post_state)
    complete = journal.append_effect_observation(
        transition_instance_fingerprint=transition,
        observed_state_fingerprint=post_state,
        classification=EffectClassificationV2.EFFECT_PRESENT_EXACT,
        evidence_receipt_fingerprint=evidence,
    ).append_commit(
        transition_instance_fingerprint=transition,
        committed_state_fingerprint=post_state,
        evidence_receipt_fingerprint=evidence,
    )
    _persist(location, binding, journal, complete)
    return complete


def _commit_observed(catalog, binding, location, journal):
    from .action_runner import _persist

    last = journal.records[-1]
    if last.record_type is JournalRecordTypeV2.AUTHORITY_CLAIM:
        observed = journal.records[-2]
    elif last.record_type is JournalRecordTypeV2.EFFECT_OBSERVATION:
        observed = last
    else:
        raise ValueError
    action, direction = _transition_context(
        catalog, observed.transition_instance_fingerprint
    )
    _pre_state, post_state = _states(action, direction)
    if (
        observed.record_type not in {
            JournalRecordTypeV2.RECOVERY_CLASSIFICATION,
            JournalRecordTypeV2.EFFECT_OBSERVATION,
        }
        or observed.effect_classification
        is not EffectClassificationV2.EFFECT_PRESENT_EXACT
        or observed.observed_state_fingerprint != post_state
    ):
        raise ValueError
    committed = journal.append_commit(
        transition_instance_fingerprint=observed.transition_instance_fingerprint,
        committed_state_fingerprint=post_state,
        evidence_receipt_fingerprint=observed.inspection_receipt_fingerprint,
    )
    _persist(location, binding, journal, committed)
    return committed


def _recover(catalog, binding, location, ports, journal):
    from .action_runner import (
        Issue39ActionRunStatusV1,
        _committed_actions,
        _result,
    )

    committed = _committed_actions(catalog, journal)
    reversed_actions = list(_reversed_actions(catalog, journal))
    if not committed:
        return _result(Issue39ActionRunStatusV1.SAFE_ABORT, (), (), journal)
    ports.recovery_inspect(journal)
    reversed_set = {action.action_fingerprint for action in reversed_actions}
    try:
        journal = _rollback_actions(
            catalog, binding, location, ports, journal, committed,
            reversed_actions, reversed_set,
        )
        from .action_runner import _start_terminal

        journal = _start_terminal(
            catalog, binding, location, ports, journal,
            TerminalStateV2.LEGACY_FLAT_LAYOUT_RESTORED,
        )
        return _result(
            Issue39ActionRunStatusV1.LEGACY_RECOVERED,
            committed,
            tuple(reversed_actions),
            journal,
        )
    except Exception:
        return _result(
            Issue39ActionRunStatusV1.INCIDENT_STOP,
            committed,
            tuple(reversed_actions),
            journal,
        )


def _rollback_actions(
    catalog, binding, location, ports, journal, committed,
    reversed_actions, reversed_set,
):
    from .action_runner import (
        _persist, _require_confirmation_claim, _reverse_transition,
        _stable_observation,
    )

    for action in reversed(committed):
        if not action.host_effect or action.action_fingerprint in reversed_set:
            continue
        ports.reverify(action, "rollback")
        if _stable_observation(ports, action) != action.post_state_fingerprint:
            raise ValueError
        command = ProductionCommandV2.ROLLBACK
        claim = ports.confirm(action, journal, command)
        transition = _reverse_transition(action)
        _require_confirmation_claim(
            catalog=catalog, action=action, binding=binding,
            journal=journal, command=command, claim=claim,
        )
        pending = journal.append_execution_confirmation_claim(
            claim=claim, transition_instance_fingerprint=transition,
            **ports.clock(),
        ).append_intent(
            transition_instance_fingerprint=transition,
            pre_state_fingerprint=action.post_state_fingerprint,
            post_state_fingerprint=action.pre_state_fingerprint,
        )
        _persist(location, binding, journal, pending)
        journal = _apply_pending(
            action, "rollback", binding, location, ports, pending
        )
        reversed_actions.append(action)
    return journal
