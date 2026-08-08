"""Journal progress for one validation action at a time."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_production_binding import ExecutionConfirmationClaimV1
from backend.r2_transaction_journal_v2 import EffectClassificationV2, R2TransactionJournalV2
from backend.r2_transaction_journal_v2._canonical import fingerprint

from .errors import TwoStartValidationError
from .evidence import R2ValidationActionEvidenceV2
from .plan import R2TwoStartValidationPlanV2, lifecycle_action_fingerprint_v2


class ValidationProgressStatusV2(str, Enum):
    VALIDATION_ACTION_PENDING = "VALIDATION_ACTION_PENDING"
    VALIDATION_ACTION_COMMITTED = "VALIDATION_ACTION_COMMITTED"
    VALIDATION_ACTIONS_COMPLETE = "VALIDATION_ACTIONS_COMPLETE"
    CUTOVER_SUCCESS = "CUTOVER_SUCCESS"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ValidationProgressV2:
    status: ValidationProgressStatusV2
    journal: R2TransactionJournalV2 = field(repr=False)
    host_mutations: int
    journal_appends: int
    progress_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ValidationProgressV2 is returned by fixed progress functions")


def begin_next_validation_action_v2(*, journal, plan, claim, observed_at_epoch, observed_monotonic_ns):
    try:
        if type(plan) is not R2TwoStartValidationPlanV2 or type(journal) is not R2TransactionJournalV2 or journal.next_legal_action not in {"CLAIM_FRESH_EXECUTION_CONFIRMATION", "CLAIM_FRESH_EXECUTION_CONFIRMATION_OR_TERMINAL"}:
            raise TwoStartValidationError()
        transition = plan.next_transition(journal)
        if transition is None:
            raise TwoStartValidationError()
        _claim(journal, plan, claim, transition.command, transition.transition_instance_fingerprint)
        result = journal.append_execution_confirmation_claim(claim=claim, transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_at_epoch=observed_at_epoch, observed_monotonic_ns=observed_monotonic_ns).append_intent(transition_instance_fingerprint=transition.transition_instance_fingerprint, pre_state_fingerprint=transition.pre_state_fingerprint, post_state_fingerprint=transition.post_state_fingerprint)
        return _progress(ValidationProgressStatusV2.VALIDATION_ACTION_PENDING, result, 0, 2)
    except TwoStartValidationError:
        raise
    except Exception:
        raise TwoStartValidationError() from None


def commit_validation_action_v2(*, journal, plan, evidence):
    try:
        if type(plan) is not R2TwoStartValidationPlanV2 or type(journal) is not R2TransactionJournalV2 or journal.next_legal_action != "READ_ONLY_INSPECTION":
            raise TwoStartValidationError()
        transition = plan.next_transition(journal)
        confirmation = journal.records[-2].execution_confirmation_claim
        if type(evidence) is not R2ValidationActionEvidenceV2 or transition is None or evidence.transition_instance_fingerprint != transition.transition_instance_fingerprint or evidence.claim_fingerprint != confirmation.claim_fingerprint or evidence.prior_journal_head_fingerprint != confirmation.prior_journal_head_fingerprint:
            raise TwoStartValidationError()
        result = journal.append_effect_observation(transition_instance_fingerprint=transition.transition_instance_fingerprint, observed_state_fingerprint=evidence.observed_state_fingerprint, classification=EffectClassificationV2.EFFECT_PRESENT_EXACT).append_commit(transition_instance_fingerprint=transition.transition_instance_fingerprint, committed_state_fingerprint=evidence.observed_state_fingerprint)
        status = ValidationProgressStatusV2.VALIDATION_ACTIONS_COMPLETE if plan.committed_prefix_count(result) == 7 else ValidationProgressStatusV2.VALIDATION_ACTION_COMMITTED
        return _progress(status, result, evidence.host_mutations, 2)
    except TwoStartValidationError:
        raise
    except Exception:
        raise TwoStartValidationError() from None


def _claim(journal, plan, claim, command, transition):
    if type(claim) is not ExecutionConfirmationClaimV1 or claim.command is not command or claim.prior_journal_head_fingerprint != journal.current_head_fingerprint or claim.transition_instance_fingerprint != transition or claim.remaining_reverse_plan_fingerprint != "0" * 64 or claim.action_fingerprint != lifecycle_action_fingerprint_v2(binding=plan._binding, plan=plan, command=command, journal_head_fingerprint=journal.current_head_fingerprint, transition_instance_fingerprint=transition):
        raise TwoStartValidationError()


def _progress(status, journal, mutations, appends):
    body = {"status": status.value, "journal_head_fingerprint": journal.current_head_fingerprint, "host_mutations": mutations, "journal_appends": appends}
    value = object.__new__(ValidationProgressV2)
    for name, item in {"status": status, "journal": journal, "host_mutations": mutations, "journal_appends": appends, "progress_fingerprint": fingerprint("r2-validation-progress-v2", body)}.items(): object.__setattr__(value, name, item)
    return value
