from __future__ import annotations

import os
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.r2_issue39_orchestrator.action_catalog import (
    build_fixed_production_action_catalog_v1,
)
from backend.r2_issue39_orchestrator.action_runner import (
    Issue39ActionRunStatusV1,
    _Issue39ActionRunnerPortsV1,
    _confirmation_action_fingerprint,
    _confirmation_context,
    _reverse_transition,
    _run_issue39_action_catalog_v1,
)
from backend.r2_issue39_orchestrator.durable_ledger import (
    Issue39LedgerResultV1,
    Issue39LedgerStatusV1,
    _Issue39LedgerLocationV1,
    _create_issue39_ledger_v1,
    _reopen_issue39_ledger_v1,
)
from backend.r2_issue39_orchestrator.preparation import (
    Issue39PrepareStatusV1,
    _allocate_prepared_execution_v1,
)
from backend.r2_issue39_orchestrator.readiness import _observation
from backend.r2_issue39_orchestrator.roster import (
    Issue39BoundRosterV1,
    Issue39RosterStatusV1,
    Issue39WorktreeV1,
)
from backend.r2_issue39_orchestrator.terminal_seal import (
    Issue39LegacyAuditV1,
    Issue39TerminalAuditV1,
    terminal_complete,
)
from backend.r2_production_binding import ProductionCommandV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_transaction_journal_v2.vocabulary import (
    JournalRecordTypeV2,
    TerminalStateV2,
)
from tests.test_r2_transaction_journal_v2 import (
    NOW,
    OWNER,
    _binding,
    _confirmed_claim,
    _genesis,
    _live_append_observation,
)


@unittest.skipUnless(os.name == "nt", "Windows synthetic action catalog")
class Issue39ActionRunnerWindowsTest(unittest.TestCase):
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
        created = _create_issue39_ledger_v1(
            location=self.location,
            binding=self.binding,
            journal=self.journal,
        )
        self.assertIs(created.status, Issue39LedgerStatusV1.CREATED)
        self.catalog = build_fixed_production_action_catalog_v1(_prepared())
        self.adapter = _WindowsSyntheticActions(self.root / "actions")
        self.confirmer = _Confirmer(self.binding, self.catalog)

    def test_complete_27_action_catalog_is_durable_and_reopenable(self):
        result = self._run()
        reopened = _reopen_issue39_ledger_v1(
            location=self.location, binding=self.binding
        )

        self.assertIs(result.status, Issue39ActionRunStatusV1.SUCCEEDED)
        self.assertEqual((result.committed, result.reversed), (27, 0))
        self.assertEqual(self.adapter.forward_calls, 27)
        self.assertIs(reopened.status, Issue39LedgerStatusV1.VERIFIED)
        self.assertEqual(reopened.segment_count, 111)
        self.assertIs(
            reopened.journal.records[-1].record_type,
            JournalRecordTypeV2.TERMINAL_STATE,
        )
        self.assertIs(
            reopened.journal.records[-1].terminal_state,
            TerminalStateV2.CUTOVER_SUCCESS,
        )
        self.assertEqual(self.confirmer.commands[-1], ProductionCommandV2.RESUME)

    def test_partial_failure_rolls_back_lifo_and_retains_reverse_objects(self):
        self.adapter.fail_before = 4

        result = self._run()

        self.assertIs(result.status, Issue39ActionRunStatusV1.LEGACY_RECOVERED)
        self.assertEqual((result.committed, result.reversed), (3, 3))
        self.assertEqual(self.adapter.rollback_order, (3, 2, 1))
        self.assertEqual(len(tuple((self.root / "actions").glob("*.rollback"))), 3)
        self.assertIs(
            result.journal.records[-1].terminal_state,
            TerminalStateV2.LEGACY_FLAT_LAYOUT_RESTORED,
        )

    def test_crash_restart_classifies_absent_without_ambiguous_retry(self):
        self.adapter.crash_before = 1
        with self.assertRaises(SystemExit):
            self._run()
        self.adapter.crash_before = None

        resumed = self._run()

        self.assertEqual(self.adapter.forward_calls, 27)
        self.assertIs(resumed.status, Issue39ActionRunStatusV1.SUCCEEDED)

    def test_post_effect_crash_commits_observed_effect_without_repeating_it(self):
        self.adapter.crash_after = 1
        with self.assertRaises(SystemExit):
            self._run()
        self.adapter.crash_after = None

        resumed = self._run()

        self.assertIs(resumed.status, Issue39ActionRunStatusV1.SUCCEEDED)
        self.assertEqual(self.adapter.forward_calls, 27)
        self.assertIn(ProductionCommandV2.RESUME, self.confirmer.commands)

    def test_claim_only_durable_crash_continues_without_new_execute_claim(self):
        self._crash_after_segment(1)

        resumed = self._run()

        self.assertIs(resumed.status, Issue39ActionRunStatusV1.SUCCEEDED)
        self.assertEqual(self.adapter.forward_calls, 27)
        self.assertEqual(
            self.confirmer.commands.count(ProductionCommandV2.EXECUTE), 24
        )
        self.assertEqual(
            self.confirmer.commands.count(ProductionCommandV2.RESUME), 1
        )

    def test_observation_only_crash_requires_resume_before_commit(self):
        self._crash_after_segment(3)

        resumed = self._run()

        self.assertIs(resumed.status, Issue39ActionRunStatusV1.SUCCEEDED)
        self.assertEqual(self.adapter.forward_calls, 27)
        self.assertIn(ProductionCommandV2.RESUME, self.confirmer.commands)

    def test_terminal_claim_only_crash_finishes_seal_without_host_effect(self):
        self._crash_after_segment(110)

        resumed = self._run()

        self.assertIs(resumed.status, Issue39ActionRunStatusV1.SUCCEEDED)
        self.assertEqual(self.adapter.forward_calls, 27)
        self.assertEqual(self.confirmer.commands.count(ProductionCommandV2.RESUME), 1)

    def test_reopened_terminal_rejects_fresh_audit_drift_without_rollback(self):
        self._run()

        def drifted(catalog, journal_head):
            state = hashlib.sha256(b"drifted-terminal-state").hexdigest()
            return Issue39TerminalAuditV1.create(
                catalog=catalog,
                journal_head_fingerprint=journal_head,
                validation_receipt_fingerprint=hashlib.sha256(b"drift").hexdigest(),
                first_read_fingerprint=state,
                second_read_fingerprint=state,
            )

        with patch.object(self, "_terminal_audit", side_effect=drifted):
            resumed = self._run()

        self.assertIs(resumed.status, Issue39ActionRunStatusV1.INCIDENT_STOP)
        self.assertEqual(self.adapter.rollback_calls, 0)

    def test_reopened_terminal_rejects_wrong_final_state(self):
        self._crash_after_segment(109)
        reopened = _reopen_issue39_ledger_v1(
            location=self.location, binding=self.binding
        )
        pending = reopened.journal
        claim = pending.records[-1]
        audit = self._terminal_audit(
            self.catalog, claim.predecessor_head_fingerprint
        )
        malformed = pending.append_terminal_state(
            transition_instance_fingerprint=claim.transition_instance_fingerprint,
            final_state_fingerprint="f" * 64,
            terminal_state=TerminalStateV2.CUTOVER_SUCCESS,
            terminal_evidence_fingerprint=audit.audit_fingerprint,
        )

        with self.assertRaisesRegex(ValueError, "R2_ISSUE39_TERMINAL_INVALID"):
            terminal_complete(self.catalog, malformed, self._ports())

    def test_restart_after_durable_classification_resumes_with_fresh_claim(self):
        self.adapter.crash_before = 1
        with self.assertRaises(SystemExit):
            self._run()
        self.adapter.crash_before = None
        with patch(
            "backend.r2_issue39_orchestrator.action_recovery._resume_classified",
            side_effect=SystemExit("classification persisted"),
        ):
            with self.assertRaises(SystemExit):
                self._run()

        resumed = self._run()

        self.assertIs(resumed.status, Issue39ActionRunStatusV1.SUCCEEDED)
        self.assertEqual(self.adapter.forward_calls, 27)

    def test_partial_prefix_is_retained_and_resumed_with_a_fresh_attempt(self):
        self.adapter.partial_crash = 1
        with self.assertRaises(SystemExit):
            self._run()
        first_attempt = self.adapter.attempts[0]
        self.adapter.partial_crash = None

        resumed = self._run()

        self.assertIs(resumed.status, Issue39ActionRunStatusV1.SUCCEEDED)
        self.assertEqual(self.adapter.forward_calls, 27)
        self.assertGreaterEqual(len(self.adapter.attempts), 2)
        self.assertNotEqual(first_attempt, self.adapter.attempts[1])
        self.assertTrue((self.adapter.root / "0001.partial").is_file())
        self.assertIn(ProductionCommandV2.RESUME, self.confirmer.commands)

    def test_rollback_intent_crash_restarts_and_finishes_lifo(self):
        self.adapter.fail_before = 4
        self.adapter.rollback_crash_before = 3
        with self.assertRaises(SystemExit):
            self._run()
        self.adapter.rollback_crash_before = None

        resumed = self._run()

        self.assertIs(resumed.status, Issue39ActionRunStatusV1.LEGACY_RECOVERED)
        self.assertEqual(self.adapter.rollback_order, (3, 2, 1))

    def test_rollback_post_effect_crash_does_not_repeat_reverse_effect(self):
        self.adapter.fail_before = 4
        self.adapter.rollback_crash_after = 3
        with self.assertRaises(SystemExit):
            self._run()
        self.adapter.rollback_crash_after = None

        resumed = self._run()

        self.assertIs(resumed.status, Issue39ActionRunStatusV1.LEGACY_RECOVERED)
        self.assertEqual(self.adapter.rollback_order, (3, 2, 1))
        self.assertEqual(self.adapter.rollback_calls, 3)

    def test_collision_and_observation_drift_stop_without_effect(self):
        self.adapter.root.mkdir()
        (self.adapter.root / "0001.state").write_bytes(b"unexpected")

        result = self._run()

        self.assertIs(result.status, Issue39ActionRunStatusV1.SAFE_ABORT)
        self.assertEqual(self.adapter.forward_calls, 0)
        self.assertEqual((self.adapter.root / "0001.state").read_bytes(), b"unexpected")

    def test_ledger_append_failure_prevents_action_call(self):
        blocked = Issue39LedgerResultV1(
            Issue39LedgerStatusV1.INCIDENT_STOP, 0, None
        )
        with patch(
            "backend.r2_issue39_orchestrator.action_runner_support._append_issue39_journal_v1",
            return_value=blocked,
        ):
            result = self._run()

        self.assertIs(result.status, Issue39ActionRunStatusV1.SAFE_ABORT)
        self.assertEqual(self.adapter.forward_calls, 0)

    def test_roster_drift_between_intent_and_effect_stops_before_apply(self):
        checks = {"count": 0}

        def reverify():
            checks["count"] += 1
            if checks["count"] == 2:
                raise ValueError("synthetic drift")

        result = self._run(reverify=reverify)

        self.assertIs(result.status, Issue39ActionRunStatusV1.SAFE_ABORT)
        self.assertEqual(self.adapter.forward_calls, 0)

    def _run(self, *, reverify=lambda *_args: None):
        return _run_issue39_action_catalog_v1(
            catalog=self.catalog,
            binding=self.binding,
            location=self.location,
            ports=self._ports(reverify),
        )

    def _ports(self, reverify=lambda *_args: None):
        return _Issue39ActionRunnerPortsV1(
                self.confirmer.confirm,
                self.adapter.observe,
                self.adapter.apply,
                reverify,
                lambda _journal: None,
                self.confirmer.clock,
                self.confirmer.confirm_terminal,
                self._terminal_audit,
                self._legacy_audit,
                self.adapter.partial,
        )

    def _terminal_audit(self, catalog, journal_head):
        state = hashlib.sha256(
            b"synthetic-terminal-state\0" + bytes.fromhex(catalog.catalog_fingerprint)
        ).hexdigest()
        return Issue39TerminalAuditV1.create(
            catalog=catalog,
            journal_head_fingerprint=journal_head,
            validation_receipt_fingerprint=hashlib.sha256(
                b"synthetic-validation-receipt"
            ).hexdigest(),
            first_read_fingerprint=state,
            second_read_fingerprint=state,
        )

    def _legacy_audit(self, catalog, journal_head):
        state = hashlib.sha256(
            b"synthetic-legacy-state\0" + bytes.fromhex(catalog.catalog_fingerprint)
        ).hexdigest()
        return Issue39LegacyAuditV1.create(
            catalog=catalog,
            journal_head_fingerprint=journal_head,
            first_read_fingerprint=state,
            second_read_fingerprint=state,
        )

    def _crash_after_segment(self, index):
        from backend.r2_issue39_orchestrator import durable_ledger

        original = durable_ledger.write_segment

        def interrupted(path, payload):
            original(path, payload)
            if path.name.startswith(f"{index:06d}-"):
                raise SystemExit("synthetic durable cut")

        with patch.object(durable_ledger, "write_segment", interrupted):
            with self.assertRaises(SystemExit):
                self._run()


class _Confirmer:
    def __init__(self, binding, catalog):
        self.binding = binding
        self.catalog = catalog
        self.observed = _live_append_observation()
        self.commands = []

    def confirm(self, action, journal, command):
        sequence = len(journal.execution_confirmation_claims) + 1
        self.commands.append(command)
        transition, remaining = _confirmation_context(
            self.catalog, action, journal, command
        )
        confirmed = NOW + sequence
        self.observed = {
            "observed_at_epoch": confirmed,
            "observed_monotonic_ns": 4_000_000_000,
        }
        return _confirmed_claim(
            binding=self.binding,
            command=command,
            action_fingerprint=_confirmation_action_fingerprint(
                action, journal, command, transition, remaining
            ),
            head=journal.current_head_fingerprint,
            transition=transition,
            remaining_reverse_plan_fingerprint=remaining,
            claim_sequence=sequence,
            confirmed_at_epoch=confirmed,
        )

    def clock(self):
        return self.observed

    def confirm_terminal(
        self, catalog, journal, state, transition, action_fingerprint
    ):
        sequence = len(journal.execution_confirmation_claims) + 1
        command = (
            ProductionCommandV2.RESUME
            if state is TerminalStateV2.CUTOVER_SUCCESS
            else ProductionCommandV2.ROLLBACK
        )
        self.commands.append(command)
        confirmed = NOW + sequence
        self.observed = {
            "observed_at_epoch": confirmed,
            "observed_monotonic_ns": 4_000_000_000,
        }
        return _confirmed_claim(
            binding=self.binding,
            command=command,
            action_fingerprint=action_fingerprint,
            head=journal.current_head_fingerprint,
            transition=transition,
            remaining_reverse_plan_fingerprint="0" * 64,
            claim_sequence=sequence,
            confirmed_at_epoch=confirmed,
        )


class _WindowsSyntheticActions:
    def __init__(self, root):
        self.root = root
        self.fail_before = None
        self.crash_before = None
        self.crash_after = None
        self.rollback_crash_before = None
        self.rollback_crash_after = None
        self.partial_crash = None
        self.forward_calls = 0
        self.rollback_calls = 0
        self._rollback_order = []
        self.attempts = []

    @property
    def rollback_order(self):
        return tuple(self._rollback_order)

    def observe(self, action):
        target = self.root / f"{action.sequence:04d}.state"
        partial = self.root / f"{action.sequence:04d}.partial"
        if partial.is_file() and not target.exists():
            return self._partial_fingerprint(action)
        if not target.exists():
            return action.pre_state_fingerprint
        if target.is_file() and target.read_bytes() == action.action_fingerprint.encode("ascii"):
            return action.post_state_fingerprint
        return "f" * 64

    def apply(self, action, direction, attempt_token):
        self.root.mkdir(exist_ok=True)
        target = self.root / f"{action.sequence:04d}.state"
        if direction == "forward":
            self.attempts.append(attempt_token)
            partial = self.root / f"{action.sequence:04d}.partial"
            if self.partial_crash == action.sequence:
                partial.write_bytes(attempt_token.encode("ascii"))
                raise SystemExit("synthetic partial crash")
            if self.crash_before == action.sequence:
                raise SystemExit("synthetic crash")
            if self.fail_before == action.sequence:
                raise RuntimeError("synthetic pre-effect failure")
            if not action.host_effect:
                self.forward_calls += 1
                return action.post_state_fingerprint
            with target.open("xb") as stream:
                stream.write(action.action_fingerprint.encode("ascii"))
            self.forward_calls += 1
            if self.crash_after == action.sequence:
                raise SystemExit("synthetic post-effect crash")
            return
        if self.rollback_crash_before == action.sequence:
            raise SystemExit("synthetic rollback crash")
        if not action.host_effect:
            raise AssertionError("read-only action must not be rolled back")
        retained = target.with_suffix(".rollback")
        target.rename(retained)
        self.rollback_calls += 1
        self._rollback_order.append(action.sequence)
        if self.rollback_crash_after == action.sequence:
            raise SystemExit("synthetic rollback post-effect crash")

    def partial(self, action, direction, observed):
        return (
            direction == "forward"
            and observed == self._partial_fingerprint(action)
            and (self.root / f"{action.sequence:04d}.partial").is_file()
        )

    @staticmethod
    def _partial_fingerprint(action):
        return hashlib.sha256(
            b"synthetic-partial-v1\0"
            + bytes.fromhex(action.action_fingerprint)
        ).hexdigest()


def _prepared():
    worktrees = tuple(
        Issue39WorktreeV1(
            f"worktree_{index:02d}",
            "embedded" if index <= 2 else "external",
            f"{index:064x}",
        )
        for index in range(1, 7)
    )
    roster = Issue39BoundRosterV1(
        Issue39RosterStatusV1.VERIFIED,
        worktrees,
        "c" * 64,
        Path("D:/synthetic"),
        (),
    )
    return _allocate_prepared_execution_v1(
        Issue39PrepareStatusV1.VERIFIED,
        "a" * 64,
        6,
        2,
        4,
        _observation(True, True, True, "b" * 64),
        None,
        roster,
    )


if __name__ == "__main__":
    unittest.main()
