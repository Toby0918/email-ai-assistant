"""One-transition foundation progress over the authoritative journal."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_production_binding import ExecutionConfirmationClaimV1, ProductionCommandV2
from backend.r2_transaction_journal_v2 import (
    EffectClassificationV2,
    R2ReadOnlyInspectionReceiptV2,
    R2TransactionJournalV2,
)
from backend.r2_transaction_journal_v2._canonical import fingerprint, is_fingerprint
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2
from backend.r2_transaction_process.production_v2 import (
    TransactionActionCompletionV2,
    transaction_action_fingerprint_v2,
)

from .errors import FoundationPublicationError
from .plan import R2FoundationPlanV2, R2FoundationTransitionV2


class FoundationProgressStatusV2(str, Enum):
    FOUNDATION_ACTION_PENDING = "FOUNDATION_ACTION_PENDING"
    FOUNDATION_ACTION_COMMITTED = "FOUNDATION_ACTION_COMMITTED"
    FOUNDATION_RECOVERY_CLASSIFIED = "FOUNDATION_RECOVERY_CLASSIFIED"
    FOUNDATION_RECOVERED_COMMIT = "FOUNDATION_RECOVERED_COMMIT"
    FOUNDATION_COMPLETE = "FOUNDATION_COMPLETE"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2FoundationEffectObservationV2:
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    action_completion_fingerprint: str = field(repr=False)
    claim_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    remaining_plan_fingerprint: str = field(repr=False)
    observed_state_fingerprint: str = field(repr=False)
    identity_fingerprint: str = field(repr=False)
    byte_fingerprint: str = field(repr=False)
    host_mutations: int
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2FoundationEffectObservationV2 requires create()")

    @classmethod
    def create(cls, *, binding, transition, action_completion, observed_state_fingerprint, identity_fingerprint, byte_fingerprint):
        try:
            if type(transition) is not R2FoundationTransitionV2 or type(action_completion) is not TransactionActionCompletionV2 or action_completion.binding_fingerprint != binding.binding_fingerprint or action_completion.transition_instance_fingerprint != transition.transition_instance_fingerprint or action_completion.mutations != 1 or observed_state_fingerprint != transition.post_state_fingerprint or not is_fingerprint(identity_fingerprint) or not is_fingerprint(byte_fingerprint):
                raise FoundationPublicationError()
            body = {
                "binding_fingerprint": binding.binding_fingerprint,
                "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
                "transition_instance_fingerprint": transition.transition_instance_fingerprint,
                "action_completion_fingerprint": action_completion.completion_fingerprint,
                "claim_fingerprint": action_completion.claim_fingerprint,
                "prior_journal_head_fingerprint": action_completion.prior_journal_head_fingerprint,
                "remaining_plan_fingerprint": action_completion.remaining_reverse_plan_fingerprint,
                "observed_state_fingerprint": observed_state_fingerprint,
                "identity_fingerprint": identity_fingerprint,
                "byte_fingerprint": byte_fingerprint,
                "host_mutations": 1,
            }
            return _allocate(cls, body, "observation_fingerprint", "r2-foundation-effect-v2")
        except FoundationPublicationError:
            raise
        except Exception:
            raise FoundationPublicationError() from None


@dataclass(frozen=True, slots=True, init=False, repr=False)
class FoundationProgressV2:
    status: FoundationProgressStatusV2
    journal: R2TransactionJournalV2 = field(repr=False)
    transition: R2FoundationTransitionV2 = field(repr=False)
    classification: EffectClassificationV2 | None
    host_mutations: int
    journal_appends: int
    progress_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("FoundationProgressV2 is returned by fixed progress functions")


def begin_next_foundation_action_v2(*, journal, plan, claim, observed_at_epoch, observed_monotonic_ns):
    try:
        transition = _next(journal, plan)
        _require_claim(journal, plan, transition, claim, (ProductionCommandV2.EXECUTE,))
        result = journal.append_execution_confirmation_claim(
            claim=claim,
            transition_instance_fingerprint=transition.transition_instance_fingerprint,
            observed_at_epoch=observed_at_epoch,
            observed_monotonic_ns=observed_monotonic_ns,
        ).append_intent(
            transition_instance_fingerprint=transition.transition_instance_fingerprint,
            pre_state_fingerprint=transition.pre_state_fingerprint,
            post_state_fingerprint=transition.post_state_fingerprint,
        )
        return _progress(FoundationProgressStatusV2.FOUNDATION_ACTION_PENDING, result, transition, None, 0, 2)
    except FoundationPublicationError:
        raise
    except Exception:
        raise FoundationPublicationError() from None


def commit_foundation_effect_v2(*, journal, plan, effect):
    try:
        transition = _pending(journal, plan)
        confirmation = journal.records[-2].execution_confirmation_claim
        expected_plan = plan.remaining_plan_fingerprint(transition)
        if type(effect) is not R2FoundationEffectObservationV2 or effect.transition_instance_fingerprint != transition.transition_instance_fingerprint or effect.claim_fingerprint != confirmation.claim_fingerprint or effect.prior_journal_head_fingerprint != confirmation.prior_journal_head_fingerprint or effect.remaining_plan_fingerprint != expected_plan or effect.observed_state_fingerprint != transition.post_state_fingerprint:
            raise FoundationPublicationError()
        result = journal.append_effect_observation(
            transition_instance_fingerprint=transition.transition_instance_fingerprint,
            observed_state_fingerprint=effect.observed_state_fingerprint,
            classification=EffectClassificationV2.EFFECT_PRESENT_EXACT,
        ).append_commit(
            transition_instance_fingerprint=transition.transition_instance_fingerprint,
            committed_state_fingerprint=effect.observed_state_fingerprint,
        )
        status = FoundationProgressStatusV2.FOUNDATION_COMPLETE if plan.committed_prefix_count(result) == 17 else FoundationProgressStatusV2.FOUNDATION_ACTION_COMMITTED
        return _progress(status, result, transition, EffectClassificationV2.EFFECT_PRESENT_EXACT, 1, 2)
    except FoundationPublicationError:
        raise
    except Exception:
        raise FoundationPublicationError() from None


def classify_foundation_pending_v2(*, journal, plan, inspection):
    try:
        transition = _pending(journal, plan)
        if type(inspection) is not R2ReadOnlyInspectionReceiptV2 or inspection.binding_fingerprint != plan.binding_fingerprint or inspection.journal_head_fingerprint != journal.current_head_fingerprint or inspection.transition_instance_fingerprint != transition.transition_instance_fingerprint:
            raise FoundationPublicationError()
        result = journal.append_recovery_classification(
            transition_instance_fingerprint=transition.transition_instance_fingerprint,
            observed_state_fingerprint=inspection.first_observation.observed_state_fingerprint,
            classification=inspection.classification,
            inspection_receipt_fingerprint=inspection.receipt_fingerprint,
        )
        status = FoundationProgressStatusV2.INCIDENT_STOP if inspection.classification is EffectClassificationV2.EFFECT_AMBIGUOUS else FoundationProgressStatusV2.FOUNDATION_RECOVERY_CLASSIFIED
        return _progress(status, result, transition, inspection.classification, 0, 1)
    except FoundationPublicationError:
        raise
    except Exception:
        raise FoundationPublicationError() from None


def resume_foundation_transition_v2(*, journal, plan, claim, observed_at_epoch, observed_monotonic_ns):
    try:
        transition = _classified(journal, plan)
        classification = journal.records[-1].effect_classification
        if classification is EffectClassificationV2.EFFECT_AMBIGUOUS:
            raise FoundationPublicationError()
        _require_claim(journal, plan, transition, claim, (ProductionCommandV2.RESUME,))
        result = journal.append_execution_confirmation_claim(
            claim=claim,
            transition_instance_fingerprint=transition.transition_instance_fingerprint,
            observed_at_epoch=observed_at_epoch,
            observed_monotonic_ns=observed_monotonic_ns,
        )
        if classification is EffectClassificationV2.EFFECT_ABSENT_EXACT:
            result = result.append_intent(
                transition_instance_fingerprint=transition.transition_instance_fingerprint,
                pre_state_fingerprint=transition.pre_state_fingerprint,
                post_state_fingerprint=transition.post_state_fingerprint,
            )
            return _progress(FoundationProgressStatusV2.FOUNDATION_ACTION_PENDING, result, transition, classification, 0, 2)
        result = result.append_commit(
            transition_instance_fingerprint=transition.transition_instance_fingerprint,
            committed_state_fingerprint=transition.post_state_fingerprint,
        )
        status = FoundationProgressStatusV2.FOUNDATION_COMPLETE if plan.committed_prefix_count(result) == 17 else FoundationProgressStatusV2.FOUNDATION_RECOVERED_COMMIT
        return _progress(status, result, transition, classification, 0, 2)
    except FoundationPublicationError:
        raise
    except Exception:
        raise FoundationPublicationError() from None


def _require_claim(journal, plan, transition, claim, commands):
    remaining = plan.remaining_plan_fingerprint(transition)
    if type(claim) is not ExecutionConfirmationClaimV1 or claim.command not in commands or claim.prior_journal_head_fingerprint != journal.current_head_fingerprint or claim.transition_instance_fingerprint != transition.transition_instance_fingerprint or claim.remaining_reverse_plan_fingerprint != remaining:
        raise FoundationPublicationError()
    expected = transaction_action_fingerprint_v2(
        plan._binding,
        claim.command,
        journal_head_fingerprint=journal.current_head_fingerprint,
        transition_instance_fingerprint=transition.transition_instance_fingerprint,
        remaining_reverse_plan_fingerprint=remaining,
    )
    if claim.action_fingerprint != expected:
        raise FoundationPublicationError()


def _next(journal, plan):
    if type(plan) is not R2FoundationPlanV2 or type(journal) is not R2TransactionJournalV2 or journal.next_legal_action not in {"CLAIM_FRESH_EXECUTION_CONFIRMATION", "CLAIM_FRESH_EXECUTION_CONFIRMATION_OR_TERMINAL"}:
        raise FoundationPublicationError()
    transition = plan.next_transition(journal)
    if transition is None:
        raise FoundationPublicationError()
    return transition


def _pending(journal, plan):
    if type(journal) is not R2TransactionJournalV2 or journal.next_legal_action != "READ_ONLY_INSPECTION":
        raise FoundationPublicationError()
    transition = plan.next_transition(journal)
    if transition is None or journal.records[-1].transition_instance_fingerprint != transition.transition_instance_fingerprint:
        raise FoundationPublicationError()
    return transition


def _classified(journal, plan):
    if type(journal) is not R2TransactionJournalV2 or not journal.records or journal.records[-1].record_type is not JournalRecordTypeV2.RECOVERY_CLASSIFICATION:
        raise FoundationPublicationError()
    transition = plan.next_transition(journal)
    if transition is None or journal.records[-1].transition_instance_fingerprint != transition.transition_instance_fingerprint:
        raise FoundationPublicationError()
    return transition


def _progress(status, journal, transition, classification, mutations, appends):
    body = {
        "status": status.value,
        "journal_head_fingerprint": journal.current_head_fingerprint,
        "transition_instance_fingerprint": transition.transition_instance_fingerprint,
        "classification": "" if classification is None else classification.value,
        "host_mutations": mutations,
        "journal_appends": appends,
    }
    value = object.__new__(FoundationProgressV2)
    for name, item in {
        "status": status, "journal": journal, "transition": transition,
        "classification": classification, "host_mutations": mutations,
        "journal_appends": appends,
        "progress_fingerprint": fingerprint("r2-foundation-progress-v2", body),
    }.items():
        object.__setattr__(value, name, item)
    return value


def _allocate(cls, body, fingerprint_name, domain):
    value = object.__new__(cls)
    for name, item in body.items():
        object.__setattr__(value, name, item)
    object.__setattr__(value, fingerprint_name, fingerprint(domain, body))
    return value
