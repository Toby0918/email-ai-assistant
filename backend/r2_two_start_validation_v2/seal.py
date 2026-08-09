"""Fresh-audit evidence and the unique forward terminal append."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import ExecutionConfirmationClaimV1, ProductionCommandV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2, TerminalStateV2
from backend.r2_transaction_journal_v2._canonical import fingerprint, is_fingerprint

from .errors import TwoStartValidationError
from .evidence import R2TwoStartValidationReceiptV2
from .plan import R2TwoStartValidationPlanV2, lifecycle_action_fingerprint_v2
from .progress import ValidationProgressStatusV2, _progress


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2FinalSealObservationV2:
    binding_fingerprint: str = field(repr=False)
    validation_receipt_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    observed_at_epoch: int
    final_state_fingerprint: str = field(repr=False)
    minimal_read_count: int
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2FinalSealObservationV2 requires create()")

    @classmethod
    def create(cls, *, binding, validation, journal, observed_at_epoch, final_state_fingerprint, minimal_read_count):
        try:
            if type(validation) is not R2TwoStartValidationReceiptV2 or type(journal) is not R2TransactionJournalV2 or validation.binding_fingerprint != binding.binding_fingerprint or validation.journal_head_fingerprint != journal.current_head_fingerprint or type(observed_at_epoch) is not int or not is_fingerprint(final_state_fingerprint) or minimal_read_count != 2 or not validation.stopped_audit_observed_at_epoch <= observed_at_epoch < validation.stopped_audit_expires_at_epoch or not validation.final_audit_observed_at_epoch <= observed_at_epoch < validation.final_audit_expires_at_epoch:
                raise TwoStartValidationError()
            body = {"binding_fingerprint": binding.binding_fingerprint, "validation_receipt_fingerprint": validation.receipt_fingerprint, "journal_head_fingerprint": journal.current_head_fingerprint, "observed_at_epoch": observed_at_epoch, "final_state_fingerprint": final_state_fingerprint, "minimal_read_count": 2}
            value = object.__new__(cls)
            for name, item in body.items(): object.__setattr__(value, name, item)
            object.__setattr__(value, "observation_fingerprint", fingerprint("r2-final-seal-observation-v2", body))
            return value
        except TwoStartValidationError:
            raise
        except Exception:
            raise TwoStartValidationError() from None


def seal_cutover_success_v2(*, journal, plan, validation, observation, claim, observed_at_epoch, observed_monotonic_ns):
    try:
        if type(journal) is not R2TransactionJournalV2 or type(plan) is not R2TwoStartValidationPlanV2 or type(validation) is not R2TwoStartValidationReceiptV2 or type(observation) is not R2FinalSealObservationV2 or plan.committed_prefix_count(journal) != 7 or journal.next_legal_action != "CLAIM_FRESH_EXECUTION_CONFIRMATION_OR_TERMINAL" or validation.journal_head_fingerprint != journal.current_head_fingerprint or observation.validation_receipt_fingerprint != validation.receipt_fingerprint or observation.journal_head_fingerprint != journal.current_head_fingerprint:
            raise TwoStartValidationError()
        transition = plan.terminal_transition_instance_fingerprint
        expected = lifecycle_action_fingerprint_v2(binding=plan._binding, plan=plan, command=ProductionCommandV2.RESUME, journal_head_fingerprint=journal.current_head_fingerprint, transition_instance_fingerprint=transition)
        if type(claim) is not ExecutionConfirmationClaimV1 or claim.command is not ProductionCommandV2.RESUME or claim.prior_journal_head_fingerprint != journal.current_head_fingerprint or claim.transition_instance_fingerprint != transition or claim.remaining_reverse_plan_fingerprint != "0" * 64 or claim.action_fingerprint != expected:
            raise TwoStartValidationError()
        result = journal.append_execution_confirmation_claim(claim=claim, transition_instance_fingerprint=transition, observed_at_epoch=observed_at_epoch, observed_monotonic_ns=observed_monotonic_ns).append_terminal_state(transition_instance_fingerprint=transition, final_state_fingerprint=observation.final_state_fingerprint, terminal_state=TerminalStateV2.CUTOVER_SUCCESS, terminal_evidence_fingerprint=observation.observation_fingerprint)
        return _progress(ValidationProgressStatusV2.CUTOVER_SUCCESS, result, 0, 2)
    except TwoStartValidationError:
        raise
    except Exception:
        raise TwoStartValidationError() from None
