"""Fixed synthetic forward transaction with durable journal ordering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ._canonical import ZERO_FINGERPRINT
from .contracts_bridge import (
    AuthorizationValidationStatus,
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    validate_real_host_authorization,
)
from .effect_state import SyntheticEffectStateV1
from .effect_guard import (
    assert_chain_effect_binding,
    assert_effect_state_intact,
)
from .errors import JournalContractError
from .journal_chain import (
    VerifiedJournalChainV1,
    verify_synthetic_journal_snapshot,
)
from .journal_record import JournalRecordV1
from .journal_store import DurableJournalStore
from .journal_types import (
    FORWARD_STEP_ORDER,
    JournalDirection,
    JournalEffectOutcome,
    JournalEventCode,
)
from .operation_binding import (
    JournalOperationBindingV1,
    profile_matches_binding,
)


class TransactionCutPoint(str, Enum):
    NONE = "NONE"
    BEFORE_INTENT = "BEFORE_INTENT"
    AFTER_INTENT = "AFTER_INTENT"
    BEFORE_EFFECT = "BEFORE_EFFECT"
    AFTER_EFFECT = "AFTER_EFFECT"
    BEFORE_OBSERVED = "BEFORE_OBSERVED"
    AFTER_OBSERVED = "AFTER_OBSERVED"
    BEFORE_COMMIT = "BEFORE_COMMIT"
    AFTER_COMMIT = "AFTER_COMMIT"


@dataclass(slots=True, init=False, repr=False)
class SyntheticJournalTransaction:
    _store: DurableJournalStore
    _binding: JournalOperationBindingV1
    _effect_state: SyntheticEffectStateV1

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticJournalTransaction requires begin()")

    @classmethod
    def begin(
        cls,
        *,
        store: DurableJournalStore,
        binding: JournalOperationBindingV1,
        effect_state: SyntheticEffectStateV1,
    ) -> SyntheticJournalTransaction:
        if (
            type(store) is not DurableJournalStore
            or type(binding) is not JournalOperationBindingV1
            or type(effect_state) is not SyntheticEffectStateV1
            or store._closed
            or store._binding.binding_fingerprint
            != binding.binding_fingerprint
        ):
            raise JournalContractError("JOURNAL_TRANSACTION_INVALID")
        assert_effect_state_intact(effect_state)
        transaction = object.__new__(cls)
        transaction._store = store
        transaction._binding = binding
        transaction._effect_state = effect_state
        return transaction

    def run_next_forward(
        self,
        *,
        profile: CutoverProfileV1,
        authorization: CutoverExecutionAuthorizationV1,
        inspected_at_epoch: int,
        action_at_epoch: int,
        cut_point: TransactionCutPoint = TransactionCutPoint.NONE,
    ) -> None:
        _assert_cut_point(cut_point)
        _assert_execute_authorization(
            profile,
            authorization,
            self._binding,
            inspected_at_epoch,
        )
        chain = self._verified_chain()
        assert_chain_effect_binding(chain, self._effect_state)
        intent = self._build_next_intent(chain, authorization)
        _crash_at(cut_point, TransactionCutPoint.BEFORE_INTENT)
        permit = self._store.append_record(intent)
        _crash_at(cut_point, TransactionCutPoint.AFTER_INTENT)
        _assert_execute_authorization(
            profile,
            authorization,
            self._binding,
            action_at_epoch,
        )
        assert_chain_effect_binding(
            self._verified_chain(), self._effect_state
        )
        self._apply_forward(intent, permit, cut_point)
        self._publish_completion(intent, cut_point)

    def _verified_chain(self) -> VerifiedJournalChainV1:
        return verify_synthetic_journal_snapshot(
            self._store._medium.snapshot(),
            binding=self._binding,
        )

    def _build_next_intent(
        self,
        chain: VerifiedJournalChainV1,
        authorization: CutoverExecutionAuthorizationV1,
    ) -> JournalRecordV1:
        if (
            chain.open_event is not None
            or chain.reverse_committed
            or chain.forward_committed >= len(FORWARD_STEP_ORDER)
        ):
            raise JournalContractError("JOURNAL_TRANSITION_INVALID")
        step_code = FORWARD_STEP_ORDER[chain.forward_committed]
        before, expected = self._effect_state._transition_for(step_code)
        if self._effect_state.observation_fingerprint != before:
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
        return JournalRecordV1.create(
            _intent_body(
                binding=self._binding,
                sequence=chain.record_count + 1,
                previous_hash=chain.head_hash,
                step_code=step_code,
                authorization_fingerprint=(
                    authorization.authorization_fingerprint
                ),
                before=before,
                expected=expected,
            )
        )

    def _apply_forward(
        self,
        intent: JournalRecordV1,
        durable_permit: object,
        cut_point: TransactionCutPoint,
    ) -> None:
        if (
            self._effect_state.observation_fingerprint
            != intent.before_observation_fingerprint
        ):
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
        _crash_at(cut_point, TransactionCutPoint.BEFORE_EFFECT)
        self._effect_state._apply(
            direction=JournalDirection.FORWARD.value,
            step_code=intent.step_code,
            intent=intent,
            durable_permit=durable_permit,
        )
        if (
            self._effect_state.observation_fingerprint
            != intent.expected_after_observation_fingerprint
        ):
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
        _crash_at(cut_point, TransactionCutPoint.AFTER_EFFECT)

    def _publish_completion(
        self,
        intent: JournalRecordV1,
        cut_point: TransactionCutPoint,
    ) -> None:
        assert_effect_state_intact(self._effect_state)
        if (
            self._effect_state.observation_fingerprint
            != intent.expected_after_observation_fingerprint
        ):
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
        _crash_at(cut_point, TransactionCutPoint.BEFORE_OBSERVED)
        observed = _followup_record(
            intent,
            event_code=JournalEventCode.EFFECT_OBSERVED.value,
        )
        self._store.append_record(observed)
        _crash_at(cut_point, TransactionCutPoint.AFTER_OBSERVED)
        _crash_at(cut_point, TransactionCutPoint.BEFORE_COMMIT)
        committed = _followup_record(
            observed,
            event_code=JournalEventCode.COMMITTED.value,
        )
        self._store.append_record(committed)
        _crash_at(cut_point, TransactionCutPoint.AFTER_COMMIT)


def _assert_execute_authorization(
    profile: object,
    authorization: object,
    binding: JournalOperationBindingV1,
    observed_at_epoch: object,
) -> None:
    if (
        type(profile) is not CutoverProfileV1
        or type(authorization) is not CutoverExecutionAuthorizationV1
        or not profile_matches_binding(profile, binding)
        or authorization.authorization_fingerprint
        != binding.forward_authorization_fingerprint
    ):
        raise JournalContractError("JOURNAL_AUTHORIZATION_INVALID")
    result = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation="cutover_execution",
        expected_operation_fingerprint=binding.operation_fingerprint,
        expected_phase="execute",
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )
    if result.status is not AuthorizationValidationStatus.AUTHORIZED:
        raise JournalContractError("JOURNAL_AUTHORIZATION_INVALID")


def _intent_body(
    *,
    binding: JournalOperationBindingV1,
    sequence: int,
    previous_hash: str,
    step_code: str,
    authorization_fingerprint: str,
    before: str,
    expected: str,
) -> dict[str, object]:
    return {
        "record_type": "JournalRecordV1",
        "sequence": sequence,
        "previous_record_hash": previous_hash,
        "step_code": step_code,
        "direction": JournalDirection.FORWARD.value,
        "event_code": JournalEventCode.INTENT.value,
        "governing_master_commit": binding.governing_master_commit,
        "operation_fingerprint": binding.operation_fingerprint,
        "profile_fingerprint": binding.profile_fingerprint,
        "forward_authorization_fingerprint": (
            binding.forward_authorization_fingerprint
        ),
        "recovery_authorization_fingerprint": (
            binding.recovery_authorization_fingerprint
        ),
        "owner_fingerprint": binding.owner_fingerprint,
        "authorization_fingerprint": authorization_fingerprint,
        "before_observation_fingerprint": before,
        "expected_after_observation_fingerprint": expected,
        "observed_effect_fingerprint": ZERO_FINGERPRINT,
        "effect_outcome": JournalEffectOutcome.PENDING.value,
    }


def _followup_record(
    previous: JournalRecordV1,
    *,
    event_code: str,
) -> JournalRecordV1:
    body = previous.to_mapping()
    body.pop("record_hash")
    body.update(
        {
            "sequence": previous.sequence + 1,
            "previous_record_hash": previous.record_hash,
            "event_code": event_code,
            "observed_effect_fingerprint": (
                previous.expected_after_observation_fingerprint
            ),
            "effect_outcome": JournalEffectOutcome.APPLIED.value,
        }
    )
    return JournalRecordV1.create(body)


def _assert_cut_point(cut_point: object) -> None:
    if type(cut_point) is not TransactionCutPoint:
        raise JournalContractError("JOURNAL_TRANSACTION_INVALID")


def _crash_at(
    selected: TransactionCutPoint,
    current: TransactionCutPoint,
) -> None:
    if selected is current:
        raise JournalContractError("SYNTHETIC_CRASH")
