"""Two-start validation and unique forward seal for Issue #96."""

from __future__ import annotations

import unittest

from backend.r2_production_binding import (
    DurableAuthorityClaimV2,
    ProductionCommandV2,
    ProductionRoleV2,
)
from backend.r2_transaction_journal_v2 import TerminalStateV2
from backend.r2_two_start_validation_v2 import (
    R2FinalSealObservationV2,
    R2TwoStartValidationPlanV2,
    R2TwoStartValidationReceiptV2,
    R2ValidationActionEvidenceV2,
    ValidationBoundaryV2,
    ValidationProgressStatusV2,
    begin_next_validation_action_v2,
    commit_validation_action_v2,
    lifecycle_action_fingerprint_v2,
    seal_cutover_success_v2,
)
from tests.test_r2_foundation_publication_v2 import (
    _plan as _foundation_plan,
    _restart,
)
from tests.test_r2_managed_unit_publication_v2 import (
    _commit_one,
    _complete_foundation,
    _managed_plan,
)
from tests.test_r2_transaction_journal_v2 import NOW, OWNER, _binding


class R2TwoStartValidationV2Tests(unittest.TestCase):
    def setUp(self):
        self.binding = _binding()
        self.foundation = _foundation_plan(self.binding)
        journal = _complete_foundation(self.binding, self.foundation)
        self.managed = _managed_plan(self.binding, self.foundation)
        for transition in self.managed.transitions:
            journal = _commit_one(self.binding, self.managed, journal, transition)
        self.journal = _restart(journal, self.binding)
        self.plan = _validation_plan(self.binding, self.managed)

    def test_plan_is_exactly_seven_actions_with_fixed_commands_and_owners(self):
        restarted = R2TwoStartValidationPlanV2.from_json(
            self.plan.to_canonical_json(),
            binding=self.binding,
            managed_plan=self.managed,
        )
        self.assertEqual(restarted, self.plan)
        self.assertEqual(restarted.transition_count, 7)
        self.assertEqual(
            tuple(item.boundary for item in restarted.transitions),
            tuple(ValidationBoundaryV2),
        )
        self.assertEqual(
            tuple(item.command for item in restarted.transitions),
            (
                ProductionCommandV2.EXECUTE,
                ProductionCommandV2.EXECUTE,
                ProductionCommandV2.EXECUTE,
                ProductionCommandV2.EVIDENCE_VERIFICATION,
                ProductionCommandV2.FINAL_AUDIT_READINESS,
                ProductionCommandV2.EXECUTE,
                ProductionCommandV2.FINAL_AUDIT_READINESS,
            ),
        )
        self.assertEqual(restarted.transitions[0].owner, ProductionRoleV2.MANAGED_SERVICE)
        self.assertEqual(restarted.transitions[3].owner, ProductionRoleV2.DATABASE)

    def test_all_actions_reconstruct_and_produce_exact_two_start_receipt(self):
        journal, evidence = self._complete_actions()
        receipt = R2TwoStartValidationReceiptV2.create(
            binding=self.binding,
            plan=self.plan,
            journal=journal,
            action_evidence=evidence,
        )
        restarted = R2TwoStartValidationReceiptV2.from_json(
            receipt.to_canonical_json(),
            binding=self.binding,
            plan=self.plan,
            journal=journal,
        )
        self.assertEqual(restarted, receipt)
        self.assertEqual((receipt.analysis_count, receipt.database_write_count), (1, 1))
        self.assertEqual(receipt.provider_attempts, 0)
        self.assertNotEqual(receipt.start_a_run_fingerprint, receipt.start_b_run_fingerprint)
        self.assertNotEqual(
            receipt.stopped_audit_actor_fingerprint,
            receipt.final_audit_actor_fingerprint,
        )

    def test_fresh_audits_seal_exactly_one_cutover_success(self):
        journal, evidence = self._complete_actions()
        receipt = R2TwoStartValidationReceiptV2.create(
            binding=self.binding,
            plan=self.plan,
            journal=journal,
            action_evidence=evidence,
        )
        observation = R2FinalSealObservationV2.create(
            binding=self.binding,
            validation=receipt,
            journal=journal,
            observed_at_epoch=NOW,
            final_state_fingerprint="e" * 64,
            minimal_read_count=2,
        )
        claim = _claim(
            self.binding,
            self.plan,
            journal,
            self.plan.terminal_transition_instance_fingerprint,
            ProductionCommandV2.RESUME,
        )
        sealed = seal_cutover_success_v2(
            journal=journal,
            plan=self.plan,
            validation=receipt,
            observation=observation,
            claim=claim,
        )
        self.assertIs(sealed.status, ValidationProgressStatusV2.CUTOVER_SUCCESS)
        self.assertEqual((sealed.host_mutations, sealed.journal_appends), (0, 2))
        restarted = _restart(sealed.journal, self.binding)
        self.assertEqual(restarted.next_legal_action, "NONE")
        self.assertIs(restarted.records[-1].terminal_state, TerminalStateV2.CUTOVER_SUCCESS)
        with self.assertRaisesRegex(ValueError, "R2_TWO_START_VALIDATION_INVALID"):
            seal_cutover_success_v2(
                journal=restarted,
                plan=self.plan,
                validation=receipt,
                observation=observation,
                claim=claim,
            )

    def test_provider_attempt_stale_audit_or_mixed_evidence_fails_closed(self):
        journal, evidence = self._complete_actions()
        bad_provider = list(evidence)
        bad_provider[1] = _evidence(
            self.binding,
            self.plan.transitions[1],
            bad_provider[1].claim_fingerprint,
            bad_provider[1].prior_journal_head_fingerprint,
            provider_attempts=1,
        )
        with self.assertRaisesRegex(ValueError, "R2_TWO_START_VALIDATION_INVALID"):
            R2TwoStartValidationReceiptV2.create(
                binding=self.binding,
                plan=self.plan,
                journal=journal,
                action_evidence=tuple(bad_provider),
            )
        stale = list(evidence)
        stale[4] = _evidence(
            self.binding,
            self.plan.transitions[4],
            stale[4].claim_fingerprint,
            stale[4].prior_journal_head_fingerprint,
            observed_at=NOW - 400,
        )
        with self.assertRaisesRegex(ValueError, "R2_TWO_START_VALIDATION_INVALID"):
            R2TwoStartValidationReceiptV2.create(
                binding=self.binding,
                plan=self.plan,
                journal=journal,
                action_evidence=tuple(stale),
            )

    def _complete_actions(self):
        journal, evidence = self.journal, []
        for transition in self.plan.transitions:
            claim = _claim(
                self.binding,
                self.plan,
                journal,
                transition.transition_instance_fingerprint,
                transition.command,
            )
            pending = begin_next_validation_action_v2(
                journal=journal, plan=self.plan, claim=claim
            )
            journal = _restart(pending.journal, self.binding)
            item = _evidence(
                self.binding,
                transition,
                claim.claim_fingerprint,
                claim.prior_journal_head_fingerprint,
            )
            committed = commit_validation_action_v2(
                journal=journal, plan=self.plan, evidence=item
            )
            self.assertEqual(committed.journal_appends, 2)
            journal = _restart(committed.journal, self.binding)
            evidence.append(item)
        self.assertIs(
            committed.status, ValidationProgressStatusV2.VALIDATION_ACTIONS_COMPLETE
        )
        return journal, tuple(evidence)


def _validation_plan(binding, managed):
    pairs = tuple((f"{index + 301:064x}", f"{index + 321:064x}") for index in range(7))
    return R2TwoStartValidationPlanV2.create(
        binding=binding,
        managed_plan=managed,
        transition_states=pairs,
        approved_identities_fingerprint="f" * 64,
    )


def _claim(binding, plan, journal, transition, command):
    action = lifecycle_action_fingerprint_v2(
        binding=binding,
        plan=plan,
        command=command,
        journal_head_fingerprint=journal.current_head_fingerprint,
        transition_instance_fingerprint=transition,
    )
    sequence = len(journal.durable_authority_claims) + 1
    return DurableAuthorityClaimV2.create(
        binding=binding,
        command=command,
        action_fingerprint=action,
        authority_fingerprint=f"{sequence + 100:064x}",
        envelope_nonce=f"{sequence + 140:064x}",
        journal_owner_fingerprint=OWNER,
        prior_journal_head_fingerprint=journal.current_head_fingerprint,
        claim_sequence=sequence,
        issued_at_epoch=NOW - 10,
        not_before_epoch=NOW - 5,
        expires_at_epoch=NOW + 60,
        claimed_at_epoch=NOW,
    )


def _evidence(binding, transition, claim_fingerprint, prior_head, *, provider_attempts=0, observed_at=NOW - 10):
    index = list(ValidationBoundaryV2).index(transition.boundary)
    start_a = "1" * 64
    start_b = "2" * 64
    run = start_b if transition.boundary in {
        ValidationBoundaryV2.START_B,
        ValidationBoundaryV2.FINAL_RUNNING_AUDIT,
    } else start_a
    actors = ("3" * 64, "3" * 64, "3" * 64, "4" * 64, "5" * 64, "6" * 64, "7" * 64)
    nonces = ("8" * 64,) * 5 + ("9" * 64,) * 2
    metrics = {
        ValidationBoundaryV2.START_A: (1, 0, 0, 0),
        ValidationBoundaryV2.RULE_FALLBACK_ANALYSIS: (1, 1, 1, 0),
        ValidationBoundaryV2.STOP_A: (1, 0, 0, 0),
        ValidationBoundaryV2.DATABASE_PROOF: (0, 0, 1, 1),
        ValidationBoundaryV2.STOPPED_LAYOUT_AUDIT: (0, 0, 0, 1),
        ValidationBoundaryV2.START_B: (1, 0, 0, 0),
        ValidationBoundaryV2.FINAL_RUNNING_AUDIT: (0, 0, 0, 1),
    }
    host, analyses, rows, reads = metrics[transition.boundary]
    audit = transition.boundary in {
        ValidationBoundaryV2.STOPPED_LAYOUT_AUDIT,
        ValidationBoundaryV2.FINAL_RUNNING_AUDIT,
    }
    return R2ValidationActionEvidenceV2.create(
        binding=binding,
        transition=transition,
        claim_fingerprint=claim_fingerprint,
        prior_journal_head_fingerprint=prior_head,
        observed_state_fingerprint=transition.post_state_fingerprint,
        run_identity_fingerprint=run,
        actor_identity_fingerprint=actors[index],
        service_nonce_fingerprint=nonces[index],
        evidence_fingerprint=f"{index + 180:064x}",
        host_mutations=host,
        analysis_count=analyses,
        database_row_count=rows,
        provider_attempts=provider_attempts,
        read_only_checks=reads,
        observed_at_epoch=observed_at if audit else 0,
        expires_at_epoch=observed_at + 300 if audit else 0,
    )


if __name__ == "__main__":
    unittest.main()
