"""Administrator module entrypoint and operator-documentation contracts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_BRIEF = (
    ROOT
    / "docs"
    / "operations"
    / "real_mailbox_scan_driven_plugin_task_brief.md"
)
IMPLEMENTATION_PLAN = (
    ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-15-real-mailbox-scan-driven-plugin-deepseek-completion.md"
)


class AdministratorModuleEntrypointTests(unittest.TestCase):
    def _run_module(self, module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        return subprocess.run(
            [sys.executable, "-B", "-m", module, *arguments],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_all_administrator_modules_reach_their_parsers_without_pythonpath(self) -> None:
        help_cases = (
            ("scripts.manage_mailbox_vault", "manage_mailbox_vault.py", "inventory"),
            (
                "scripts.manage_private_knowledge",
                "manage_private_knowledge.py",
                "import-candidate",
            ),
            (
                "scripts.evaluate_private_deepseek",
                "evaluate_private_deepseek.py",
                "build",
            ),
        )
        for module, program, command in help_cases:
            with self.subTest(module=module):
                result = self._run_module(module, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"usage: {program}", result.stdout)
                self.assertIn(command, result.stdout)

        result = self._run_module("scripts.evaluate_private_deepseek", "not-a-command")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {"ok": False, "code": "argument_invalid"},
        )
        self.assertEqual(result.stderr, "")

    def test_private_evaluation_module_has_static_root_and_command_help(self) -> None:
        for arguments, expected in (
            (("--help",), ("build", "verify", "run")),
            (("-h",), ("build", "verify", "run")),
            (("build", "--help"), ("--staging", "--dataset")),
            (("build", "-h"), ("--staging", "--dataset")),
            (("verify", "--help"), ("--dataset",)),
            (("verify", "-h"), ("--dataset",)),
            (
                ("run", "--help"),
                ("--dataset", "--interactive-judge", "--confirm-private-evaluation"),
            ),
            (
                ("run", "-h"),
                ("--dataset", "--interactive-judge", "--confirm-private-evaluation"),
            ),
        ):
            with self.subTest(arguments=arguments):
                result = self._run_module(
                    "scripts.evaluate_private_deepseek", *arguments
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn("usage: evaluate_private_deepseek.py", result.stdout)
                for value in expected:
                    self.assertIn(value, result.stdout)
                self.assertEqual(result.stderr, "")

    def test_private_evaluation_help_cannot_mask_forbidden_override(self) -> None:
        result = self._run_module(
            "scripts.evaluate_private_deepseek",
            "verify",
            "--dataset",
            "C:/SyntheticExternal/private.pkeval",
            "--model",
            "deepseek-v4-pro",
            "--help",
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            result.stdout,
            '{"code": "argument_invalid", "ok": false}\n',
        )
        self.assertEqual(result.stderr, "")

    def test_governance_documents_capture_the_approved_six_slice_boundary(self) -> None:
        for path in (TASK_BRIEF, IMPLEMENTATION_PLAN):
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"missing governance document: {path}")
                text = path.read_text(encoding="utf-8")
                for required in (
                    "Slice 1: Administrator entrypoints and governance",
                    "Slice 2: Evaluation staging, dataset build, and interactive judge",
                    "Slice 3: Read-only runtime knowledge snapshot bootstrap",
                    "Slice 4: Tencent context extraction, privacy diagnostics, and rule facts",
                    "Slice 5: Task-card extension UI",
                    "Slice 6: Full verification, project status, and live inventory readiness",
                    "rolling 24-month",
                    "imap.exmail.qq.com:993",
                    "inventory fingerprint",
                    "no raw mail to Codex, DeepSeek, Git, or public SQLite",
                    "separate live credential and fingerprint gate",
                ):
                    self.assertIn(required, text)

        brief = TASK_BRIEF.read_text(encoding="utf-8")
        self.assertEqual(
            re.findall(r"(?m)^## (\d+)\. ", brief),
            [str(number) for number in range(1, 19)],
        )
        self.assertIn("## 2. Task type\n\n`docs`", brief)
        self.assertIn("## 3. Current status\n\n`implemented`", brief)
        for required_section in (
            "## 15. Human confirmation required",
            "## 16. Pre-execution checklist",
            "## 17. Remote provider private-context checklist",
            "## 18. Post-execution record",
        ):
            self.assertIn(required_section, brief)

    def test_task_brief_preserves_allowed_ignored_sqlite_without_accessing_it(self) -> None:
        brief = TASK_BRIEF.read_text(encoding="utf-8")

        for required in (
            "`outputs/email_agent.sqlite3` may remain in OneDrive",
            "must remain Git-ignored and untracked",
            "must not be uploaded",
            "must not be opened, moved, or deleted during this phase",
        ):
            with self.subTest(required=required):
                self.assertIn(required, brief)
        self.assertNotIn("separately isolated or disposed of", brief)

    def test_operator_docs_use_module_entrypoints_and_stop_after_inventory(self) -> None:
        expected_by_path = {
            ROOT / "docs" / "operations" / "testing_checklist.md": (
                "python -B -m scripts.manage_mailbox_vault init",
                "python -B -m scripts.manage_mailbox_vault inventory",
                "python -B -m scripts.manage_mailbox_vault scan",
                "python -B -m scripts.manage_private_knowledge import-candidate",
                "python -B -m scripts.evaluate_private_deepseek verify",
                "STOP after inventory",
            ),
            ROOT / "docs" / "operations" / "deployment_notes.md": (
                "python -B -m scripts.manage_mailbox_vault init",
                "python -B -m scripts.manage_mailbox_vault inventory",
                "python -B -m scripts.manage_mailbox_vault scan",
                "STOP after inventory",
            ),
            ROOT / "docs" / "operations" / "private_deepseek_evaluation.md": (
                "python -B -m scripts.evaluate_private_deepseek verify",
                "python -B -m scripts.evaluate_private_deepseek run",
            ),
        }
        for path, required_commands in expected_by_path.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                for command in required_commands:
                    self.assertIn(command, text)
                if "STOP after inventory" in required_commands:
                    inventory_index = text.index(
                        "python -B -m scripts.manage_mailbox_vault inventory"
                    )
                    stop_index = text.index("STOP after inventory")
                    scan_index = text.index(
                        "python -B -m scripts.manage_mailbox_vault scan"
                    )
                    self.assertLess(inventory_index, stop_index)
                    self.assertLess(stop_index, scan_index)
                    self.assertIn(
                        "--confirm-inventory-fingerprint",
                        text[scan_index:scan_index + 500],
                    )

    def test_live_runbooks_verify_before_and_after_approved_attachments(self) -> None:
        scan_command = "python -B -m scripts.manage_mailbox_vault scan"
        verify_command = "python -B -m scripts.manage_mailbox_vault verify"
        approval = "attachment approval"
        attachments_command = "python -B -m scripts.manage_mailbox_vault attachments"
        for path in (
            ROOT / "docs" / "operations" / "testing_checklist.md",
            ROOT / "docs" / "operations" / "deployment_notes.md",
        ):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                scan_index = text.index(scan_command)
                verify_indexes = tuple(
                    match.start()
                    for match in re.finditer(re.escape(verify_command), text)
                    if match.start() > scan_index
                )
                self.assertGreaterEqual(
                    len(verify_indexes), 2,
                    "live runbook requires one verify before and one after attachments",
                )
                first_verify, second_verify = verify_indexes[:2]
                approval_index = text.find(
                    approval, first_verify + len(verify_command)
                )
                attachments_index = text.find(
                    attachments_command, approval_index + len(approval)
                )
                self.assertNotEqual(approval_index, -1)
                self.assertNotEqual(attachments_index, -1)
                self.assertLess(scan_index, first_verify)
                self.assertLess(first_verify, approval_index)
                self.assertLess(approval_index, attachments_index)
                self.assertLess(attachments_index, second_verify)

    def test_runnable_admin_examples_never_use_direct_script_paths(self) -> None:
        forbidden = re.compile(
            r"python(?:\s+-B)?\s+scripts[\\/]"
            r"(?:manage_mailbox_vault|manage_private_knowledge|evaluate_private_deepseek)\.py"
        )
        findings: list[str] = []
        for path in (ROOT / "docs").rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            if forbidden.search(text):
                findings.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
