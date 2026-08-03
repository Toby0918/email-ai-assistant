"""Capability and documentation guards for Issue #93."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from backend.cutover_contracts.authorization import REAL_AUTHORIZATION_TYPES


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_transaction_journal_v2"


class R2TransactionJournalV2ArchitectureTests(unittest.TestCase):
    def test_unified_journal_is_pure_non_authorizing_and_has_no_stage_owner(self):
        paths = tuple(PACKAGE.glob("*.py"))
        source = "".join(path.read_text(encoding="utf-8") for path in paths)
        imports = {
            node.module
            for path in paths
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        for required in (
            "AUTHORITY_CLAIM",
            "INTENT",
            "EFFECT_OBSERVATION",
            "COMMIT",
            "RECOVERY_CLASSIFICATION",
            "TERMINAL_STATE",
            "EFFECT_ABSENT_EXACT",
            "EFFECT_PRESENT_EXACT",
            "EFFECT_AMBIGUOUS",
        ):
            self.assertIn(required, source)
        self.assertFalse(
            {
                "pathlib",
                "os",
                "subprocess",
                "sqlite3",
                "backend.r2_preflight_process",
                "backend.r2_evidence_process",
                "backend.r2_transaction_process",
            }
            & imports
        )
        for forbidden in (
            "open(",
            "stage_journal_owner",
            "current_head_owner",
            "privatekey",
            ".sign(",
            "delete",
            "unlink",
            "remove(",
            "rmtree",
            "retry",
            "mailbox",
            "provider",
            "vault",
        ):
            self.assertNotIn(forbidden, source.lower())
        from backend.r2_transaction_journal_v2 import (
            R2ReadOnlyInspectionReceiptV2,
        )

        self.assertNotIn(R2ReadOnlyInspectionReceiptV2, REAL_AUTHORIZATION_TYPES)

    def test_normative_docs_pin_unified_journal_and_read_only_inspection(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #93 unified transaction journal",
                "fresh-process reconstruction",
                "read-only tri-state inspection",
            ),
            "docs/constraints/architecture_constraints.md": (
                "R2TransactionJournalV2",
                "single authoritative current head",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 unified-journal guards",
                "torn tail",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #93 journal rules",
                "RECOVERY_CLASSIFICATION",
            ),
            "docs/operations/project_structure.md": (
                "r2_transaction_journal_v2/",
                "inspection.py",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_transaction_journal_v2.py",
                "PRE/POST/AMBIGUOUS",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
