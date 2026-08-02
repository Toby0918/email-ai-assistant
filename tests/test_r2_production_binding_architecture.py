"""Capability and documentation guards for production binding V2."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

import backend.r2_production_binding as production_binding
from backend.cutover_contracts.authorization import REAL_AUTHORIZATION_TYPES


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_production_binding"


class R2ProductionBindingArchitectureTests(unittest.TestCase):
    def test_package_files_exports_and_authority_separation_are_exact(self):
        self.assertEqual(
            {path.name for path in PACKAGE.glob("*.py")},
            {
                "__init__.py",
                "_binding_body.py",
                "_canonical.py",
                "_claim_body.py",
                "binding.py",
                "claim.py",
                "errors.py",
                "vocabulary.py",
            },
        )
        self.assertEqual(
            set(production_binding.__all__),
            {
                "ApprovedCutoverBindingV2",
                "AuthorityClaimError",
                "AuthorityDomainV2",
                "DurableAuthorityClaimV2",
                "OperatorRoleV2",
                "ProductionBindingError",
                "ProductionCommandV2",
                "ProductionRoleV2",
                "PublicKeyRoleV2",
                "authority_domain_for_command_v2",
                "production_action_fingerprint_v2",
                "validate_new_authority_claim",
            },
        )
        exported_types = {
            value
            for name in production_binding.__all__
            if isinstance((value := getattr(production_binding, name)), type)
        }
        self.assertTrue(exported_types.isdisjoint(REAL_AUTHORIZATION_TYPES))

    def test_package_has_verification_values_but_no_issuer_or_host_capability(self):
        allowed_absolute = {
            "__future__",
            "dataclasses",
            "enum",
            "hashlib",
            "json",
            "backend.r2_final_master_closure",
        }
        forbidden_calls = {
            "open",
            "print",
            "exec",
            "eval",
            "compile",
            "__import__",
        }
        source = ""
        for path in sorted(PACKAGE.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            source += text
            tree = ast.parse(text, filename=str(path))
            imports = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module is not None
            }
            imports.update(
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )
            calls = {
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            with self.subTest(path=path.name):
                self.assertLessEqual(imports, allowed_absolute)
                self.assertTrue(calls.isdisjoint(forbidden_calls))
        for forbidden in (
            "Ed25519PrivateKey",
            ".sign(",
            "private_bytes",
            "subprocess",
            "socket",
            "sqlite3",
            "requests",
            "openai",
            "mailbox",
            "vault",
            "_CLAIMED",
        ):
            self.assertNotIn(forbidden, source)

    def test_public_interface_accepts_no_private_key_path_or_command_text(self):
        for value in (
            production_binding.ApprovedCutoverBindingV2.create,
            production_binding.DurableAuthorityClaimV2.create,
            production_binding.validate_new_authority_claim,
        ):
            parameters = set(inspect.signature(value).parameters)
            self.assertTrue(
                parameters.isdisjoint(
                    {
                        "private_key",
                        "signing_key",
                        "path",
                        "root",
                        "argv",
                        "shell",
                        "git_command",
                    }
                )
            )

    def test_normative_docs_pin_binding_and_fresh_process_claim_contracts(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "ApprovedCutoverBindingV2",
                "DurableAuthorityClaimV2",
                "no private signing keys",
            ),
            "docs/constraints/architecture_constraints.md": (
                "backend/r2_production_binding",
                "fresh-process reconstruction",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 production binding V2 guards",
                "durable single-use",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #87 reviewed production binding V2 rules",
                "four authority domains",
            ),
            "docs/operations/project_structure.md": (
                "backend/r2_production_binding/",
                "DurableAuthorityClaimV2",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_production_binding_contracts.py",
                "test_r2_production_binding_architecture.py",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
