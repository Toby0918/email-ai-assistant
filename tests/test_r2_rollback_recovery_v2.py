"""Journal-derived LIFO rollback and legacy restoration for Issue #97."""

from __future__ import annotations

import unittest

from backend.r2_rollback_recovery_v2 import (
    R2LegacyRestorationEvidenceV2,
    R2RollbackEffectEvidenceV2,
    R2RollbackPlanV2,
    RollbackBoundaryV2,
    RollbackProgressStatusV2,
    begin_next_rollback_action_v2,
    classify_rollback_pending_v2,
    commit_rollback_effect_v2,
    resume_rollback_transition_v2,
    seal_legacy_flat_layout_restored_v2,
)
from backend.r2_transaction_journal_v2 import (
    EffectClassificationV2,
    TerminalStateV2,
)
from backend.r2_transaction_process.production_v2 import complete_transaction_action_v2
from tests.test_r2_foundation_publication_v2 import _restart
from tests.r2_rollback_recovery_v2_fixture import (
    complete_forward_journal as _complete_forward_journal,
    complete_rollback as _complete_rollback,
    inspection as _inspection,
    rollback_claim as _rollback_claim,
    rollback_plan as _rollback_plan,
    terminal_claim as _terminal_claim,
)
from tests.test_r2_transaction_journal_v2 import _live_append_observation


class R2RollbackRecoveryV2Tests(unittest.TestCase):
    def setUp(self):
        self.binding, self.foundation, self.managed, self.validation, self.journal = (
            _complete_forward_journal()
        )
        self.plan = _rollback_plan(
            self.binding,
            self.foundation,
            self.managed,
            self.validation,
            self.journal,
        )

    def test_plan_is_journal_derived_lifo_with_failed_container_first(self):
        restarted = R2RollbackPlanV2.from_json(
            self.plan.to_canonical_json(),
            binding=self.binding,
            foundation_plan=self.foundation,
            managed_plan=self.managed,
            validation_plan=self.validation,
            journal=self.journal,
        )
        self.assertEqual(restarted, self.plan)
        self.assertEqual(restarted.transition_count, 33)
        self.assertIs(
            restarted.transitions[0].boundary,
            RollbackBoundaryV2.PRESERVE_FAILED_CONTAINER,
        )
        forward = self.foundation.transitions + self.managed.transitions + self.validation.transitions
        self.assertEqual(
            tuple(item.source_transition_fingerprint for item in restarted.transitions[1:]),
            tuple(item.transition_instance_fingerprint for item in reversed(forward)),
        )
        self.assertEqual(
            len({item.remaining_plan_fingerprint for item in restarted.transitions}), 33
        )
        self.assertNotIn("0" * 64, restarted.remaining_plan_fingerprints)
        with self.assertRaisesRegex(TypeError, "R2RollbackPlanV2 requires derive"):
            R2RollbackPlanV2(transitions=tuple(reversed(restarted.transitions)))

    def test_all_reverse_actions_use_fresh_confirmation_and_retain_objects(self):
        journal = self.journal
        claims = []
        for transition in self.plan.transitions:
            prior = journal.current_head_fingerprint
            claim = _rollback_claim(self.binding, self.plan, journal, transition)
            pending = begin_next_rollback_action_v2(
                journal=journal, plan=self.plan, claim=claim,
                **_live_append_observation(),
            )
            completion = complete_transaction_action_v2(
                self.binding,
                claim,
                prior,
                transition.transition_instance_fingerprint,
                transition.remaining_plan_fingerprint,
            )
            evidence = R2RollbackEffectEvidenceV2.create(
                binding=self.binding,
                transition=transition,
                action_completion=completion,
                observed_state_fingerprint=transition.post_state_fingerprint,
                retained_objects_fingerprint="a" * 64,
                failed_container_retained=True,
                partial_objects_retained=True,
                destructive_operations=0,
            )
            committed = commit_rollback_effect_v2(
                journal=_restart(pending.journal, self.binding),
                plan=self.plan,
                evidence=evidence,
            )
            self.assertEqual((committed.host_mutations, committed.journal_appends), (1, 2))
            journal = _restart(committed.journal, self.binding)
            claims.append(claim.claim_fingerprint)
        self.assertEqual(len(set(claims)), self.plan.transition_count)
        self.assertIs(committed.status, RollbackProgressStatusV2.ROLLBACK_ACTIONS_COMPLETE)
        self.assertEqual(self.plan.completed_prefix_count(journal), 33)

    def test_reverse_crash_recovery_is_tri_state_and_never_blind_replays(self):
        transition = self.plan.transitions[0]
        for state, pre, post, classification in (
            (transition.pre_state_fingerprint, True, False, EffectClassificationV2.EFFECT_ABSENT_EXACT),
            (transition.post_state_fingerprint, False, True, EffectClassificationV2.EFFECT_PRESENT_EXACT),
            ("e" * 64, False, False, EffectClassificationV2.EFFECT_AMBIGUOUS),
        ):
            claim = _rollback_claim(self.binding, self.plan, self.journal, transition)
            pending = begin_next_rollback_action_v2(
                journal=self.journal, plan=self.plan, claim=claim,
                **_live_append_observation(),
            )
            inspection = _inspection(pending.journal, state, pre=pre, post=post)
            classified = classify_rollback_pending_v2(
                journal=pending.journal, plan=self.plan, inspection=inspection
            )
            self.assertIs(classified.classification, classification)
            if classification is EffectClassificationV2.EFFECT_AMBIGUOUS:
                self.assertIs(classified.status, RollbackProgressStatusV2.INCIDENT_STOP)
                with self.assertRaisesRegex(ValueError, "R2_ROLLBACK_RECOVERY_INVALID"):
                    resume_rollback_transition_v2(
                        journal=classified.journal, plan=self.plan, claim=claim,
                        **_live_append_observation(),
                    )
                continue
            fresh = _rollback_claim(
                self.binding, self.plan, classified.journal, transition
            )
            resumed = resume_rollback_transition_v2(
                journal=classified.journal, plan=self.plan, claim=fresh,
                **_live_append_observation(),
            )
            expected_mutations = 0
            self.assertEqual(resumed.host_mutations, expected_mutations)
            self.assertEqual(resumed.journal_appends, 2)
            if classification is EffectClassificationV2.EFFECT_PRESENT_EXACT:
                self.assertEqual(self.plan.completed_prefix_count(resumed.journal), 1)
            else:
                self.assertEqual(self.plan.completed_prefix_count(resumed.journal), 0)

    def test_exact_legacy_audits_allow_one_terminal_and_no_cleanup(self):
        journal = _complete_rollback(self.binding, self.plan, self.journal)
        evidence = R2LegacyRestorationEvidenceV2.create(
            binding=self.binding,
            plan=self.plan,
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
        claim = _terminal_claim(self.binding, self.plan, journal)
        sealed = seal_legacy_flat_layout_restored_v2(
            journal=journal, plan=self.plan, evidence=evidence, claim=claim,
            **_live_append_observation(),
        )
        self.assertIs(sealed.status, RollbackProgressStatusV2.LEGACY_FLAT_LAYOUT_RESTORED)
        self.assertEqual((sealed.host_mutations, sealed.journal_appends), (0, 2))
        self.assertIs(
            sealed.journal.records[-1].terminal_state,
            TerminalStateV2.LEGACY_FLAT_LAYOUT_RESTORED,
        )
        with self.assertRaisesRegex(ValueError, "R2_ROLLBACK_RECOVERY_INVALID"):
            seal_legacy_flat_layout_restored_v2(
                journal=sealed.journal, plan=self.plan, evidence=evidence, claim=claim,
                **_live_append_observation(),
            )


if __name__ == "__main__":
    unittest.main()
