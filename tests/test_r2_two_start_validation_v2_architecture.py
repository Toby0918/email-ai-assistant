"""Capability and documentation guards for Issue #96."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from backend.cutover_contracts.authorization import REAL_AUTHORIZATION_TYPES


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_two_start_validation_v2"


class R2TwoStartValidationV2ArchitectureTests(unittest.TestCase):
    def test_lifecycle_and_seal_are_pure_non_authorizing(self):
        paths = tuple(PACKAGE.glob("*.py"))
        source = "".join(path.read_text(encoding="utf-8") for path in paths)
        imports = {
            node.module
            for path in paths
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        for phrase in (
            "START_A", "RULE_FALLBACK_ANALYSIS", "STOP_A", "DATABASE_PROOF",
            "STOPPED_LAYOUT_AUDIT", "START_B", "FINAL_RUNNING_AUDIT",
            "CUTOVER_SUCCESS",
        ):
            self.assertIn(phrase, source)
        self.assertFalse({"pathlib", "os", "subprocess", "sqlite3"} & imports)
        for forbidden in (
            "open(", "privatekey", ".sign(", "delete", "unlink", "remove(",
            "rmtree", "shell", "mailbox", "vault", "cleanup", "batch",
        ):
            self.assertNotIn(forbidden, source.lower())
        from backend.r2_two_start_validation_v2 import R2TwoStartValidationReceiptV2

        self.assertNotIn(R2TwoStartValidationReceiptV2, REAL_AUTHORIZATION_TYPES)

    def test_normative_docs_pin_two_start_and_unique_seal(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #96 two-start validation and final seal",
                "exactly one durable CUTOVER_SUCCESS",
            ),
            "docs/constraints/architecture_constraints.md": (
                "R2TwoStartValidationPlanV2",
                "seven ordered lifecycle transitions",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 two-start validation guards",
                "provider_attempts=0",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #96 validation rules",
                "minimal_read_count=2",
            ),
            "docs/operations/project_structure.md": (
                "r2_two_start_validation_v2/",
                "seal.py",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_two_start_validation_v2.py",
                "7 validation transitions",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
