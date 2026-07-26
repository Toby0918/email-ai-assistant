"""Explicit pre-bound recovery and journal-derived reverse action."""

from __future__ import annotations

from .action_common import (
    assert_action_chain_context,
    assert_action_context,
    assert_recovery_authorization,
    event_record,
    publish_pending_record as publish_pending,
    publish_fact_and_commit,
    verified_chain,
)
from .contracts_bridge import CutoverProfileV1, RecoveryAuthorizationV1
from .effect_state import SyntheticEffectStateV1
from .errors import JournalContractError
from .journal_chain import (
    VerifiedJournalChainV1,
    active_observed_record,
)
from .journal_record import JournalRecordV1
from .journal_store import DurableJournalStore
from .journal_types import (
    JournalDirection,
    JournalEffectOutcome,
    JournalEventCode,
)
from .operation_binding import JournalOperationBindingV1
from .transaction import (
    TransactionCutPoint,
    _crash_at,
    _intent_body,
)


def rollback_next_synthetic(
    *,
    store: DurableJournalStore,
    binding: JournalOperationBindingV1,
    profile: CutoverProfileV1,
    recovery_authorization: RecoveryAuthorizationV1,
    effect_state: SyntheticEffectStateV1,
    observed_at_epoch: int,
    action_at_epoch: int,
    cut_point: TransactionCutPoint = TransactionCutPoint.NONE,
) -> None:
    assert_action_context(store, binding, effect_state, cut_point)
    assert_recovery_authorization(
        profile, recovery_authorization, binding, observed_at_epoch
    )
    chain = verified_chain(store, binding)
    assert_action_chain_context(chain, effect_state)
    chain, pending_committed = publish_pending(store, chain, binding, effect_state)
    if pending_committed:
        return
    if _has_open_direction(chain, JournalDirection.FORWARD.value):
        _reconcile_forward(
            store,
            chain,
            effect_state,
            recovery_authorization.authorization_fingerprint,
        )
        chain = verified_chain(store, binding)
        assert_action_chain_context(chain, effect_state)
    prepared = _prepare_reverse(
        store,
        chain,
        binding,
        recovery_authorization.authorization_fingerprint,
        effect_state,
        cut_point,
    )
    if prepared[0] is None:
        return
    assert_recovery_authorization(
        profile, recovery_authorization, binding, action_at_epoch
    )
    assert_action_chain_context(verified_chain(store, binding), effect_state)
    _finish_reverse(
        store,
        prepared,
        recovery_authorization.authorization_fingerprint,
        effect_state,
        cut_point,
    )


def _finish_reverse(
    store: DurableJournalStore,
    prepared: tuple[
        JournalRecordV1 | None,
        JournalRecordV1 | None,
        JournalRecordV1 | None,
        object | None,
    ],
    recovery_fingerprint: str,
    effect: SyntheticEffectStateV1,
    cut_point: TransactionCutPoint,
) -> None:
    intent, anchor, prior_observed, durable_permit = prepared
    current = effect.observation_fingerprint
    if prior_observed is not None:
        if current != prior_observed.observed_effect_fingerprint:
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
    elif current == intent.before_observation_fingerprint:
        _crash_at(cut_point, TransactionCutPoint.BEFORE_EFFECT)
        effect._apply(
            direction=JournalDirection.REVERSE.value,
            step_code=intent.step_code,
            intent=intent,
            durable_permit=durable_permit,
        )
        if (
            effect.observation_fingerprint
            != intent.expected_after_observation_fingerprint
        ):
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
        _crash_at(cut_point, TransactionCutPoint.AFTER_EFFECT)
    elif current != intent.expected_after_observation_fingerprint:
        raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
    publish_fact_and_commit(
        store=store,
        intent=intent,
        anchor=anchor,
        prior_observed=prior_observed,
        authorization_fingerprint=recovery_fingerprint,
        outcome=JournalEffectOutcome.APPLIED.value,
        cut_point=cut_point,
    )


def _has_open_direction(
    chain: VerifiedJournalChainV1,
    direction: str,
) -> bool:
    return (
        chain._active_intent is not None
        and chain._active_intent.direction == direction
    )


def _reconcile_forward(
    store: DurableJournalStore,
    chain: VerifiedJournalChainV1,
    effect: SyntheticEffectStateV1,
    recovery_fingerprint: str,
) -> None:
    intent = chain._active_intent
    current = effect.observation_fingerprint
    prior_observed = active_observed_record(chain)
    last = chain._records[-1]
    if prior_observed is not None:
        if current != prior_observed.observed_effect_fingerprint:
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
        _commit_reconciled(
            store,
            intent,
            last,
            prior_observed,
            recovery_fingerprint,
        )
        return
    if current == intent.before_observation_fingerprint:
        outcome = JournalEffectOutcome.NOT_APPLIED.value
    elif current == intent.expected_after_observation_fingerprint:
        outcome = JournalEffectOutcome.APPLIED.value
    else:
        raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
    observed = event_record(
        intent=intent,
        previous=last,
        event_code=JournalEventCode.EFFECT_OBSERVED.value,
        authorization_fingerprint=recovery_fingerprint,
        outcome=outcome,
    )
    store.append_record(observed)
    _commit_reconciled(
        store,
        intent,
        observed,
        observed,
        recovery_fingerprint,
    )


def _commit_reconciled(
    store: DurableJournalStore,
    intent: JournalRecordV1,
    anchor: JournalRecordV1,
    observed: JournalRecordV1,
    recovery_fingerprint: str,
) -> None:
    committed = event_record(
        intent=intent,
        previous=anchor,
        event_code=JournalEventCode.COMMITTED.value,
        authorization_fingerprint=recovery_fingerprint,
        outcome=observed.effect_outcome,
    )
    store.append_record(committed)


def _prepare_reverse(
    store: DurableJournalStore,
    chain: VerifiedJournalChainV1,
    binding: JournalOperationBindingV1,
    recovery_fingerprint: str,
    effect: SyntheticEffectStateV1,
    cut_point: TransactionCutPoint,
) -> tuple[
    JournalRecordV1 | None,
    JournalRecordV1 | None,
    JournalRecordV1 | None,
    object | None,
]:
    if _has_open_direction(chain, JournalDirection.REVERSE.value):
        intent = chain._active_intent
        last = chain._records[-1]
        observed = active_observed_record(chain)
        return (
            intent,
            last,
            observed,
            (
                None
                if observed is not None
                else store._durable_permit_for(intent)
            ),
        )
    target = _reverse_target(chain)
    if target is None:
        return None, None, None, None
    intent = _reverse_intent(
        chain, binding, recovery_fingerprint, target
    )
    if (
        effect.observation_fingerprint
        != intent.before_observation_fingerprint
    ):
        raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
    _crash_at(cut_point, TransactionCutPoint.BEFORE_INTENT)
    permit = store.append_record(intent)
    _crash_at(cut_point, TransactionCutPoint.AFTER_INTENT)
    return intent, intent, None, permit


def _reverse_target(
    chain: VerifiedJournalChainV1,
) -> JournalRecordV1 | None:
    applied = [
        intent
        for intent, outcome in zip(
            chain._forward_intents,
            chain._forward_outcomes,
            strict=True,
        )
        if outcome == JournalEffectOutcome.APPLIED.value
    ]
    if chain.reverse_committed >= len(applied):
        return None
    return applied[-1 - chain.reverse_committed]


def _reverse_intent(
    chain: VerifiedJournalChainV1,
    binding: JournalOperationBindingV1,
    recovery_fingerprint: str,
    target: JournalRecordV1,
) -> JournalRecordV1:
    body = _intent_body(
        binding=binding,
        sequence=chain.record_count + 1,
        previous_hash=chain.head_hash,
        step_code=target.step_code,
        authorization_fingerprint=recovery_fingerprint,
        before=target.expected_after_observation_fingerprint,
        expected=target.before_observation_fingerprint,
    )
    body["direction"] = JournalDirection.REVERSE.value
    return JournalRecordV1.create(body)
