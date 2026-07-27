"""Pure reducer from a verified chain and observation to one status."""

from __future__ import annotations

from .contracts_bridge import (
    AuthorizationValidationStatus,
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    RecoveryAuthorizationV1,
    validate_real_host_authorization,
)
from .closed_classifier import classify_closed
from .effect_state import SyntheticEffectSnapshotV1
from .journal_chain import (
    VerifiedJournalChainV1,
    active_observed_record,
)
from .journal_types import JournalDirection, JournalEffectOutcome
from .operation_binding import JournalOperationBindingV1
from .pending_classifier import classify_pending
from .recovery_types import (
    JournalOperationPhase,
    JournalOperationStatus,
)

_OPEN_PHASES = {
    (JournalDirection.FORWARD.value, True): JournalOperationPhase.FORWARD_ACTION,
    (JournalDirection.FORWARD.value, False): JournalOperationPhase.FORWARD_OBSERVATION,
    (JournalDirection.REVERSE.value, True): JournalOperationPhase.REVERSE_ACTION,
    (JournalDirection.REVERSE.value, False): JournalOperationPhase.REVERSE_OBSERVATION,
}


def classify_restart(
    *,
    chain: VerifiedJournalChainV1,
    pending: int,
    effect: SyntheticEffectSnapshotV1,
    binding: JournalOperationBindingV1,
    profile: CutoverProfileV1,
    resume: object,
    recovery: object,
    epoch: int,
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    resume_valid = _resume_valid(resume, profile, binding, epoch)
    recovery_valid = _recovery_valid(
        recovery, profile, binding, epoch
    )
    if chain._pending_record is not None:
        return classify_pending(
            chain,
            resume_valid=resume_valid,
            recovery_valid=recovery_valid,
        )
    if chain._active_intent is not None:
        return _classify_open(
            chain, effect, resume_valid, recovery_valid
        )
    stable = _stable_observation(chain, effect)
    if effect.observation_fingerprint != stable:
        return _incident()
    return classify_closed(
        chain,
        pending=pending,
        resume_valid=resume_valid,
        recovery_valid=recovery_valid,
    )


def _classify_open(
    chain: VerifiedJournalChainV1,
    effect: SyntheticEffectSnapshotV1,
    resume_valid: bool,
    recovery_valid: bool,
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    intent = chain._active_intent
    current = effect.observation_fingerprint
    observed = active_observed_record(chain)
    if observed is not None:
        return _classify_observed_open(
            intent.direction,
            observed.effect_outcome,
            observed.observed_effect_fingerprint,
            current,
            resume_valid,
            recovery_valid,
        )
    if current not in {
        intent.before_observation_fingerprint,
        intent.expected_after_observation_fingerprint,
    }:
        return _incident()
    is_before = current == intent.before_observation_fingerprint
    if intent.direction == JournalDirection.REVERSE.value:
        if not recovery_valid:
            return _incident()
        phase = _OPEN_PHASES[(intent.direction, is_before)]
        return JournalOperationStatus.ROLLBACK_REQUIRED, phase
    if resume_valid:
        phase = _OPEN_PHASES[(intent.direction, is_before)]
        return JournalOperationStatus.RESUME_ALLOWED, phase
    if _active_effect_count(chain, current) and recovery_valid:
        phase = _OPEN_PHASES[(intent.direction, is_before)]
        return JournalOperationStatus.ROLLBACK_REQUIRED, phase
    if not _active_effect_count(chain, current):
        return (
            JournalOperationStatus.SAFE_ABORT,
            JournalOperationPhase.TERMINAL,
        )
    return _incident()


def _classify_observed_open(
    direction: str,
    outcome: str,
    observed: str,
    current: str,
    resume_valid: bool,
    recovery_valid: bool,
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    if current != observed:
        return _incident()
    if direction == JournalDirection.REVERSE.value:
        if recovery_valid:
            return (
                JournalOperationStatus.ROLLBACK_REQUIRED,
                JournalOperationPhase.REVERSE_OBSERVATION,
            )
        return _incident()
    if outcome == JournalEffectOutcome.NOT_APPLIED.value:
        if recovery_valid:
            return (
                JournalOperationStatus.ROLLBACK_REQUIRED,
                JournalOperationPhase.FORWARD_OBSERVATION,
            )
        return _incident()
    if resume_valid:
        return (
            JournalOperationStatus.RESUME_ALLOWED,
            JournalOperationPhase.FORWARD_OBSERVATION,
        )
    if recovery_valid:
        return (
            JournalOperationStatus.ROLLBACK_REQUIRED,
            JournalOperationPhase.FORWARD_OBSERVATION,
        )
    return _incident()


def _stable_observation(
    chain: VerifiedJournalChainV1,
    effect: SyntheticEffectSnapshotV1,
) -> str:
    applied = [
        intent
        for intent, outcome in zip(
            chain._forward_intents,
            chain._forward_outcomes,
            strict=True,
        )
        if outcome == JournalEffectOutcome.APPLIED.value
    ]
    if chain.reverse_committed:
        return applied[-chain.reverse_committed].before_observation_fingerprint
    if chain._forward_intents:
        intent = chain._forward_intents[-1]
        return (
            intent.expected_after_observation_fingerprint
            if chain._forward_outcomes[-1]
            == JournalEffectOutcome.APPLIED.value
            else intent.before_observation_fingerprint
        )
    return effect.initial_observation_fingerprint


def _resume_valid(
    authorization: object,
    profile: CutoverProfileV1,
    binding: JournalOperationBindingV1,
    epoch: object,
) -> bool:
    if type(authorization) is not CutoverExecutionAuthorizationV1:
        return False
    result = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation="cutover_execution",
        expected_operation_fingerprint=binding.operation_fingerprint,
        expected_phase="resume",
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=epoch,
    )
    return result.status is AuthorizationValidationStatus.AUTHORIZED


def _recovery_valid(
    authorization: object,
    profile: CutoverProfileV1,
    binding: JournalOperationBindingV1,
    epoch: object,
) -> bool:
    if (
        type(authorization) is not RecoveryAuthorizationV1
        or authorization.authorization_fingerprint
        != binding.recovery_authorization_fingerprint
    ):
        return False
    result = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation="recovery",
        expected_operation_fingerprint=binding.operation_fingerprint,
        expected_phase="rollback",
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=epoch,
    )
    return result.status is AuthorizationValidationStatus.AUTHORIZED


def _active_effect_count(
    chain: VerifiedJournalChainV1,
    observation: str,
) -> int:
    active = _applied_count(chain) - chain.reverse_committed
    intent = chain._active_intent
    if (
        intent.direction == JournalDirection.FORWARD.value
        and observation == intent.expected_after_observation_fingerprint
    ):
        active += 1
    return active


def _applied_count(chain: VerifiedJournalChainV1) -> int:
    return sum(
        outcome == JournalEffectOutcome.APPLIED.value
        for outcome in chain._forward_outcomes
    )


def _incident(
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    return (
        JournalOperationStatus.INCIDENT_STOP,
        JournalOperationPhase.CHAIN_VERIFICATION,
    )
