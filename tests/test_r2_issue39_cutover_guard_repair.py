from __future__ import annotations

import io
import inspect
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.r2_issue39_orchestrator.action_catalog import (
    build_fixed_production_action_catalog_v1,
)
from backend.r2_issue39_orchestrator.confirmation_context import (
    display_confirmation_context_v1,
    format_confirmation_context_v1,
)
from backend.r2_issue39_orchestrator.closure_binding import (
    _Issue39ClosureBindingV1,
)
from backend.r2_issue39_orchestrator import (
    bootstrap_confirmation,
    production_confirmation,
    production_preflight,
)
from backend.r2_issue39_orchestrator.production_confirmation import (
    FixedIssue39ActionConfirmerV1,
)
from backend.r2_production_binding import ProductionCommandV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from scripts import execute_project_container_cutover as cutover_entry
from tests.test_r2_issue39_action_runner_windows import _prepared
from tests.test_r2_transaction_journal_v2 import (
    _binding,
    _genesis,
    _live_append_observation,
)


class Issue39CutoverGuardRepairTest(unittest.TestCase):
    def test_initial_launcher_accepts_only_script_root_at_fixed_worktree(self):
        self.assertEqual(
            str(cutover_entry.FIXED_INITIAL_LAUNCHER_ROOT),
            r"D:\Projects\email_ai_assistant\.worktrees\issue39-governed-enablement",
        )
        with tempfile.TemporaryDirectory() as temporary:
            script_root = Path(temporary)
            scripts = script_root / "scripts"
            scripts.mkdir()
            script = scripts / "execute_project_container_cutover.py"
            script.write_text(
                "# test-owned fixed launcher\n", encoding="ascii"
            )
            alternate = scripts / "alternate_cutover.py"
            alternate.write_text("# alternate launcher\n", encoding="ascii")
            with (
                patch.object(
                    cutover_entry, "FIXED_INITIAL_LAUNCHER_ROOT", script_root
                ),
                patch.object(
                    cutover_entry, "FIXED_INITIAL_LAUNCHER_SCRIPT", script
                ),
            ):
                self.assertTrue(
                    cutover_entry._initial_launch_anchor_matches(
                        script, script_root
                    )
                )
                self.assertFalse(
                    cutover_entry._initial_launch_anchor_matches(
                        script, script_root.parent
                    )
                )
                self.assertFalse(
                    cutover_entry._initial_launch_anchor_matches(
                        alternate, script_root
                    )
                )

    def test_wrong_cwd_script_stops_before_importing_live_orchestrator(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "execute_project_container_cutover.py"
        )
        with tempfile.TemporaryDirectory() as temporary:
            completed = subprocess.run(
                (sys.executable, "-I", "-B", str(script), "run"),
                cwd=temporary,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(
            completed.stdout.decode("ascii"),
            '{"accepted":0,"host_actions":0,"rejected":1,'
            '"status":"BLOCKED_ISSUE39_LAUNCH_ANCHOR"}' + os.linesep,
        )
        self.assertEqual(completed.stderr, b"")

    def test_catalog_context_is_ascii_bounded_and_human_reviewable(self):
        line = format_confirmation_context_v1(
            phase="catalog",
            operation="legacy_service_quiescence",
            command=ProductionCommandV2.EXECUTE,
            direction="forward",
            current_state="PRE_STATE_EXACT",
            sequence=1,
            total=27,
        )

        self.assertEqual(
            line,
            "ISSUE39_CONFIRMATION_CONTEXT_V1 "
            "phase=catalog operation=legacy_service_quiescence "
            "command=execute direction=forward state=PRE_STATE_EXACT "
            "sequence=1 total=27",
        )
        self.assertTrue(line.isascii())
        self.assertLess(len(line), 256)

    def test_context_is_displayed_as_one_line_before_signature_material(self):
        output = io.StringIO()
        with patch("sys.stdout", output):
            display_confirmation_context_v1(
                phase="terminal",
                operation="cutover_success_seal",
                command=ProductionCommandV2.RESUME,
                direction="none",
                current_state="FINAL_AUDIT_EXACT",
                sequence=28,
                total=28,
            )

        self.assertEqual(
            output.getvalue(),
            "ISSUE39_CONFIRMATION_CONTEXT_V1 "
            "phase=terminal operation=cutover_success_seal "
            "command=resume direction=none state=FINAL_AUDIT_EXACT "
            "sequence=28 total=28\n",
        )

    def test_context_rejects_unreviewed_or_non_printable_values(self):
        invalid = (
            {"phase": "unknown"},
            {"operation": "legacy_service_quiescence\nforged"},
            {"direction": "sideways"},
            {"current_state": "raw path"},
            {"sequence": 0},
            {"total": 99},
        )
        base = {
            "phase": "catalog",
            "operation": "legacy_service_quiescence",
            "command": ProductionCommandV2.EXECUTE,
            "direction": "forward",
            "current_state": "PRE_STATE_EXACT",
            "sequence": 1,
            "total": 27,
        }
        for replacement in invalid:
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError):
                    format_confirmation_context_v1(
                        **(base | replacement)
                    )

    def test_context_rejects_valid_fields_in_an_invalid_combination(self):
        invalid = (
            {
                "phase": "preflight",
                "operation": "host_baseline",
                "command": ProductionCommandV2.RESUME,
                "direction": "none",
                "current_state": "READY_TO_OBSERVE",
            },
            {
                "phase": "evidence",
                "operation": "evidence_resume",
                "command": ProductionCommandV2.EVIDENCE_PUBLICATION,
                "direction": "none",
                "current_state": "EVIDENCE_CLASSIFIED_EXACT",
            },
            {
                "phase": "catalog",
                "operation": "database_proof",
                "command": ProductionCommandV2.EXECUTE,
                "direction": "forward",
                "current_state": "PRE_STATE_EXACT",
            },
            {
                "phase": "terminal",
                "operation": "cutover_success_seal",
                "command": ProductionCommandV2.ROLLBACK,
                "direction": "none",
                "current_state": "FINAL_AUDIT_EXACT",
            },
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    format_confirmation_context_v1(
                        **values, sequence=1, total=1
                    )

    def test_catalog_adapter_displays_bound_context_before_confirmation(self):
        binding = _binding()
        closure = _Issue39ClosureBindingV1(
            SimpleNamespace(manifest_fingerprint="d" * 64),
            SimpleNamespace(receipt_fingerprint="e" * 64),
            object(),
            binding,
        )
        catalog = build_fixed_production_action_catalog_v1(_prepared())
        journal = R2TransactionJournalV2.create(
            binding=binding,
            genesis=_genesis(binding),
            **_live_append_observation(),
        )
        confirmer = FixedIssue39ActionConfirmerV1.create(
            closure=closure,
            catalog=catalog,
        )
        action = catalog.actions[0]

        with (
            patch.object(
                production_confirmation,
                "display_confirmation_context_v1",
            ) as display,
            patch.object(
                production_confirmation,
                "confirm_execution_confirmation_v1",
                return_value=object(),
            ),
        ):
            confirmer.confirm(action, journal, ProductionCommandV2.EXECUTE)

        display.assert_called_once_with(
            phase="catalog",
            operation="legacy_service_quiescence",
            command=ProductionCommandV2.EXECUTE,
            direction="forward",
            current_state="PRE_STATE_EXACT",
            sequence=1,
            total=27,
        )

    def test_catalog_context_precedes_candidate_and_acknowledgement(self):
        binding = _binding()
        closure = _Issue39ClosureBindingV1(
            SimpleNamespace(manifest_fingerprint="d" * 64),
            SimpleNamespace(receipt_fingerprint="e" * 64),
            object(),
            binding,
        )
        catalog = build_fixed_production_action_catalog_v1(_prepared())
        journal = R2TransactionJournalV2.create(
            binding=binding,
            genesis=_genesis(binding),
            **_live_append_observation(),
        )
        confirmer = FixedIssue39ActionConfirmerV1.create(
            closure=closure,
            catalog=catalog,
        )
        output = io.StringIO()

        def signed(*, candidate):
            self.assertIsNotNone(candidate)
            sys.stdout.write("candidate-fingerprint\n")
            sys.stdout.write("fixed-acknowledgement\n")
            return object()

        with (
            patch("sys.stdout", output),
            patch.object(
                production_confirmation,
                "confirm_execution_confirmation_v1",
                side_effect=signed,
            ),
        ):
            confirmer.confirm(
                catalog.actions[0], journal, ProductionCommandV2.EXECUTE
            )

        self.assertEqual(
            output.getvalue().splitlines(),
            [
                "ISSUE39_CONFIRMATION_CONTEXT_V1 "
                "phase=catalog operation=legacy_service_quiescence "
                "command=execute direction=forward state=PRE_STATE_EXACT "
                "sequence=1 total=27",
                "candidate-fingerprint",
                "fixed-acknowledgement",
            ],
        )

    def test_every_v3_issue39_confirmation_adapter_displays_context(self):
        for module in (
            production_preflight,
            bootstrap_confirmation,
            production_confirmation,
        ):
            with self.subTest(module=module.__name__):
                source = inspect.getsource(module)
                self.assertIn("display_confirmation_context_v1", source)
                self.assertLess(
                    source.index("display_confirmation_context_v1"),
                    source.rindex("confirm_execution_confirmation_v1"),
                )


if __name__ == "__main__":
    unittest.main()
