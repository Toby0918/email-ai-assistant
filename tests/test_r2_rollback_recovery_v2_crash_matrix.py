"""Forward crash-cut matrix for Issue #97 rollback."""

import unittest

from backend.r2_managed_unit_publication_v2 import (
    R2ManagedRecoveryInspectionV2,
    begin_next_managed_action_v2,
    classify_managed_pending_v2,
)
from backend.r2_rollback_recovery_v2 import (
    RollbackProgressStatusV2,
    begin_next_rollback_action_v2,
)
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2
from tests.r2_rollback_recovery_v2_fixture import (
    complete_forward_journal,
    inspection,
    journal_prefix,
    rollback_claim,
    rollback_plan,
)
from tests.test_r2_foundation_publication_v2 import (
    _claim as _forward_claim,
    _plan as _foundation_plan,
)
from tests.test_r2_managed_unit_publication_v2 import _complete_foundation, _managed_plan
from tests.test_r2_transaction_journal_v2 import _binding
from tests.test_r2_two_start_validation_v2 import _validation_plan


class R2RollbackCrashMatrixV2Tests(unittest.TestCase):
    def setUp(self):
        self.binding, self.foundation, self.managed, self.validation, self.journal = (
            complete_forward_journal()
        )

    def test_every_forward_commit_prefix_has_a_complete_reverse_matrix(self):
        commits = [index for index, record in enumerate(self.journal.records) if record.record_type is JournalRecordTypeV2.COMMIT]
        self.assertEqual(len(commits), 32)
        for expected, record_index in enumerate(commits, start=1):
            prefix = journal_prefix(self.journal, self.binding, record_index + 1)
            plan = rollback_plan(self.binding, self.foundation, self.managed, self.validation, prefix)
            self.assertEqual((plan.forward_commit_count, plan.transition_count), (expected, expected + 1))

    def test_every_forward_journal_cut_has_one_disposition(self):
        committed = 0
        for record_index, record in enumerate(self.journal.records, start=1):
            prefix = journal_prefix(self.journal, self.binding, record_index)
            committed += record.record_type is JournalRecordTypeV2.COMMIT
            if committed == 0:
                with self.assertRaisesRegex(ValueError, "R2_ROLLBACK_RECOVERY_INVALID"):
                    rollback_plan(self.binding, self.foundation, self.managed, self.validation, prefix)
                continue
            plan = rollback_plan(self.binding, self.foundation, self.managed, self.validation, prefix)
            transition = plan.transitions[0]
            claim = rollback_claim(self.binding, plan, prefix, transition)
            if record.record_type is JournalRecordTypeV2.COMMIT:
                started = begin_next_rollback_action_v2(journal=prefix, plan=plan, claim=claim)
                self.assertIs(started.status, RollbackProgressStatusV2.ROLLBACK_ACTION_PENDING)
            else:
                with self.assertRaisesRegex(ValueError, "R2_ROLLBACK_RECOVERY_INVALID"):
                    begin_next_rollback_action_v2(journal=prefix, plan=plan, claim=claim)

    def test_exact_forward_pre_switches_to_fresh_rollback_authority(self):
        binding = _binding()
        foundation = _foundation_plan(binding)
        journal = _complete_foundation(binding, foundation)
        managed = _managed_plan(binding, foundation)
        validation = _validation_plan(binding, managed)
        forward = managed.transitions[0]
        pending = begin_next_managed_action_v2(journal=journal, plan=managed, claim=_forward_claim(binding, managed, journal, forward))
        plan_at_intent = rollback_plan(binding, foundation, managed, validation, pending.journal)
        transition = plan_at_intent.transitions[0]
        with self.assertRaisesRegex(ValueError, "R2_ROLLBACK_RECOVERY_INVALID"):
            begin_next_rollback_action_v2(journal=pending.journal, plan=plan_at_intent, claim=rollback_claim(binding, plan_at_intent, pending.journal, transition))
        observed = inspection(pending.journal, forward.pre_state_fingerprint, pre=True)
        proof = R2ManagedRecoveryInspectionV2.create(binding=binding, transition=forward, inspection=observed, acl_conformance_fingerprint="c" * 64, semantic_conformance_fingerprint="d" * 64, acl_exact=True, semantic_exact=True)
        classified = classify_managed_pending_v2(journal=pending.journal, plan=managed, inspection=proof)
        plan = rollback_plan(binding, foundation, managed, validation, classified.journal)
        transition = plan.transitions[0]
        started = begin_next_rollback_action_v2(journal=classified.journal, plan=plan, claim=rollback_claim(binding, plan, classified.journal, transition))
        self.assertIs(started.status, RollbackProgressStatusV2.ROLLBACK_ACTION_PENDING)


if __name__ == "__main__":
    unittest.main()
