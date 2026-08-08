"""Unique terminal append after exact legacy restoration evidence."""

from backend.r2_production_binding import ExecutionConfirmationClaimV1, ProductionCommandV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2, TerminalStateV2
from backend.r2_transaction_process.production_v2 import transaction_action_fingerprint_v2

from .errors import RollbackRecoveryError
from .evidence import R2LegacyRestorationEvidenceV2
from .plan import R2RollbackPlanV2
from .progress import RollbackProgressStatusV2, _progress


def seal_legacy_flat_layout_restored_v2(*, journal, plan, evidence, claim, observed_at_epoch, observed_monotonic_ns):
    try:
        _require_seal(journal, plan, evidence, claim)
        result = journal.append_execution_confirmation_claim(
            claim=claim,
            transition_instance_fingerprint=plan.terminal_transition_instance_fingerprint,
            observed_at_epoch=observed_at_epoch,
            observed_monotonic_ns=observed_monotonic_ns,
        ).append_terminal_state(
            transition_instance_fingerprint=plan.terminal_transition_instance_fingerprint,
            final_state_fingerprint=evidence.legacy_topology_fingerprint,
            terminal_state=TerminalStateV2.LEGACY_FLAT_LAYOUT_RESTORED,
            terminal_evidence_fingerprint=evidence.evidence_fingerprint,
        )
        return _progress(
            RollbackProgressStatusV2.LEGACY_FLAT_LAYOUT_RESTORED,
            result,
            plan.terminal_transition_instance_fingerprint,
            None,
            0,
            2,
        )
    except RollbackRecoveryError:
        raise
    except Exception:
        raise RollbackRecoveryError() from None


def _require_seal(journal, plan, evidence, claim):
    if (
        type(journal) is not R2TransactionJournalV2
        or type(plan) is not R2RollbackPlanV2
        or type(evidence) is not R2LegacyRestorationEvidenceV2
        or type(claim) is not ExecutionConfirmationClaimV1
        or plan.completed_prefix_count(journal) != plan.transition_count
        or evidence.binding_fingerprint != plan.binding_fingerprint
        or evidence.plan_fingerprint != plan.plan_fingerprint
        or evidence.journal_head_fingerprint != journal.current_head_fingerprint
        or claim.command is not ProductionCommandV2.ROLLBACK
        or claim.prior_journal_head_fingerprint != journal.current_head_fingerprint
        or claim.transition_instance_fingerprint
        != plan.terminal_transition_instance_fingerprint
        or claim.remaining_reverse_plan_fingerprint != plan.terminal_plan_fingerprint
    ):
        raise RollbackRecoveryError()
    expected = transaction_action_fingerprint_v2(
        plan._binding,
        ProductionCommandV2.ROLLBACK,
        journal_head_fingerprint=journal.current_head_fingerprint,
        transition_instance_fingerprint=plan.terminal_transition_instance_fingerprint,
        remaining_reverse_plan_fingerprint=plan.terminal_plan_fingerprint,
    )
    if claim.action_fingerprint != expected:
        raise RollbackRecoveryError()
