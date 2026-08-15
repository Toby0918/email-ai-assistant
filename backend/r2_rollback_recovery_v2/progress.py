"""One reverse boundary at a time over the unified journal."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_production_binding import ExecutionConfirmationClaimV1, ProductionCommandV2
from backend.r2_transaction_journal_v2 import (
    EffectClassificationV2,
    R2ReadOnlyInspectionReceiptV2,
    R2TransactionJournalV2,
)
from backend.r2_transaction_journal_v2._canonical import fingerprint
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2
from backend.r2_transaction_process.production_v2 import transaction_action_fingerprint_v2

from .errors import RollbackRecoveryError
from .evidence import R2RollbackEffectEvidenceV2
from .plan import R2RollbackPlanV2


class RollbackProgressStatusV2(str, Enum):
    ROLLBACK_ACTION_PENDING = "ROLLBACK_ACTION_PENDING"
    ROLLBACK_ACTION_COMMITTED = "ROLLBACK_ACTION_COMMITTED"
    ROLLBACK_RECOVERY_CLASSIFIED = "ROLLBACK_RECOVERY_CLASSIFIED"
    ROLLBACK_RECOVERED_COMMIT = "ROLLBACK_RECOVERED_COMMIT"
    ROLLBACK_ACTIONS_COMPLETE = "ROLLBACK_ACTIONS_COMPLETE"
    LEGACY_FLAT_LAYOUT_RESTORED = "LEGACY_FLAT_LAYOUT_RESTORED"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RollbackProgressV2:
    status: RollbackProgressStatusV2
    journal: R2TransactionJournalV2 = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    classification: EffectClassificationV2 | None
    host_mutations: int
    journal_appends: int
    progress_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("RollbackProgressV2 is returned by fixed progress functions")


def begin_next_rollback_action_v2(*, journal, plan, claim, observed_at_epoch, observed_monotonic_ns):
    try:
        transition = _next(journal, plan)
        _require_claim(journal, plan, transition, claim)
        result = journal.append_execution_confirmation_claim(claim=claim, transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_at_epoch=observed_at_epoch, observed_monotonic_ns=observed_monotonic_ns).append_intent(transition_instance_fingerprint=transition.transition_instance_fingerprint, pre_state_fingerprint=transition.pre_state_fingerprint, post_state_fingerprint=transition.post_state_fingerprint)
        return _progress(RollbackProgressStatusV2.ROLLBACK_ACTION_PENDING, result, transition.transition_instance_fingerprint, None, 0, 2)
    except RollbackRecoveryError:
        raise
    except Exception:
        raise RollbackRecoveryError() from None


def commit_rollback_effect_v2(*, journal, plan, evidence):
    try:
        transition = _pending(journal, plan)
        confirmation = journal.records[-2].execution_confirmation_claim
        if type(evidence) is not R2RollbackEffectEvidenceV2 or evidence.transition_instance_fingerprint != transition.transition_instance_fingerprint or evidence.claim_fingerprint != confirmation.claim_fingerprint or evidence.prior_journal_head_fingerprint != confirmation.prior_journal_head_fingerprint or evidence.remaining_plan_fingerprint != transition.remaining_plan_fingerprint:
            raise RollbackRecoveryError()
        result = journal.append_effect_observation(transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_state_fingerprint=evidence.observed_state_fingerprint, classification=EffectClassificationV2.EFFECT_PRESENT_EXACT).append_commit(transition_instance_fingerprint=transition.transition_instance_fingerprint, committed_state_fingerprint=evidence.observed_state_fingerprint)
        status = RollbackProgressStatusV2.ROLLBACK_ACTIONS_COMPLETE if plan.completed_prefix_count(result) == plan.transition_count else RollbackProgressStatusV2.ROLLBACK_ACTION_COMMITTED
        return _progress(status, result, transition.transition_instance_fingerprint, EffectClassificationV2.EFFECT_PRESENT_EXACT, 1, 2)
    except RollbackRecoveryError:
        raise
    except Exception:
        raise RollbackRecoveryError() from None


def classify_rollback_pending_v2(*, journal, plan, inspection):
    try:
        transition = _pending(journal, plan)
        if type(inspection) is not R2ReadOnlyInspectionReceiptV2 or inspection.binding_fingerprint != plan.binding_fingerprint or inspection.journal_head_fingerprint != journal.current_head_fingerprint or inspection.transition_instance_fingerprint != transition.transition_instance_fingerprint:
            raise RollbackRecoveryError()
        result = journal.append_recovery_classification(transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_state_fingerprint=inspection.first_observation.observed_state_fingerprint, classification=inspection.classification, inspection_receipt_fingerprint=inspection.receipt_fingerprint)
        status = RollbackProgressStatusV2.INCIDENT_STOP if inspection.classification is EffectClassificationV2.EFFECT_AMBIGUOUS else RollbackProgressStatusV2.ROLLBACK_RECOVERY_CLASSIFIED
        return _progress(status, result, transition.transition_instance_fingerprint, inspection.classification, 0, 1)
    except RollbackRecoveryError:
        raise
    except Exception:
        raise RollbackRecoveryError() from None


def resume_rollback_transition_v2(*, journal, plan, claim, observed_at_epoch, observed_monotonic_ns):
    try:
        transition = _classified(journal, plan)
        classification = journal.records[-1].effect_classification
        recovery_evidence = journal.records[-1].inspection_receipt_fingerprint
        if classification is EffectClassificationV2.EFFECT_AMBIGUOUS:
            raise RollbackRecoveryError()
        _require_claim(journal, plan, transition, claim)
        result = journal.append_execution_confirmation_claim(claim=claim, transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_at_epoch=observed_at_epoch, observed_monotonic_ns=observed_monotonic_ns)
        if classification is EffectClassificationV2.EFFECT_ABSENT_EXACT:
            result = result.append_intent(transition_instance_fingerprint=transition.transition_instance_fingerprint, pre_state_fingerprint=transition.pre_state_fingerprint, post_state_fingerprint=transition.post_state_fingerprint)
            return _progress(RollbackProgressStatusV2.ROLLBACK_ACTION_PENDING, result, transition.transition_instance_fingerprint, classification, 0, 2)
        result = result.append_commit(transition_instance_fingerprint=transition.transition_instance_fingerprint, committed_state_fingerprint=transition.post_state_fingerprint, evidence_receipt_fingerprint=recovery_evidence)
        status = RollbackProgressStatusV2.ROLLBACK_ACTIONS_COMPLETE if plan.completed_prefix_count(result) == plan.transition_count else RollbackProgressStatusV2.ROLLBACK_RECOVERED_COMMIT
        return _progress(status, result, transition.transition_instance_fingerprint, classification, 0, 2)
    except RollbackRecoveryError:
        raise
    except Exception:
        raise RollbackRecoveryError() from None


def _require_claim(journal, plan, transition, claim):
    expected = transaction_action_fingerprint_v2(plan._binding, ProductionCommandV2.ROLLBACK, journal_head_fingerprint=journal.current_head_fingerprint, transition_instance_fingerprint=transition.transition_instance_fingerprint, remaining_reverse_plan_fingerprint=transition.remaining_plan_fingerprint)
    if type(claim) is not ExecutionConfirmationClaimV1 or claim.command is not ProductionCommandV2.ROLLBACK or claim.prior_journal_head_fingerprint != journal.current_head_fingerprint or claim.transition_instance_fingerprint != transition.transition_instance_fingerprint or claim.remaining_reverse_plan_fingerprint != transition.remaining_plan_fingerprint or claim.action_fingerprint != expected:
        raise RollbackRecoveryError()


def _next(journal, plan):
    if type(plan) is not R2RollbackPlanV2 or type(journal) is not R2TransactionJournalV2 or not _rollback_start_allowed(journal):
        raise RollbackRecoveryError()
    transition = plan.next_transition(journal)
    if transition is None:
        raise RollbackRecoveryError()
    return transition


def _rollback_start_allowed(journal):
    if journal.next_legal_action not in {"CLAIM_FRESH_EXECUTION_CONFIRMATION", "CLAIM_FRESH_EXECUTION_CONFIRMATION_OR_TERMINAL"} or not journal.records:
        return False
    last = journal.records[-1]
    return last.record_type is JournalRecordTypeV2.COMMIT or (
        last.record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION
        and last.effect_classification is EffectClassificationV2.EFFECT_ABSENT_EXACT
    )


def _pending(journal, plan):
    if type(plan) is not R2RollbackPlanV2 or type(journal) is not R2TransactionJournalV2 or journal.next_legal_action != "READ_ONLY_INSPECTION":
        raise RollbackRecoveryError()
    transition = plan.next_transition(journal)
    if transition is None or journal.records[-1].transition_instance_fingerprint != transition.transition_instance_fingerprint:
        raise RollbackRecoveryError()
    return transition


def _classified(journal, plan):
    if type(plan) is not R2RollbackPlanV2 or type(journal) is not R2TransactionJournalV2 or not journal.records or journal.records[-1].record_type is not JournalRecordTypeV2.RECOVERY_CLASSIFICATION:
        raise RollbackRecoveryError()
    transition = plan.next_transition(journal)
    if transition is None or journal.records[-1].transition_instance_fingerprint != transition.transition_instance_fingerprint:
        raise RollbackRecoveryError()
    return transition


def _progress(status, journal, transition, classification, mutations, appends):
    body = {"status": status.value, "journal_head_fingerprint": journal.current_head_fingerprint, "transition_instance_fingerprint": transition, "classification": "" if classification is None else classification.value, "host_mutations": mutations, "journal_appends": appends}
    value = object.__new__(RollbackProgressV2)
    for name, item in {"status": status, "journal": journal, "transition_instance_fingerprint": transition, "classification": classification, "host_mutations": mutations, "journal_appends": appends, "progress_fingerprint": fingerprint("r2-rollback-progress-v2", body)}.items():
        object.__setattr__(value, name, item)
    return value
