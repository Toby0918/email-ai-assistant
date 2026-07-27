"""Shared exact guards and journal event builders for recovery actions."""

from __future__ import annotations

from ._canonical import ZERO_FINGERPRINT
from .contracts_bridge import (
    AuthorizationValidationStatus,
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    RecoveryAuthorizationV1,
    validate_real_host_authorization,
)
from .effect_state import SyntheticEffectStateV1
from .effect_guard import (
    assert_chain_effect_binding,
    assert_effect_state_intact,
    assert_pending_observation,
)
from .errors import JournalContractError
from .journal_chain import (
    VerifiedJournalChainV1,
    active_observed_record,
    verify_synthetic_journal_snapshot,
)
from .journal_record import JournalRecordV1
from .journal_store import DurableJournalStore
from .journal_types import JournalEffectOutcome, JournalEventCode
from .operation_binding import (
    JournalOperationBindingV1,
    profile_matches_binding,
)
from .transaction import TransactionCutPoint, _crash_at


def assert_action_context(
    store: object,
    binding: object,
    effect: object,
    cut_point: object,
) -> None:
    if (
        type(store) is not DurableJournalStore
        or type(binding) is not JournalOperationBindingV1
        or type(effect) is not SyntheticEffectStateV1
        or type(cut_point) is not TransactionCutPoint
        or store._closed
        or store._binding.binding_fingerprint
        != binding.binding_fingerprint
    ):
        raise JournalContractError("JOURNAL_TRANSACTION_INVALID")
    assert_effect_state_intact(effect)


def assert_resume_authorization(
    profile: object,
    authorization: object,
    binding: JournalOperationBindingV1,
    epoch: object,
) -> None:
    _assert_authorization(
        profile,
        authorization,
        binding,
        epoch,
        expected_type=CutoverExecutionAuthorizationV1,
        operation="cutover_execution",
        phase="resume",
        exact_fingerprint=None,
    )


def assert_recovery_authorization(
    profile: object,
    authorization: object,
    binding: JournalOperationBindingV1,
    epoch: object,
) -> None:
    _assert_authorization(
        profile,
        authorization,
        binding,
        epoch,
        expected_type=RecoveryAuthorizationV1,
        operation="recovery",
        phase="rollback",
        exact_fingerprint=binding.recovery_authorization_fingerprint,
    )


def verified_chain(
    store: DurableJournalStore,
    binding: JournalOperationBindingV1,
) -> VerifiedJournalChainV1:
    return verify_synthetic_journal_snapshot(
        store._medium.snapshot(),
        binding=binding,
    )


def assert_action_chain_context(
    chain: VerifiedJournalChainV1,
    effect: SyntheticEffectStateV1,
) -> None:
    assert_chain_effect_binding(chain, effect)
    observed = active_observed_record(chain)
    if (
        observed is not None
        and effect.observation_fingerprint
        != observed.observed_effect_fingerprint
    ):
        raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")


def publish_pending_record(
    store: DurableJournalStore,
    chain: VerifiedJournalChainV1,
    binding: JournalOperationBindingV1,
    effect: SyntheticEffectStateV1,
) -> tuple[VerifiedJournalChainV1, bool]:
    pending = chain._pending_record
    if pending is None:
        return chain, False
    assert_pending_observation(chain, effect)
    store.append_record(pending)
    refreshed = verified_chain(store, binding)
    assert_action_chain_context(refreshed, effect)
    return (
        refreshed,
        pending.event_code == JournalEventCode.COMMITTED.value,
    )


def publish_fact_and_commit(
    *,
    store: DurableJournalStore,
    intent: JournalRecordV1,
    anchor: JournalRecordV1,
    prior_observed: JournalRecordV1 | None,
    authorization_fingerprint: str,
    outcome: str,
    cut_point: TransactionCutPoint,
) -> None:
    observed = prior_observed
    if observed is not None and observed.effect_outcome != outcome:
        raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
    if observed is None:
        _crash_at(cut_point, TransactionCutPoint.BEFORE_OBSERVED)
        observed = event_record(
            intent=intent,
            previous=anchor,
            event_code=JournalEventCode.EFFECT_OBSERVED.value,
            authorization_fingerprint=authorization_fingerprint,
            outcome=outcome,
        )
        store.append_record(observed)
        _crash_at(cut_point, TransactionCutPoint.AFTER_OBSERVED)
    _crash_at(cut_point, TransactionCutPoint.BEFORE_COMMIT)
    committed = event_record(
        intent=intent,
        previous=anchor if prior_observed is not None else observed,
        event_code=JournalEventCode.COMMITTED.value,
        authorization_fingerprint=authorization_fingerprint,
        outcome=outcome,
    )
    store.append_record(committed)
    _crash_at(cut_point, TransactionCutPoint.AFTER_COMMIT)


def event_record(
    *,
    intent: JournalRecordV1,
    previous: JournalRecordV1,
    event_code: str,
    authorization_fingerprint: str,
    outcome: str,
) -> JournalRecordV1:
    body = intent.to_mapping()
    body.pop("record_hash")
    body.update(
        {
            "sequence": previous.sequence + 1,
            "previous_record_hash": previous.record_hash,
            "event_code": event_code,
            "authorization_fingerprint": authorization_fingerprint,
            "effect_outcome": outcome,
            "observed_effect_fingerprint": _observed_fingerprint(
                intent, event_code, outcome
            ),
        }
    )
    return JournalRecordV1.create(body)


def _observed_fingerprint(
    intent: JournalRecordV1,
    event_code: str,
    outcome: str,
) -> str:
    if event_code == JournalEventCode.RESUME_BOUND.value:
        return ZERO_FINGERPRINT
    if outcome == JournalEffectOutcome.APPLIED.value:
        return intent.expected_after_observation_fingerprint
    return intent.before_observation_fingerprint


def _assert_authorization(
    profile: object,
    authorization: object,
    binding: JournalOperationBindingV1,
    epoch: object,
    *,
    expected_type: type,
    operation: str,
    phase: str,
    exact_fingerprint: str | None,
) -> None:
    if (
        type(profile) is not CutoverProfileV1
        or type(authorization) is not expected_type
        or not profile_matches_binding(profile, binding)
        or (
            exact_fingerprint is not None
            and authorization.authorization_fingerprint
            != exact_fingerprint
        )
    ):
        raise JournalContractError("JOURNAL_AUTHORIZATION_INVALID")
    result = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation=operation,
        expected_operation_fingerprint=binding.operation_fingerprint,
        expected_phase=phase,
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=epoch,
    )
    if result.status is not AuthorizationValidationStatus.AUTHORIZED:
        raise JournalContractError("JOURNAL_AUTHORIZATION_INVALID")
