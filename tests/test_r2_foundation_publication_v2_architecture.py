"""Capability and documentation guards for Issue #94."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from backend.cutover_contracts.authorization import REAL_AUTHORIZATION_TYPES


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_foundation_publication_v2"


class R2FoundationPublicationV2ArchitectureTests(unittest.TestCase):
    def test_fixed_plan_and_progress_receipts_are_non_authorizing(self):
        source = "".join(
            path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
        )
        imports = {
            node.module
            for path in PACKAGE.glob("*.py")
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        for phrase in (
            "LEGACY_SERVICE_QUIESCENCE",
            "LEGACY_ANCHOR_RENAME",
            "CONTAINER_PUBLICATION",
            "MAIN_PUBLICATION",
            "ACL_WHOLE_TREE_CONFORMANCE",
            "REPOSITORY_RELOCATION",
            "WORKTREE_RECONSTRUCTION",
        ):
            self.assertIn(phrase, source)
        self.assertFalse(
            {"pathlib", "os", "subprocess", "sqlite3"} & imports
        )
        for forbidden in (
            "open(", "privatekey", ".sign(", "delete", "unlink", "remove(",
            "rmtree", "shell", "mailbox", "provider", "vault", "cleanup",
        ):
            self.assertNotIn(forbidden, source.lower())
        from backend.r2_foundation_publication_v2 import FoundationProgressV2

        self.assertNotIn(FoundationProgressV2, REAL_AUTHORIZATION_TYPES)

    def test_normative_docs_pin_foundation_single_actions(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #94 foundation single-actions",
                "exactly seventeen foundation transitions",
            ),
            "docs/constraints/architecture_constraints.md": (
                "R2FoundationPlanV2",
                "eleven worktree instances",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 foundation publication guards",
                "recovered commit without effect replay",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #94 foundation rules",
                "FOUNDATION_RECOVERED_COMMIT",
            ),
            "docs/operations/project_structure.md": (
                "r2_foundation_publication_v2/",
                "progress.py",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_foundation_publication_v2.py",
                "17 foundation transitions",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
