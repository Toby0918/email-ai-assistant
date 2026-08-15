from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.r2_issue39_orchestrator.durable_ledger import (
    Issue39LedgerStatusV1,
    _Issue39LedgerLocationV1,
    _append_issue39_journal_v1,
    _create_issue39_ledger_v1,
    _reopen_issue39_ledger_v1,
)
from tests.test_r2_transaction_journal_v2 import (
    NOW,
    _binding,
    _confirmed_claim,
    _genesis,
    _live_append_observation,
)
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_production_binding import ProductionCommandV2
from backend.r2_transaction_process.production_v2 import (
    transaction_action_fingerprint_v2,
)


class Issue39DurableLedgerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.location = _Issue39LedgerLocationV1(self.root / "ledger")
        self.binding = _binding()
        self.journal = R2TransactionJournalV2.create(
            binding=self.binding,
            genesis=_genesis(self.binding),
            **_live_append_observation(),
        )

    def test_create_append_and_reopen_verify_every_create_only_prefix(self):
        created = _create_issue39_ledger_v1(
            location=self.location,
            binding=self.binding,
            journal=self.journal,
        )
        transition = "1" * 64
        claim = _confirmed_claim(
            binding=self.binding,
            command=ProductionCommandV2.EXECUTE,
            action_fingerprint=transaction_action_fingerprint_v2(
                self.binding,
                ProductionCommandV2.EXECUTE,
                journal_head_fingerprint=self.journal.current_head_fingerprint,
                transition_instance_fingerprint=transition,
                remaining_reverse_plan_fingerprint="0" * 64,
            ),
            head=self.journal.current_head_fingerprint,
            transition=transition,
            remaining_reverse_plan_fingerprint="0" * 64,
            claim_sequence=2,
            confirmed_at_epoch=NOW,
        )
        next_journal = self.journal.append_execution_confirmation_claim(
            claim=claim,
            transition_instance_fingerprint=transition,
            **_live_append_observation(),
        ).append_intent(
            transition_instance_fingerprint=transition,
            pre_state_fingerprint="2" * 64,
            post_state_fingerprint="3" * 64,
        )

        appended = _append_issue39_journal_v1(
            location=self.location,
            binding=self.binding,
            previous=self.journal,
            journal=next_journal,
        )
        reopened = _reopen_issue39_ledger_v1(
            location=self.location,
            binding=self.binding,
        )

        self.assertEqual(created.status, Issue39LedgerStatusV1.CREATED)
        self.assertEqual(appended.status, Issue39LedgerStatusV1.APPENDED)
        self.assertEqual(reopened.status, Issue39LedgerStatusV1.VERIFIED)
        self.assertEqual(reopened.journal.to_framed_bytes(), next_journal.to_framed_bytes())
        self.assertEqual(len(tuple(self.location.directory.iterdir())), 3)

    def test_collision_or_prefix_tamper_is_retained_and_fails_closed(self):
        _create_issue39_ledger_v1(
            location=self.location,
            binding=self.binding,
            journal=self.journal,
        )
        segment = next(self.location.directory.iterdir())
        segment.write_bytes(b"tampered")

        result = _reopen_issue39_ledger_v1(
            location=self.location,
            binding=self.binding,
        )

        self.assertEqual(result.status, Issue39LedgerStatusV1.INCIDENT_STOP)
        self.assertEqual(segment.read_bytes(), b"tampered")


if __name__ == "__main__":
    unittest.main()
