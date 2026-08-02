"""Deterministic object-level retention ledger for Issue #98."""

from __future__ import annotations

import unittest

from backend.r2_retention_ledger_v2 import (
    R2RetentionLedgerV2,
    R2RetentionProofV2,
    RetentionLedgerStageV2,
    RetentionObjectKindV2,
)
from backend.r2_rollback_recovery_v2 import (
    R2LegacyRestorationEvidenceV2,
    R2RollbackEffectEvidenceV2,
    begin_next_rollback_action_v2,
    classify_rollback_pending_v2,
    commit_rollback_effect_v2,
    resume_rollback_transition_v2,
    seal_legacy_flat_layout_restored_v2,
)
from backend.r2_transaction_process.production_v2 import complete_transaction_action_v2
from tests.r2_rollback_recovery_v2_fixture import (
    complete_forward_journal,
    complete_rollback,
    inspection,
    rollback_claim,
    rollback_plan,
    terminal_claim,
)
from tests.test_r2_foundation_publication_v2 import _restart


class R2RetentionLedgerV2Tests(unittest.TestCase):
    def setUp(self):
        self.binding, self.foundation, self.managed, self.validation, self.journal = (
            complete_forward_journal()
        )
        self.rollback = rollback_plan(
            self.binding,
            self.foundation,
            self.managed,
            self.validation,
            self.journal,
        )

    def test_forward_projection_tracks_every_required_object_class(self):
        ledger = self._project(self.journal)
        restarted = R2RetentionLedgerV2.from_json(
            ledger.to_canonical_json(),
            binding=self.binding,
            foundation_plan=self.foundation,
            managed_plan=self.managed,
            validation_plan=self.validation,
            rollback_plan=self.rollback,
            journal=self.journal,
        )
        self.assertEqual(restarted, ledger)
        self.assertIs(ledger.stage, RetentionLedgerStageV2.FORWARD_COMMITTED)
        self.assertEqual(ledger.forward_commit_count, 32)
        self.assertEqual(ledger.rollback_commit_count, 0)
        self.assertEqual(
            ledger.kind_counts,
            {
                RetentionObjectKindV2.ORIGINAL_OBJECT: 32,
                RetentionObjectKindV2.NEW_OBJECT: 32,
                RetentionObjectKindV2.PARTIAL_OBJECT: 32,
                RetentionObjectKindV2.FAILED_CONTAINER: 1,
                RetentionObjectKindV2.EVIDENCE_OBJECT: 32,
                RetentionObjectKindV2.JOURNAL_ARTIFACT: self.journal.record_count,
            },
        )
        self.assertEqual(ledger.entry_count, sum(ledger.kind_counts.values()))
        self.assertEqual(len({item.entry_fingerprint for item in ledger.entries}), ledger.entry_count)
        self.assertTrue(all(item.retention_required for item in ledger.entries))

    def test_pending_recovery_rollback_and_terminal_states_reconcile(self):
        transition = self.rollback.transitions[0]
        claim = rollback_claim(self.binding, self.rollback, self.journal, transition)
        pending = begin_next_rollback_action_v2(
            journal=self.journal, plan=self.rollback, claim=claim
        )
        self.assertIs(
            self._project(pending.journal).stage,
            RetentionLedgerStageV2.ROLLBACK_PENDING,
        )
        classified = classify_rollback_pending_v2(
            journal=pending.journal,
            plan=self.rollback,
            inspection=inspection(
                pending.journal, transition.pre_state_fingerprint, pre=True
            ),
        )
        self.assertIs(
            self._project(classified.journal).stage,
            RetentionLedgerStageV2.ROLLBACK_RECOVERY_CLASSIFIED,
        )
        fresh = rollback_claim(
            self.binding, self.rollback, classified.journal, transition
        )
        resumed = resume_rollback_transition_v2(
            journal=classified.journal, plan=self.rollback, claim=fresh
        )
        self.assertIs(
            self._project(resumed.journal).stage,
            RetentionLedgerStageV2.ROLLBACK_PENDING,
        )
        committed = _commit_reverse(
            self.binding, self.rollback, self.journal, transition
        )
        self.assertIs(
            self._project(committed).stage,
            RetentionLedgerStageV2.ROLLBACK_IN_PROGRESS,
        )
        complete = complete_rollback(self.binding, self.rollback, self.journal)
        self.assertIs(
            self._project(complete).stage,
            RetentionLedgerStageV2.ROLLBACK_COMPLETE,
        )
        sealed = _seal(self.binding, self.rollback, complete)
        self.assertIs(
            self._project(sealed).stage,
            RetentionLedgerStageV2.LEGACY_RESTORED,
        )

    def test_proof_reconciles_all_entries_with_zero_capabilities_or_payload(self):
        complete = complete_rollback(self.binding, self.rollback, self.journal)
        ledger = self._project(complete)
        proof = R2RetentionProofV2.create(
            binding=self.binding, ledger=ledger, journal=complete
        )
        restarted = R2RetentionProofV2.from_json(
            proof.to_canonical_json(),
            binding=self.binding,
            ledger=ledger,
            journal=complete,
        )
        self.assertEqual(restarted, proof)
        self.assertEqual(
            (
                proof.reconciled_entry_count,
                proof.untracked_artifact_count,
                proof.deletion_capability_count,
                proof.overwrite_capability_count,
                proof.prune_capability_count,
                proof.automatic_expiry_capability_count,
                proof.private_payload_field_count,
            ),
            (ledger.entry_count, 0, 0, 0, 0, 0, 0),
        )
        self.assertNotIn("object_fingerprint", repr(proof))

    def test_mixed_inputs_and_injected_artifacts_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "R2_RETENTION_LEDGER_INVALID"):
            R2RetentionLedgerV2.project(
                binding=object(),
                foundation_plan=self.foundation,
                managed_plan=self.managed,
                validation_plan=self.validation,
                rollback_plan=self.rollback,
                journal=self.journal,
            )
        ledger = self._project(self.journal)
        payload = ledger.to_canonical_json().replace(b'"entry_count":258', b'"entry_count":259')
        with self.assertRaisesRegex(ValueError, "R2_RETENTION_LEDGER_INVALID"):
            R2RetentionLedgerV2.from_json(
                payload,
                binding=self.binding,
                foundation_plan=self.foundation,
                managed_plan=self.managed,
                validation_plan=self.validation,
                rollback_plan=self.rollback,
                journal=self.journal,
            )

    def _project(self, journal):
        return R2RetentionLedgerV2.project(
            binding=self.binding,
            foundation_plan=self.foundation,
            managed_plan=self.managed,
            validation_plan=self.validation,
            rollback_plan=self.rollback,
            journal=journal,
        )


def _commit_reverse(binding, plan, journal, transition):
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
    return _restart(
        commit_rollback_effect_v2(
            journal=pending.journal, plan=plan, evidence=evidence
        ).journal,
        binding,
    )


def _seal(binding, plan, journal):
    evidence = R2LegacyRestorationEvidenceV2.create(
        binding=binding,
        plan=plan,
        journal=journal,
        legacy_topology_fingerprint="b" * 64,
        legacy_service_health_fingerprint="c" * 64,
        legacy_acl_audit_fingerprint="d" * 64,
        git_worktree_audit_fingerprint="e" * 64,
        original_identity_count=22,
        git_relationship_count=12,
        retained_failed_container_count=1,
        destructive_operations=0,
        provider_attempts=0,
        legacy_analysis_writes=0,
        independent_read_count=2,
    )
    return seal_legacy_flat_layout_restored_v2(
        journal=journal,
        plan=plan,
        evidence=evidence,
        claim=terminal_claim(binding, plan, journal),
    ).journal


if __name__ == "__main__":
    unittest.main()
