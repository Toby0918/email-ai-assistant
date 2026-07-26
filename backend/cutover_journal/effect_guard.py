"""Exact synthetic effect identity and journal-transition guards."""

from __future__ import annotations

from ._canonical import is_opaque_fingerprint
from .effect_state import (
    SyntheticEffectSnapshotV1,
    SyntheticEffectStateV1,
)
from .errors import JournalContractError
from .journal_chain import (
    VerifiedJournalChainV1,
    active_observed_record,
)
from .journal_record import JournalRecordV1
from .journal_types import (
    JournalDirection,
    JournalEffectOutcome,
    JournalEventCode,
    JournalStepCode,
)


EFFECT_ERROR = "JOURNAL_OBSERVATION_AMBIGUOUS"


def assert_effect_state_intact(effect: object) -> None:
    if type(effect) is not SyntheticEffectStateV1:
        _invalid()
    _assert_values(
        initial=effect._initial,
        prepared=effect._prepared,
        published=effect._published,
        current=effect._observation,
        identity=effect._identity_mapping_intact,
        forward=effect._forward_invocations,
        reverse=effect._reverse_invocations,
    )


def assert_effect_snapshot_intact(effect: object) -> None:
    if type(effect) is not SyntheticEffectSnapshotV1:
        _invalid()
    _assert_values(
        initial=effect.initial_observation_fingerprint,
        prepared=effect.prepared_observation_fingerprint,
        published=effect.published_observation_fingerprint,
        current=effect.observation_fingerprint,
        identity=effect.identity_mapping_intact,
        forward=effect.forward_invocations,
        reverse=effect.reverse_invocations,
    )


def assert_chain_effect_binding(
    chain: object,
    effect: SyntheticEffectStateV1 | SyntheticEffectSnapshotV1,
) -> None:
    if type(chain) is not VerifiedJournalChainV1:
        _invalid()
    if type(effect) is SyntheticEffectStateV1:
        assert_effect_state_intact(effect)
    else:
        assert_effect_snapshot_intact(effect)
    values = _effect_values(effect)
    records = list(chain._forward_intents)
    if chain._active_intent is not None:
        records.append(chain._active_intent)
    if chain._pending_record is not None:
        records.append(chain._pending_record)
    for record in records:
        before, expected = _transition_for(record, values)
        if (
            record.before_observation_fingerprint != before
            or record.expected_after_observation_fingerprint != expected
        ):
            _invalid()
    _assert_invocation_counts(chain, effect)


def _assert_invocation_counts(
    chain: VerifiedJournalChainV1,
    effect: SyntheticEffectStateV1 | SyntheticEffectSnapshotV1,
) -> None:
    forward = sum(
        outcome == JournalEffectOutcome.APPLIED.value
        for outcome in chain._forward_outcomes
    )
    reverse = chain.reverse_committed
    active = chain._active_intent
    if active is not None:
        observed = active_observed_record(chain)
        applied = (
            observed.effect_outcome == JournalEffectOutcome.APPLIED.value
            if observed is not None
            else effect.observation_fingerprint
            == active.expected_after_observation_fingerprint
        )
        if applied and active.direction == JournalDirection.FORWARD.value:
            forward += 1
        elif applied and active.direction == JournalDirection.REVERSE.value:
            reverse += 1
    if (
        effect.forward_invocations != forward
        or effect.reverse_invocations != reverse
    ):
        _invalid()


def assert_pending_observation(
    chain: VerifiedJournalChainV1,
    effect: SyntheticEffectStateV1 | SyntheticEffectSnapshotV1,
) -> None:
    pending = chain._pending_record
    if pending is None:
        return
    current = (
        effect.observation_fingerprint
        if type(effect) is SyntheticEffectStateV1
        else effect.observation_fingerprint
    )
    if pending.event_code == JournalEventCode.INTENT.value:
        allowed = {pending.before_observation_fingerprint}
    elif pending.event_code == JournalEventCode.RESUME_BOUND.value:
        observed = active_observed_record(chain)
        allowed = (
            {observed.observed_effect_fingerprint}
            if observed is not None
            else {
                pending.before_observation_fingerprint,
                pending.expected_after_observation_fingerprint,
            }
        )
    else:
        allowed = {pending.observed_effect_fingerprint}
    if current not in allowed:
        _invalid()


def _assert_values(
    *,
    initial: object,
    prepared: object,
    published: object,
    current: object,
    identity: object,
    forward: object,
    reverse: object,
) -> None:
    observations = (initial, prepared, published, current)
    if (
        not all(is_opaque_fingerprint(value) for value in observations)
        or len(set(observations[:3])) != 3
        or identity is not True
        or not all(_valid_count(value) for value in (forward, reverse))
    ):
        _invalid()


def _effect_values(
    effect: SyntheticEffectStateV1 | SyntheticEffectSnapshotV1,
) -> tuple[str, str, str]:
    if type(effect) is SyntheticEffectStateV1:
        return effect._initial, effect._prepared, effect._published
    return (
        effect.initial_observation_fingerprint,
        effect.prepared_observation_fingerprint,
        effect.published_observation_fingerprint,
    )


def _transition_for(
    record: JournalRecordV1,
    values: tuple[str, str, str],
) -> tuple[str, str]:
    initial, prepared, published = values
    if record.step_code == JournalStepCode.SYNTHETIC_PREPARE.value:
        transition = (initial, prepared)
    elif record.step_code == JournalStepCode.SYNTHETIC_PUBLISH.value:
        transition = (prepared, published)
    else:
        _invalid()
    if record.direction == JournalDirection.REVERSE.value:
        return transition[1], transition[0]
    return transition


def _valid_count(value: object) -> bool:
    return type(value) is int and 0 <= value <= 1_000_000


def _invalid() -> None:
    raise JournalContractError(EFFECT_ERROR)
