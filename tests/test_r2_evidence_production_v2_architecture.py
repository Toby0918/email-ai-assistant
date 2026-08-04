"""Capability and documentation guards for Issue #89."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from backend.cutover_contracts.authorization import REAL_AUTHORIZATION_TYPES
from backend.r2_evidence_process.production_v2 import (
    dormant_evidence_production_v2,
    run_evidence_production_v2,
)
from backend.r2_transaction_journal_v2 import R2JournalGenesisV2


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "backend" / "r2_evidence_process"
JOURNAL = ROOT / "backend" / "r2_transaction_journal_v2"


class R2EvidenceProductionV2ArchitectureTests(unittest.TestCase):
    def test_physical_evidence_root_and_pure_journal_package_are_closed(self):
        self.assertEqual(
            {path.name for path in JOURNAL.glob("*.py")},
            {
                "__init__.py",
                "_canonical.py",
                "errors.py",
                "genesis.py",
                "inspection.py",
                "journal.py",
                "record.py",
                "vocabulary.py",
            },
        )
        self.assertNotIn(R2JournalGenesisV2, REAL_AUTHORIZATION_TYPES)
        production = (EVIDENCE / "production_v2.py").read_text(encoding="utf-8")
        journal = "".join(
            path.read_text(encoding="utf-8") for path in JOURNAL.glob("*.py")
        )
        combined = production + journal
        for forbidden in (
            "Ed25519PrivateKey",
            ".sign(",
            "private_bytes",
            "DORMANT_PROFILE",
            "EVIDENCE_PUBLIC_KEY",
            "subprocess",
            "sqlite3",
            "os.replace",
            "os.remove",
            "unlink",
            "rmtree",
            "open(",
            "mailbox",
            "vault",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertIn("outcome.provider_attempts != 0", production)

        imports = set()
        for path in (EVIDENCE / "production_v2.py", *JOURNAL.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports.update(
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            )
        for forbidden in (
            "backend.r2_preflight_process",
            "backend.r2_transaction_process",
            "backend.cutover_transaction_composition",
            "backend.migration_evidence_verifier",
        ):
            self.assertNotIn(forbidden, imports)

    def test_public_surface_has_one_verb_and_no_path_selector_or_issuer(self):
        self.assertEqual(
            set(inspect.signature(dormant_evidence_production_v2).parameters),
            {"argv"},
        )
        parameters = set(inspect.signature(run_evidence_production_v2).parameters)
        self.assertTrue(
            parameters.isdisjoint(
                {
                    "path",
                    "root",
                    "target",
                    "profile",
                    "selector",
                    "force",
                    "shell",
                    "private_key",
                    "issuer",
                    "payload",
                }
            )
        )

    def test_normative_docs_pin_create_only_publication_and_genesis(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #89 production evidence V2 and journal genesis",
                "R2JournalGenesisV2",
                "create-only",
            ),
            "docs/constraints/architecture_constraints.md": (
                "single V2 evidence-publication verb",
                "fresh-process genesis reconstruction",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 V2 evidence and genesis guards",
                "reviewed-evidence action fingerprint",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #89 evidence/genesis rules",
                "canonical genesis",
            ),
            "docs/operations/project_structure.md": (
                "r2_evidence_process/production_v2.py",
                "r2_transaction_journal_v2/",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_evidence_production_v2.py",
                "test_r2_evidence_production_v2_architecture.py",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
