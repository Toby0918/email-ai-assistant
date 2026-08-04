"""Capability and documentation guards for Issue #90."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from backend.cutover_contracts.authorization import REAL_AUTHORIZATION_TYPES
from backend.r2_transaction_process.production_v2 import (
    TransactionActionCompletionV2,
    dormant_transaction_production_v2,
    run_transaction_production_v2,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_transaction_process"
PRODUCTION = PACKAGE / "production_v2.py"


class R2TransactionProductionV2ArchitectureTests(unittest.TestCase):
    def test_dispatcher_has_only_verification_and_one_action_composition(self):
        source = "".join(
            path.read_text(encoding="utf-8")
            for path in (
                PRODUCTION,
                PACKAGE / "_production_v2_canonical.py",
            )
        )
        self.assertNotIn(TransactionActionCompletionV2, REAL_AUTHORIZATION_TYPES)
        self.assertIn("DORMANT_NO_EXTERNAL_ISSUER", source)
        for forbidden in (
            "ed25519privatekey",
            ".sign(",
            "private_bytes",
            "dormant_profile",
            "execution_public_key",
            "recovery_public_key",
            "subprocess",
            "sqlite3",
            "os.replace",
            "os.remove",
            "unlink",
            "rmtree",
            "open(",
            "retry",
            "cleanup",
            "mailbox",
            "vault",
        ):
            self.assertNotIn(forbidden, source.lower())
        self.assertIn("outcome.provider_attempts != 0", source)

        tree = ast.parse(PRODUCTION.read_text(encoding="utf-8"))
        self.assertFalse(any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertTrue(
            imports.isdisjoint(
                {
                    "backend.r2_preflight_process",
                    "backend.r2_evidence_process",
                    "backend.migration_evidence_verifier",
                }
            )
        )

    def test_public_surface_has_no_path_batch_switch_retry_or_issuer(self):
        self.assertEqual(
            set(inspect.signature(dormant_transaction_production_v2).parameters),
            {"argv"},
        )
        parameters = set(inspect.signature(run_transaction_production_v2).parameters)
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
                    "batch",
                    "retry",
                    "switch_direction",
                    "cleanup",
                }
            )
        )

    def test_normative_docs_pin_single_authority_single_action(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #90 V2 single-action transaction process",
                "one authority",
                "at most one action",
            ),
            "docs/constraints/architecture_constraints.md": (
                "three V2 transaction verbs",
                "journal-bound action fingerprint",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 V2 single-action transaction guards",
                "no retry",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #90 transaction reachability rules",
                "one invocation",
            ),
            "docs/operations/project_structure.md": (
                "r2_transaction_process/production_v2.py",
                "_production_v2_canonical.py",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_transaction_production_v2.py",
                "test_r2_transaction_production_v2_architecture.py",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
