"""Capability and documentation guards for Issue #92."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from backend.cutover_contracts.authorization import REAL_AUTHORIZATION_TYPES


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_repository_manifest"


class R2GitByteStateV2ArchitectureTests(unittest.TestCase):
    def test_git_byte_contract_is_pure_and_non_authorizing(self):
        paths = tuple(PACKAGE.glob("*git_byte*.py"))
        source = "".join(
            path.read_text(encoding="utf-8") for path in paths
        )
        imports = {
            node.module
            for path in paths
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertIn("R2GitByteStateReceiptV1", source)
        self.assertFalse(
            {
                "pathlib",
                "os",
                "subprocess",
                "backend.r2_preflight_process",
                "backend.r2_evidence_process",
                "backend.r2_transaction_process",
            }
            & imports
        )
        for forbidden in (
            "open(",
            ".read_",
            "walk(",
            "glob(",
            "ls-files",
            "--ignored",
            "mailbox",
            "vault",
            "credential",
            "private key",
            "delete",
            "unlink",
            "remove(",
            "rmtree",
        ):
            self.assertNotIn(forbidden, source.lower())
        from backend.r2_repository_manifest import R2GitByteStateReceiptV1

        self.assertNotIn(R2GitByteStateReceiptV1, REAL_AUTHORIZATION_TYPES)

    def test_normative_docs_pin_git_object_byte_state(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #92 Git-byte state",
                "fourteen local refs",
                "ignored or private content",
            ),
            "docs/constraints/architecture_constraints.md": (
                "Git-object byte conformance",
                "stable common state",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 Git-byte state guards",
                "same-size",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #92 Git-byte rules",
                "eleven original",
            ),
            "docs/operations/project_structure.md": (
                "git_byte_state_v2.py",
                "git_byte_types_v2.py",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_git_byte_state_v2.py",
                "EOL/filter drift",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
