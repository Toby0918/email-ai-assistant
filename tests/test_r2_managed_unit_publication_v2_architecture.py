"""Capability and documentation guards for Issue #95."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from backend.cutover_contracts.authorization import REAL_AUTHORIZATION_TYPES


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_managed_unit_publication_v2"


class R2ManagedUnitPublicationV2ArchitectureTests(unittest.TestCase):
    def test_managed_plan_is_pure_retaining_and_non_authorizing(self):
        paths = tuple(PACKAGE.glob("*.py"))
        source = "".join(path.read_text(encoding="utf-8") for path in paths)
        imports = {
            node.module
            for path in paths
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        for phrase in (
            "RUNTIME", "DATABASE", "CRX", "CONFIG", "PREPARE", "PUBLISH",
            "source_retained", "partial_retained", "failed_unit_retained",
        ):
            self.assertIn(phrase, source)
        self.assertFalse({"pathlib", "os", "subprocess", "sqlite3"} & imports)
        for forbidden in (
            "open(", "privatekey", ".sign(", "delete", "unlink", "remove(",
            "rmtree", "shell", "mailbox", "provider", "vault", "cleanup",
        ):
            self.assertNotIn(forbidden, source.lower())
        from backend.r2_managed_unit_publication_v2 import ManagedProgressV2

        self.assertNotIn(ManagedProgressV2, REAL_AUTHORIZATION_TYPES)

    def test_normative_docs_pin_managed_single_actions(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #95 managed-unit single-actions",
                "source, partial, and failed-unit evidence",
            ),
            "docs/constraints/architecture_constraints.md": (
                "R2ManagedUnitPlanV2",
                "exactly eight transitions",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 managed-unit publication guards",
                "SQLite semantic conformance",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #95 managed-unit rules",
                "MANAGED_RECOVERED_COMMIT",
            ),
            "docs/operations/project_structure.md": (
                "r2_managed_unit_publication_v2/",
                "recovery.py",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_managed_unit_publication_v2.py",
                "8 managed-unit transitions",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
