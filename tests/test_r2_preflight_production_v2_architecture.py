"""Capability and normative-document guards for Issue #88."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

import backend.r2_operator_process as operator_process
from backend.r2_preflight_process.production_v2 import (
    dormant_preflight_production_v2,
    run_preflight_production_v2,
)


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "backend" / "r2_preflight_process" / "production_v2.py"
AUTHORITY = ROOT / "backend" / "r2_operator_process" / "production_v2.py"


class R2PreflightProductionV2ArchitectureTests(unittest.TestCase):
    def test_v2_dispatcher_has_verification_and_read_only_composition_only(self):
        source = PREFLIGHT.read_text(encoding="utf-8")
        authority = AUTHORITY.read_text(encoding="utf-8")
        combined = source + authority
        self.assertIn("Ed25519PublicKey", authority)
        self.assertIn("DORMANT_NO_EXTERNAL_ISSUER", source)
        for forbidden in (
            "Ed25519PrivateKey",
            ".sign(",
            "private_bytes",
            "DORMANT_PROFILE",
            "PREFLIGHT_PUBLIC_KEY",
            "_CLAIMED",
            "subprocess",
            "sqlite3",
            "shutil",
            "os.replace",
            "os.remove",
            "unlink",
            "rmtree",
            "mailbox",
            "vault",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertIn("outcome.provider_attempts != 0", source)

        imports = set()
        for path in (PREFLIGHT, AUTHORITY):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports.update(
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            )
        for forbidden in (
            "backend.cutover_host_mutation",
            "backend.cutover_repository_transaction",
            "backend.cutover_managed_activation",
            "backend.cutover_service_lifecycle",
            "backend.migration_evidence_publication_composition",
            "backend.cutover_transaction_composition",
        ):
            self.assertNotIn(forbidden, imports)

    def test_public_dispatch_surface_has_no_path_selector_or_issuer_input(self):
        self.assertTrue(
            {
                "ProductionAuthorityEnvelopeError",
                "production_authority_message_v2",
                "verify_production_authority_v2",
            }.issubset(operator_process.__all__)
        )
        self.assertEqual(
            set(inspect.signature(dormant_preflight_production_v2).parameters),
            {"argv"},
        )
        parameters = set(inspect.signature(run_preflight_production_v2).parameters)
        self.assertTrue(
            parameters.isdisjoint(
                {
                    "path",
                    "root",
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

    def test_normative_docs_pin_v2_reachability_and_dormancy(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #88 production preflight V2 dispatcher",
                "DORMANT_NO_EXTERNAL_ISSUER",
                "read-only",
            ),
            "docs/constraints/architecture_constraints.md": (
                "six V2 preflight verbs",
                "complete production composition",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 V2 preflight dispatcher guards",
                "no external issuer",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #88 production preflight reachability rules",
                "one read-only role",
            ),
            "docs/operations/project_structure.md": (
                "r2_operator_process/production_v2.py",
                "r2_preflight_process/production_v2.py",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_preflight_production_v2.py",
                "test_r2_preflight_production_v2_architecture.py",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
