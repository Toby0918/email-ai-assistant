"""One-transition managed-unit progress over the authoritative journal."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_production_binding import ExecutionConfirmationClaimV1, ProductionCommandV2
from backend.r2_transaction_journal_v2 import EffectClassificationV2, R2TransactionJournalV2
from backend.r2_transaction_journal_v2._canonical import fingerprint, is_fingerprint
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2
from backend.r2_transaction_process.production_v2 import TransactionActionCompletionV2, transaction_action_fingerprint_v2

from .errors import ManagedUnitPublicationError
from .plan import R2ManagedUnitPlanV2, R2ManagedUnitTransitionV2
from .recovery import R2ManagedRecoveryInspectionV2


class ManagedProgressStatusV2(str, Enum):
    MANAGED_ACTION_PENDING = "MANAGED_ACTION_PENDING"
    MANAGED_ACTION_COMMITTED = "MANAGED_ACTION_COMMITTED"
    MANAGED_RECOVERY_CLASSIFIED = "MANAGED_RECOVERY_CLASSIFIED"
    MANAGED_RECOVERED_COMMIT = "MANAGED_RECOVERED_COMMIT"
    MANAGED_UNITS_COMPLETE = "MANAGED_UNITS_COMPLETE"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2ManagedUnitEffectObservationV2:
    binding_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    action_completion_fingerprint: str = field(repr=False)
    claim_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    observed_state_fingerprint: str = field(repr=False)
    identity_fingerprint: str = field(repr=False)
    byte_fingerprint: str = field(repr=False)
    acl_conformance_fingerprint: str = field(repr=False)
    semantic_conformance_fingerprint: str = field(repr=False)
    source_retained: bool
    partial_retained: bool
    failed_unit_retained: bool
    destructive_operations: int
    host_mutations: int
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2ManagedUnitEffectObservationV2 requires create()")

    @classmethod
    def create(cls, **values):
        try:
            expected = {
                "binding", "transition", "action_completion", "observed_state_fingerprint",
                "identity_fingerprint", "byte_fingerprint", "acl_conformance_fingerprint",
                "semantic_conformance_fingerprint", "source_retained", "partial_retained",
                "failed_unit_retained", "destructive_operations",
            }
            binding, transition, completion = values.get("binding"), values.get("transition"), values.get("action_completion")
            if set(values) != expected or type(transition) is not R2ManagedUnitTransitionV2 or type(completion) is not TransactionActionCompletionV2 or completion.binding_fingerprint != binding.binding_fingerprint or completion.transition_instance_fingerprint != transition.transition_instance_fingerprint or completion.mutations != 1 or values["observed_state_fingerprint"] != transition.post_state_fingerprint or not all(is_fingerprint(values[name]) for name in ("identity_fingerprint", "byte_fingerprint", "acl_conformance_fingerprint", "semantic_conformance_fingerprint")) or any(values[name] is not True for name in ("source_retained", "partial_retained", "failed_unit_retained")) or values["destructive_operations"] != 0:
                raise ManagedUnitPublicationError()
            body = {
                "binding_fingerprint": binding.binding_fingerprint,
                "transition_instance_fingerprint": transition.transition_instance_fingerprint,
                "action_completion_fingerprint": completion.completion_fingerprint,
                "claim_fingerprint": completion.claim_fingerprint,
                "prior_journal_head_fingerprint": completion.prior_journal_head_fingerprint,
                "observed_state_fingerprint": values["observed_state_fingerprint"],
                **{name: values[name] for name in ("identity_fingerprint", "byte_fingerprint", "acl_conformance_fingerprint", "semantic_conformance_fingerprint", "source_retained", "partial_retained", "failed_unit_retained", "destructive_operations")},
                "host_mutations": 1,
            }
            return _allocate(cls, body, "observation_fingerprint", "r2-managed-unit-effect-v2")
        except ManagedUnitPublicationError:
            raise
        except Exception:
            raise ManagedUnitPublicationError() from None


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ManagedProgressV2:
    status: ManagedProgressStatusV2
    journal: R2TransactionJournalV2 = field(repr=False)
    transition: R2ManagedUnitTransitionV2 = field(repr=False)
    classification: EffectClassificationV2 | None
    host_mutations: int
    journal_appends: int
    progress_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ManagedProgressV2 is returned by fixed progress functions")


def begin_next_managed_action_v2(*, journal, plan, claim, observed_at_epoch, observed_monotonic_ns):
    try:
        transition = _next(journal, plan)
        _require_claim(journal, plan, transition, claim, ProductionCommandV2.EXECUTE)
        result = journal.append_execution_confirmation_claim(claim=claim, transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_at_epoch=observed_at_epoch, observed_monotonic_ns=observed_monotonic_ns).append_intent(transition_instance_fingerprint=transition.transition_instance_fingerprint, pre_state_fingerprint=transition.pre_state_fingerprint, post_state_fingerprint=transition.post_state_fingerprint)
        return _progress(ManagedProgressStatusV2.MANAGED_ACTION_PENDING, result, transition, None, 0, 2)
    except ManagedUnitPublicationError:
        raise
    except Exception:
        raise ManagedUnitPublicationError() from None


def commit_managed_effect_v2(*, journal, plan, effect):
    try:
        transition = _pending(journal, plan)
        confirmation = journal.records[-2].execution_confirmation_claim
        if type(effect) is not R2ManagedUnitEffectObservationV2 or effect.transition_instance_fingerprint != transition.transition_instance_fingerprint or effect.claim_fingerprint != confirmation.claim_fingerprint or effect.prior_journal_head_fingerprint != confirmation.prior_journal_head_fingerprint or effect.observed_state_fingerprint != transition.post_state_fingerprint:
            raise ManagedUnitPublicationError()
        result = journal.append_effect_observation(transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_state_fingerprint=effect.observed_state_fingerprint, classification=EffectClassificationV2.EFFECT_PRESENT_EXACT).append_commit(transition_instance_fingerprint=transition.transition_instance_fingerprint, committed_state_fingerprint=effect.observed_state_fingerprint)
        status = ManagedProgressStatusV2.MANAGED_UNITS_COMPLETE if plan.committed_prefix_count(result) == 8 else ManagedProgressStatusV2.MANAGED_ACTION_COMMITTED
        return _progress(status, result, transition, EffectClassificationV2.EFFECT_PRESENT_EXACT, 1, 2)
    except ManagedUnitPublicationError:
        raise
    except Exception:
        raise ManagedUnitPublicationError() from None


def classify_managed_pending_v2(*, journal, plan, inspection):
    try:
        transition = _pending(journal, plan)
        if type(inspection) is not R2ManagedRecoveryInspectionV2 or inspection.binding_fingerprint != plan.binding_fingerprint or inspection.inspection.journal_head_fingerprint != journal.current_head_fingerprint or inspection.transition_instance_fingerprint != transition.transition_instance_fingerprint:
            raise ManagedUnitPublicationError()
        receipt = inspection.inspection
        result = journal.append_recovery_classification(transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_state_fingerprint=receipt.first_observation.observed_state_fingerprint, classification=receipt.classification, inspection_receipt_fingerprint=inspection.proof_fingerprint)
        status = ManagedProgressStatusV2.INCIDENT_STOP if receipt.classification is EffectClassificationV2.EFFECT_AMBIGUOUS else ManagedProgressStatusV2.MANAGED_RECOVERY_CLASSIFIED
        return _progress(status, result, transition, receipt.classification, 0, 1)
    except ManagedUnitPublicationError:
        raise
    except Exception:
        raise ManagedUnitPublicationError() from None


def resume_managed_transition_v2(*, journal, plan, claim, observed_at_epoch, observed_monotonic_ns):
    try:
        transition = _classified(journal, plan)
        classification = journal.records[-1].effect_classification
        if classification is EffectClassificationV2.EFFECT_AMBIGUOUS:
            raise ManagedUnitPublicationError()
        _require_claim(journal, plan, transition, claim, ProductionCommandV2.RESUME)
        result = journal.append_execution_confirmation_claim(claim=claim, transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_at_epoch=observed_at_epoch, observed_monotonic_ns=observed_monotonic_ns)
        if classification is EffectClassificationV2.EFFECT_ABSENT_EXACT:
            result = result.append_intent(transition_instance_fingerprint=transition.transition_instance_fingerprint, pre_state_fingerprint=transition.pre_state_fingerprint, post_state_fingerprint=transition.post_state_fingerprint)
            return _progress(ManagedProgressStatusV2.MANAGED_ACTION_PENDING, result, transition, classification, 0, 2)
        result = result.append_commit(transition_instance_fingerprint=transition.transition_instance_fingerprint, committed_state_fingerprint=transition.post_state_fingerprint)
        status = ManagedProgressStatusV2.MANAGED_UNITS_COMPLETE if plan.committed_prefix_count(result) == 8 else ManagedProgressStatusV2.MANAGED_RECOVERED_COMMIT
        return _progress(status, result, transition, classification, 0, 2)
    except ManagedUnitPublicationError:
        raise
    except Exception:
        raise ManagedUnitPublicationError() from None


def _require_claim(journal, plan, transition, claim, command):
    remaining = plan.remaining_plan_fingerprint(transition)
    if type(claim) is not ExecutionConfirmationClaimV1 or claim.command is not command or claim.prior_journal_head_fingerprint != journal.current_head_fingerprint or claim.transition_instance_fingerprint != transition.transition_instance_fingerprint or claim.remaining_reverse_plan_fingerprint != remaining:
        raise ManagedUnitPublicationError()
    expected = transaction_action_fingerprint_v2(plan._binding, command, journal_head_fingerprint=journal.current_head_fingerprint, transition_instance_fingerprint=transition.transition_instance_fingerprint, remaining_reverse_plan_fingerprint=remaining)
    if claim.action_fingerprint != expected:
        raise ManagedUnitPublicationError()


def _next(journal, plan):
    if type(plan) is not R2ManagedUnitPlanV2 or type(journal) is not R2TransactionJournalV2 or journal.next_legal_action not in {"CLAIM_FRESH_EXECUTION_CONFIRMATION", "CLAIM_FRESH_EXECUTION_CONFIRMATION_OR_TERMINAL"}:
        raise ManagedUnitPublicationError()
    transition = plan.next_transition(journal)
    if transition is None:
        raise ManagedUnitPublicationError()
    return transition


def _pending(journal, plan):
    if type(journal) is not R2TransactionJournalV2 or journal.next_legal_action != "READ_ONLY_INSPECTION":
        raise ManagedUnitPublicationError()
    transition = plan.next_transition(journal)
    if transition is None or journal.records[-1].transition_instance_fingerprint != transition.transition_instance_fingerprint:
        raise ManagedUnitPublicationError()
    return transition


def _classified(journal, plan):
    if type(journal) is not R2TransactionJournalV2 or not journal.records or journal.records[-1].record_type is not JournalRecordTypeV2.RECOVERY_CLASSIFICATION:
        raise ManagedUnitPublicationError()
    transition = plan.next_transition(journal)
    if transition is None or journal.records[-1].transition_instance_fingerprint != transition.transition_instance_fingerprint:
        raise ManagedUnitPublicationError()
    return transition


def _progress(status, journal, transition, classification, mutations, appends):
    body = {"status": status.value, "journal_head_fingerprint": journal.current_head_fingerprint, "transition_instance_fingerprint": transition.transition_instance_fingerprint, "classification": "" if classification is None else classification.value, "host_mutations": mutations, "journal_appends": appends}
    value = object.__new__(ManagedProgressV2)
    for name, item in {"status": status, "journal": journal, "transition": transition, "classification": classification, "host_mutations": mutations, "journal_appends": appends, "progress_fingerprint": fingerprint("r2-managed-progress-v2", body)}.items():
        object.__setattr__(value, name, item)
    return value


def _allocate(cls, body, fingerprint_name, domain):
    value = object.__new__(cls)
    for name, item in body.items():
        object.__setattr__(value, name, item)
    object.__setattr__(value, fingerprint_name, fingerprint(domain, body))
    return value
