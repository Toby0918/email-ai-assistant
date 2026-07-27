"""Explicit, authorization-aware synthetic forward resume."""

from __future__ import annotations

from .action_common import (
    assert_action_chain_context,
    assert_action_context,
    assert_resume_authorization,
    event_record,
    publish_pending_record,
    publish_fact_and_commit,
    verified_chain,
)
from .contracts_bridge import (
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
)
from .effect_state import SyntheticEffectStateV1
from .errors import JournalContractError
from .journal_chain import (
    VerifiedJournalChainV1,
    active_observed_record,
)
from .journal_record import JournalRecordV1
from .journal_store import DurableJournalStore
from .journal_types import (
    FORWARD_STEP_ORDER,
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


def resume_synthetic(
    *,
    store: DurableJournalStore,
    binding: JournalOperationBindingV1,
    profile: CutoverProfileV1,
    resume_authorization: CutoverExecutionAuthorizationV1,
    effect_state: SyntheticEffectStateV1,
    observed_at_epoch: int,
    action_at_epoch: int,
    cut_point: TransactionCutPoint = TransactionCutPoint.NONE,
) -> None:
    """Explicitly resume one exact forward step after fresh validation."""
    assert_action_context(store, binding, effect_state, cut_point)
    assert_resume_authorization(
        profile, resume_authorization, binding, observed_at_epoch
    )
    chain = verified_chain(store, binding)
    assert_action_chain_context(chain, effect_state)
    _assert_resume_pending(chain)
    chain, pending_committed = publish_pending_record(
        store, chain, binding, effect_state
    )
    if pending_committed:
        return
    observed = active_observed_record(chain)
    if (
        observed is not None
        and observed.effect_outcome
        != JournalEffectOutcome.APPLIED.value
    ):
        raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
    intent, anchor, observed, permit = _prepare_resume(
        store, chain, binding, resume_authorization, effect_state, cut_point
    )
    assert_resume_authorization(
        profile, resume_authorization, binding, action_at_epoch
    )
    assert_action_chain_context(verified_chain(store, binding), effect_state)
    _apply_if_needed(intent, effect_state, permit, observed, cut_point)
    publish_fact_and_commit(
        store=store,
        intent=intent,
        anchor=anchor,
        prior_observed=observed,
        authorization_fingerprint=(
            resume_authorization.authorization_fingerprint
        ),
        outcome=JournalEffectOutcome.APPLIED.value,
        cut_point=cut_point,
    )


def _assert_resume_pending(chain: VerifiedJournalChainV1) -> None:
    pending = chain._pending_record
    observed = active_observed_record(chain)
    if pending is not None and (
        pending.direction != JournalDirection.FORWARD.value
        or (
            pending.event_code == JournalEventCode.RESUME_BOUND.value
            and observed is not None
            and observed.effect_outcome
            != JournalEffectOutcome.APPLIED.value
        )
        or (
            pending.event_code
            in {
                JournalEventCode.EFFECT_OBSERVED.value,
                JournalEventCode.COMMITTED.value,
            }
            and pending.effect_outcome
            != JournalEffectOutcome.APPLIED.value
        )
    ):
        raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")


def _apply_if_needed(
    intent: JournalRecordV1,
    effect_state: SyntheticEffectStateV1,
    durable_permit: object,
    prior_observed: JournalRecordV1 | None,
    cut_point: TransactionCutPoint,
) -> None:
    current = effect_state.observation_fingerprint
    if prior_observed is not None:
        if (
            prior_observed.effect_outcome
            != JournalEffectOutcome.APPLIED.value
            or current != prior_observed.observed_effect_fingerprint
        ):
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
        return
    if current == intent.before_observation_fingerprint:
        _crash_at(cut_point, TransactionCutPoint.BEFORE_EFFECT)
        effect_state._apply(
            direction=JournalDirection.FORWARD.value,
            step_code=intent.step_code,
            intent=intent,
            durable_permit=durable_permit,
        )
        if (
            effect_state.observation_fingerprint
            != intent.expected_after_observation_fingerprint
        ):
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
        _crash_at(cut_point, TransactionCutPoint.AFTER_EFFECT)
    elif current != intent.expected_after_observation_fingerprint:
        raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")


def _prepare_resume(
    store: DurableJournalStore,
    chain: VerifiedJournalChainV1,
    binding: JournalOperationBindingV1,
    authorization: CutoverExecutionAuthorizationV1,
    effect: SyntheticEffectStateV1,
    cut_point: TransactionCutPoint,
) -> tuple[
    JournalRecordV1,
    JournalRecordV1,
    JournalRecordV1 | None,
    object,
]:
    if chain._active_intent is None:
        intent = _next_resume_intent(
            chain, binding, authorization, effect
        )
        _crash_at(cut_point, TransactionCutPoint.BEFORE_INTENT)
        permit = store.append_record(intent)
        _crash_at(cut_point, TransactionCutPoint.AFTER_INTENT)
        return intent, intent, None, permit
    intent = chain._active_intent
    if intent.direction != JournalDirection.FORWARD.value:
        raise JournalContractError("JOURNAL_TRANSITION_INVALID")
    return _bind_open_resume(store, chain, intent, authorization)


def _bind_open_resume(
    store: DurableJournalStore,
    chain: VerifiedJournalChainV1,
    intent: JournalRecordV1,
    authorization: CutoverExecutionAuthorizationV1,
) -> tuple[
    JournalRecordV1,
    JournalRecordV1,
    JournalRecordV1 | None,
    object,
]:
    last = chain._records[-1]
    prior_observed = active_observed_record(chain)
    if last.event_code == JournalEventCode.RESUME_BOUND.value:
        if (
            last.authorization_fingerprint
            == authorization.authorization_fingerprint
        ):
            return (
                intent,
                last,
                prior_observed,
                (
                    None
                    if prior_observed is not None
                    else store._durable_permit_for(intent)
                ),
            )
    bound = event_record(
        intent=intent,
        previous=last,
        event_code=JournalEventCode.RESUME_BOUND.value,
        authorization_fingerprint=authorization.authorization_fingerprint,
        outcome=JournalEffectOutcome.PENDING.value,
    )
    store.append_record(bound)
    return (
        intent,
        bound,
        prior_observed,
        (
            None
            if prior_observed is not None
            else store._durable_permit_for(intent)
        ),
    )


def _next_resume_intent(
    chain: VerifiedJournalChainV1,
    binding: JournalOperationBindingV1,
    authorization: CutoverExecutionAuthorizationV1,
    effect: SyntheticEffectStateV1,
) -> JournalRecordV1:
    if (
        chain.forward_committed == 0
        or chain.forward_committed >= len(FORWARD_STEP_ORDER)
        or chain.reverse_committed
    ):
        raise JournalContractError("JOURNAL_TRANSITION_INVALID")
    step = FORWARD_STEP_ORDER[chain.forward_committed]
    before, expected = effect._transition_for(step)
    if effect.observation_fingerprint != before:
        raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
    return JournalRecordV1.create(
        _intent_body(
            binding=binding,
            sequence=chain.record_count + 1,
            previous_hash=chain.head_hash,
            step_code=step,
            authorization_fingerprint=(
                authorization.authorization_fingerprint
            ),
            before=before,
            expected=expected,
        )
    )
