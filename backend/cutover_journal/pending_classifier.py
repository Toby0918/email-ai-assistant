"""Classification for one verified but not yet published record."""

from __future__ import annotations

from .journal_chain import (
    VerifiedJournalChainV1,
    active_observed_record,
)
from .journal_types import (
    JournalDirection,
    JournalEffectOutcome,
    JournalEventCode,
)
from .recovery_types import (
    JournalOperationPhase,
    JournalOperationStatus,
)


def classify_pending(
    chain: VerifiedJournalChainV1,
    *,
    resume_valid: bool,
    recovery_valid: bool,
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    record = chain._pending_record
    if record.direction == JournalDirection.REVERSE.value:
        phase = (
            JournalOperationPhase.PENDING_INTENT_PUBLICATION
            if record.event_code == JournalEventCode.INTENT.value
            else JournalOperationPhase.REVERSE_OBSERVATION
        )
        if recovery_valid:
            return JournalOperationStatus.ROLLBACK_REQUIRED, phase
        return _incident()
    return _classify_forward(
        chain,
        resume_valid=resume_valid,
        recovery_valid=recovery_valid,
    )


def _classify_forward(
    chain: VerifiedJournalChainV1,
    *,
    resume_valid: bool,
    recovery_valid: bool,
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    record = chain._pending_record
    if record.event_code == JournalEventCode.INTENT.value:
        if resume_valid:
            return (
                JournalOperationStatus.RESUME_ALLOWED,
                JournalOperationPhase.PENDING_INTENT_PUBLICATION,
            )
        active = sum(
            outcome == JournalEffectOutcome.APPLIED.value
            for outcome in chain._forward_outcomes
        ) - chain.reverse_committed
        if active and recovery_valid:
            return (
                JournalOperationStatus.ROLLBACK_REQUIRED,
                JournalOperationPhase.PENDING_INTENT_PUBLICATION,
            )
        return (
            JournalOperationStatus.SAFE_ABORT,
            JournalOperationPhase.TERMINAL,
        ) if not active else _incident()
    return _classify_forward_followup(
        chain,
        resume_valid=resume_valid,
        recovery_valid=recovery_valid,
    )


def _classify_forward_followup(
    chain: VerifiedJournalChainV1,
    *,
    resume_valid: bool,
    recovery_valid: bool,
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    record = chain._pending_record
    phase = (
        JournalOperationPhase.AUTHORIZATION
        if record.event_code == JournalEventCode.RESUME_BOUND.value
        else JournalOperationPhase.FORWARD_OBSERVATION
    )
    observed = active_observed_record(chain)
    if (
        record.event_code == JournalEventCode.RESUME_BOUND.value
        and observed is not None
        and observed.effect_outcome
        == JournalEffectOutcome.NOT_APPLIED.value
    ):
        return (
            (JournalOperationStatus.ROLLBACK_REQUIRED, phase)
            if recovery_valid
            else _incident()
        )
    if record.effect_outcome == JournalEffectOutcome.NOT_APPLIED.value:
        return (
            (JournalOperationStatus.ROLLBACK_REQUIRED, phase)
            if recovery_valid
            else _incident()
        )
    if resume_valid:
        return JournalOperationStatus.RESUME_ALLOWED, phase
    if recovery_valid:
        return JournalOperationStatus.ROLLBACK_REQUIRED, phase
    return _incident()


def _incident(
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    return (
        JournalOperationStatus.INCIDENT_STOP,
        JournalOperationPhase.CHAIN_VERIFICATION,
    )
