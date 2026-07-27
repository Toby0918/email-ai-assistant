"""Classification for a verified journal with no open or pending record."""

from __future__ import annotations

from .journal_chain import VerifiedJournalChainV1
from .journal_types import FORWARD_STEP_ORDER, JournalEffectOutcome
from .recovery_types import (
    JournalOperationPhase,
    JournalOperationStatus,
)


def classify_closed(
    chain: VerifiedJournalChainV1,
    *,
    pending: int,
    resume_valid: bool,
    recovery_valid: bool,
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    complete = (
        chain.forward_committed == len(FORWARD_STEP_ORDER)
        and all(
            outcome == JournalEffectOutcome.APPLIED.value
            for outcome in chain._forward_outcomes
        )
        and chain.reverse_committed == 0
        and pending == 0
    )
    if complete:
        return (
            JournalOperationStatus.CUTOVER_SUCCEEDED,
            JournalOperationPhase.TERMINAL,
        )
    active = _applied_count(chain) - chain.reverse_committed
    terminal_no_effect = (
        bool(chain._forward_outcomes)
        and chain._forward_outcomes[-1]
        == JournalEffectOutcome.NOT_APPLIED.value
    )
    if terminal_no_effect:
        if active == 0:
            return _safe_abort()
        if recovery_valid:
            return _rollback()
        return _incident()
    if active == 0:
        return _safe_abort()
    if resume_valid and chain.reverse_committed == 0 and pending == 0:
        return (
            JournalOperationStatus.RESUME_ALLOWED,
            JournalOperationPhase.NEXT_FORWARD_INTENT,
        )
    if recovery_valid:
        return _rollback()
    return _incident()


def _applied_count(chain: VerifiedJournalChainV1) -> int:
    return sum(
        outcome == JournalEffectOutcome.APPLIED.value
        for outcome in chain._forward_outcomes
    )


def _safe_abort(
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    return (
        JournalOperationStatus.SAFE_ABORT,
        JournalOperationPhase.TERMINAL,
    )


def _rollback(
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    return (
        JournalOperationStatus.ROLLBACK_REQUIRED,
        JournalOperationPhase.REVERSE_ACTION,
    )


def _incident(
) -> tuple[JournalOperationStatus, JournalOperationPhase]:
    return (
        JournalOperationStatus.INCIDENT_STOP,
        JournalOperationPhase.CHAIN_VERIFICATION,
    )
