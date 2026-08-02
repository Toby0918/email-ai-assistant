"""Shared synthetic builders for Issue #97 tests."""

from backend.r2_production_binding import DurableAuthorityClaimV2, ProductionCommandV2
from backend.r2_rollback_recovery_v2 import (
    R2RollbackEffectEvidenceV2,
    R2RollbackPlanV2,
    begin_next_rollback_action_v2,
    commit_rollback_effect_v2,
)
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_transaction_process.production_v2 import (
    complete_transaction_action_v2,
    transaction_action_fingerprint_v2,
)
from backend.r2_two_start_validation_v2 import (
    begin_next_validation_action_v2,
    commit_validation_action_v2,
)
from tests.test_r2_foundation_publication_v2 import OWNER, _plan, _restart
from tests.test_r2_managed_unit_publication_v2 import (
    _commit_one,
    _complete_foundation,
    _managed_plan,
)
from tests.test_r2_transaction_journal_v2 import NOW, _binding
from tests.test_r2_two_start_validation_v2 import (
    _claim as _validation_claim,
    _evidence as _validation_evidence,
    _validation_plan,
)


def complete_forward_journal():
    binding = _binding()
    foundation = _plan(binding)
    journal = _complete_foundation(binding, foundation)
    managed = _managed_plan(binding, foundation)
    for transition in managed.transitions:
        journal = _commit_one(binding, managed, journal, transition)
    validation = _validation_plan(binding, managed)
    for transition in validation.transitions:
        claim = _validation_claim(
            binding,
            validation,
            journal,
            transition.transition_instance_fingerprint,
            transition.command,
        )
        pending = begin_next_validation_action_v2(
            journal=journal, plan=validation, claim=claim
        )
        evidence = _validation_evidence(
            binding,
            transition,
            claim.claim_fingerprint,
            claim.prior_journal_head_fingerprint,
        )
        journal = commit_validation_action_v2(
            journal=pending.journal, plan=validation, evidence=evidence
        ).journal
    return binding, foundation, managed, validation, _restart(journal, binding)


def rollback_plan(binding, foundation, managed, validation, journal):
    return R2RollbackPlanV2.derive(
        binding=binding,
        foundation_plan=foundation,
        managed_plan=managed,
        validation_plan=validation,
        journal=journal,
    )


def rollback_claim(binding, plan, journal, transition):
    return _claim(
        binding,
        plan,
        journal,
        transition.transition_instance_fingerprint,
        transition.remaining_plan_fingerprint,
        500,
        700,
    )


def terminal_claim(binding, plan, journal):
    return _claim(
        binding,
        plan,
        journal,
        plan.terminal_transition_instance_fingerprint,
        plan.terminal_plan_fingerprint,
        900,
        1100,
    )


def inspection(journal, state, *, pre=False, post=False):
    from tests.test_r2_foundation_publication_v2 import _inspection

    return _inspection(journal, state, pre=pre, post=post)


def complete_rollback(binding, plan, journal):
    for transition in plan.transitions:
        prior = journal.current_head_fingerprint
        claim = rollback_claim(binding, plan, journal, transition)
        pending = begin_next_rollback_action_v2(journal=journal, plan=plan, claim=claim)
        completion = complete_transaction_action_v2(
            binding,
            claim,
            prior,
            transition.transition_instance_fingerprint,
            transition.remaining_plan_fingerprint,
        )
        evidence = R2RollbackEffectEvidenceV2.create(
            binding=binding,
            transition=transition,
            action_completion=completion,
            observed_state_fingerprint=transition.post_state_fingerprint,
            retained_objects_fingerprint="a" * 64,
            failed_container_retained=True,
            partial_objects_retained=True,
            destructive_operations=0,
        )
        journal = commit_rollback_effect_v2(
            journal=pending.journal, plan=plan, evidence=evidence
        ).journal
    return _restart(journal, binding)


def journal_prefix(journal, binding, record_count):
    frames = journal.to_framed_bytes().splitlines(keepends=True)
    return R2TransactionJournalV2.from_framed_bytes(
        b"".join(frames[: record_count + 1]), binding=binding
    )


def _claim(binding, plan, journal, transition, remaining, authority_offset, nonce_offset):
    action = transaction_action_fingerprint_v2(
        binding,
        ProductionCommandV2.ROLLBACK,
        journal_head_fingerprint=journal.current_head_fingerprint,
        transition_instance_fingerprint=transition,
        remaining_reverse_plan_fingerprint=remaining,
    )
    sequence = len(journal.durable_authority_claims) + 1
    return DurableAuthorityClaimV2.create(
        binding=binding,
        command=ProductionCommandV2.ROLLBACK,
        action_fingerprint=action,
        authority_fingerprint=f"{sequence + authority_offset:064x}",
        envelope_nonce=f"{sequence + nonce_offset:064x}",
        journal_owner_fingerprint=OWNER,
        prior_journal_head_fingerprint=journal.current_head_fingerprint,
        claim_sequence=sequence,
        issued_at_epoch=NOW - 10,
        not_before_epoch=NOW - 5,
        expires_at_epoch=NOW + 60,
        claimed_at_epoch=NOW,
    )
