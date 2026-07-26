"""Strict forward and reverse journal transition reducer."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import JournalContractError
from .journal_record import JournalRecordV1
from .journal_types import (
    FORWARD_STEP_ORDER,
    JournalDirection,
    JournalEffectOutcome,
    JournalEventCode,
)


@dataclass(slots=True)
class ReducedChainState:
    forward_intents: list[JournalRecordV1]
    forward_outcomes: list[str]
    reverse_committed: int = 0
    active_intent: JournalRecordV1 | None = None
    active_authorization: str | None = None
    previous_event: str | None = None
    previous_observed: JournalRecordV1 | None = None
    reverse_started: bool = False


def reduce_records(
    records: tuple[JournalRecordV1, ...],
) -> ReducedChainState:
    state = ReducedChainState(forward_intents=[], forward_outcomes=[])
    for record in records:
        if record.direction == JournalDirection.FORWARD.value:
            _accept_forward(state, record)
        else:
            _accept_reverse(state, record)
    return state


def _accept_forward(
    state: ReducedChainState,
    record: JournalRecordV1,
) -> None:
    if state.reverse_started or _has_terminal_no_effect(state):
        _invalid()
    if state.active_intent is None:
        _begin_forward(state, record)
        return
    _assert_same_transition(state.active_intent, record)
    if record.event_code == JournalEventCode.RESUME_BOUND.value:
        _accept_resume_binding(state, record)
    elif record.event_code == JournalEventCode.EFFECT_OBSERVED.value:
        _accept_observed(state, record, allow_recovery=True)
    elif record.event_code == JournalEventCode.COMMITTED.value:
        _commit_forward(state, record)
    else:
        _invalid()


def _begin_forward(
    state: ReducedChainState,
    record: JournalRecordV1,
) -> None:
    index = len(state.forward_intents)
    if (
        index >= len(FORWARD_STEP_ORDER)
        or record.step_code != FORWARD_STEP_ORDER[index]
        or record.event_code != JournalEventCode.INTENT.value
        or (
            index == 0
            and record.authorization_fingerprint
            != record.forward_authorization_fingerprint
        )
        or record.authorization_fingerprint
        == record.recovery_authorization_fingerprint
    ):
        _invalid()
    if state.forward_intents:
        expected_before = state.forward_intents[-1]
        if (
            record.before_observation_fingerprint
            != expected_before.expected_after_observation_fingerprint
        ):
            _invalid()
    state.active_intent = record
    state.active_authorization = record.authorization_fingerprint
    state.previous_event = record.event_code
    state.previous_observed = None


def _accept_resume_binding(
    state: ReducedChainState,
    record: JournalRecordV1,
) -> None:
    if state.previous_event not in {
        JournalEventCode.INTENT.value,
        JournalEventCode.RESUME_BOUND.value,
        JournalEventCode.EFFECT_OBSERVED.value,
    }:
        _invalid()
    state.active_authorization = record.authorization_fingerprint
    state.previous_event = record.event_code


def _accept_observed(
    state: ReducedChainState,
    record: JournalRecordV1,
    *,
    allow_recovery: bool,
) -> None:
    if state.previous_event not in {
        JournalEventCode.INTENT.value,
        JournalEventCode.RESUME_BOUND.value,
    } or state.previous_observed is not None:
        _invalid()
    allowed = {state.active_authorization}
    if allow_recovery:
        allowed.add(record.recovery_authorization_fingerprint)
    if (
        record.authorization_fingerprint not in allowed
        or (
            record.effect_outcome
            == JournalEffectOutcome.NOT_APPLIED.value
            and record.authorization_fingerprint
            != record.recovery_authorization_fingerprint
        )
    ):
        _invalid()
    state.active_authorization = record.authorization_fingerprint
    state.previous_event = record.event_code
    state.previous_observed = record


def _commit_forward(
    state: ReducedChainState,
    record: JournalRecordV1,
) -> None:
    if (
        state.previous_event
        not in {
            JournalEventCode.EFFECT_OBSERVED.value,
            JournalEventCode.RESUME_BOUND.value,
        }
        or state.previous_observed is None
        or not _same_observation(state.previous_observed, record)
        or record.authorization_fingerprint
        not in {
            state.active_authorization,
            record.recovery_authorization_fingerprint,
        }
    ):
        _invalid()
    state.forward_intents.append(state.active_intent)
    state.forward_outcomes.append(record.effect_outcome)
    _clear_active(state)


def _accept_reverse(
    state: ReducedChainState,
    record: JournalRecordV1,
) -> None:
    state.reverse_started = True
    if state.active_intent is None:
        _begin_reverse(state, record)
        return
    _assert_same_transition(state.active_intent, record)
    if record.event_code == JournalEventCode.EFFECT_OBSERVED.value:
        _accept_reverse_observed(state, record)
    elif record.event_code == JournalEventCode.COMMITTED.value:
        _commit_reverse(state, record)
    else:
        _invalid()


def _begin_reverse(
    state: ReducedChainState,
    record: JournalRecordV1,
) -> None:
    target_index = _reverse_target_index(state)
    if target_index < 0:
        _invalid()
    target = state.forward_intents[target_index]
    if (
        record.event_code != JournalEventCode.INTENT.value
        or record.step_code != target.step_code
        or record.authorization_fingerprint
        != record.recovery_authorization_fingerprint
        or record.before_observation_fingerprint
        != target.expected_after_observation_fingerprint
        or record.expected_after_observation_fingerprint
        != target.before_observation_fingerprint
    ):
        _invalid()
    state.active_intent = record
    state.active_authorization = record.authorization_fingerprint
    state.previous_event = record.event_code
    state.previous_observed = None


def _accept_reverse_observed(
    state: ReducedChainState,
    record: JournalRecordV1,
) -> None:
    if (
        record.effect_outcome != JournalEffectOutcome.APPLIED.value
        or record.authorization_fingerprint
        != record.recovery_authorization_fingerprint
    ):
        _invalid()
    _accept_observed(state, record, allow_recovery=False)


def _commit_reverse(
    state: ReducedChainState,
    record: JournalRecordV1,
) -> None:
    if (
        state.previous_event != JournalEventCode.EFFECT_OBSERVED.value
        or state.previous_observed is None
        or record.effect_outcome != JournalEffectOutcome.APPLIED.value
        or not _same_observation(state.previous_observed, record)
    ):
        _invalid()
    state.reverse_committed += 1
    _clear_active(state)


def _assert_same_transition(
    intent: JournalRecordV1,
    record: JournalRecordV1,
) -> None:
    if (
        record.direction != intent.direction
        or record.step_code != intent.step_code
        or record.before_observation_fingerprint
        != intent.before_observation_fingerprint
        or record.expected_after_observation_fingerprint
        != intent.expected_after_observation_fingerprint
    ):
        _invalid()


def _same_observation(
    observed: JournalRecordV1,
    committed: JournalRecordV1,
) -> bool:
    return (
        committed.effect_outcome == observed.effect_outcome
        and committed.observed_effect_fingerprint
        == observed.observed_effect_fingerprint
    )


def _reverse_target_index(state: ReducedChainState) -> int:
    applied = [
        index
        for index, outcome in enumerate(state.forward_outcomes)
        if outcome == JournalEffectOutcome.APPLIED.value
    ]
    if state.reverse_committed >= len(applied):
        return -1
    return applied[-1 - state.reverse_committed]


def _has_terminal_no_effect(state: ReducedChainState) -> bool:
    return bool(
        state.forward_outcomes
        and state.forward_outcomes[-1]
        == JournalEffectOutcome.NOT_APPLIED.value
    )


def _clear_active(state: ReducedChainState) -> None:
    state.active_intent = None
    state.active_authorization = None
    state.previous_event = None
    state.previous_observed = None


def _invalid() -> None:
    raise JournalContractError("JOURNAL_CHAIN_INVALID")
