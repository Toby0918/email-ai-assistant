"""Capability and documentation guards for production binding V3."""

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
        from backend.r2_solo_maintainer_closure import (
            FinalMasterBindingV1 as PublicFinalMasterBindingV1,
        )
        from backend.r2_solo_maintainer_closure.contracts import (
            FinalMasterBindingV1 as ContractFinalMasterBindingV1,
        )

        self.assertIs(PublicFinalMasterBindingV1, ContractFinalMasterBindingV1)
        self.assertEqual(
            {path.name for path in PACKAGE.glob("*.py")},
            {
                "__init__.py",
                "_binding_body.py",
                "_adapter_identity.py",
                "_frame_primitives.py",
                "_module_identity.py",
                "_semantic_identity.py",
                "_static_code.py",
                "_traversal.py",
                "_type_identity.py",
                "_canonical.py",
                "_claim_body.py",
                "binding.py",
                "claim.py",
                "catalog.py",
                "errors.py",
                "execution_confirmation.py",
                "vocabulary.py",
                "review.py",
            },
        )
        self.assertEqual(
            set(production_binding.__all__),
            {
                "ApprovedCutoverBindingV3",
                "AuthorityDomainV2",
                "ExecutionConfirmationCandidateV1",
                "ExecutionConfirmationClaimV1",
                "ExecutionConfirmationError",
                "OperatorRoleV2",
                "ProductionBindingError",
                "ProductionCommandV2",
                "ProductionRoleV2",
                "authority_domain_for_command_v2",
                "confirm_execution_confirmation_v1",
                "prepare_execution_confirmation_v1",
                "production_action_fingerprint_v2",
                "production_adapter_fingerprint_v1",
                "production_composition_evidence_fingerprint_v3",
                "require_reviewed_production_binding_v3",
                "validate_new_execution_confirmation_claim",
            },
        )
        exported_types = {
            value
            for name in production_binding.__all__
            if isinstance((value := getattr(production_binding, name)), type)
        }
        self.assertTrue(exported_types.isdisjoint(REAL_AUTHORIZATION_TYPES))

    def test_only_fixed_confirmation_runtime_has_bounded_console_capability(self):
        allowed_absolute = {
            "__future__",
            "builtins",
            "dataclasses",
            "enum",
            "hashlib",
            "inspect",
            "json",
            "dis",
            "marshal",
            "re",
            "struct",
            "types",
            "sys",
            "backend.r2_solo_maintainer_closure.contracts",
        }
        forbidden_calls = {"open", "print", "exec", "eval", "compile", "__import__"}
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
                allowed = set(allowed_absolute)
                if path.name == "review.py":
                    allowed.update({"ctypes", "msvcrt", "os", "threading", "time"})
                self.assertLessEqual(imports, allowed)
                self.assertTrue(calls.isdisjoint(forbidden_calls))
        for forbidden in (
            "ApprovedCutoverBindingV2",
            "DurableAuthorityClaimV2",
            "PublicKeyRoleV2",
            "verification_public_keys",
            "public_key_registry_fingerprint",
            "Ed25519",
            ".sign(",
            "private_bytes",
            "subprocess",
            "socket",
            "sqlite3",
            "requests",
            "openai",
            "mailbox",
            "vault",
        ):
            self.assertNotIn(forbidden, source)

    def test_public_interfaces_accept_no_key_path_or_command_text(self):
        values = (
            production_binding.ApprovedCutoverBindingV3.create,
            production_binding.prepare_execution_confirmation_v1,
            production_binding.confirm_execution_confirmation_v1,
            production_binding.validate_new_execution_confirmation_claim,
        )
        forbidden = {
            "private_key",
            "signing_key",
            "verification_public_keys",
            "path",
            "root",
            "argv",
            "shell",
            "git_command",
            "issue39_approval",
        }
        for value in values:
            self.assertTrue(
                set(inspect.signature(value).parameters).isdisjoint(forbidden)
            )

    def test_normative_docs_pin_v3_and_dormant_confirmation_contracts(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "ApprovedCutoverBindingV3",
                "ExecutionConfirmationClaimV1",
            ),
            "docs/constraints/architecture_constraints.md": (
                "backend/r2_production_binding",
                "SOLE_MAINTAINER_SELF_REVIEW",
            ),
            "docs/constraints/linter_constraints.md": (
                "ApprovedCutoverBindingV3",
                "DORMANT_NO_ISSUE39_APPROVAL",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Execution Confirmation",
                "issue39_authority_count=0",
            ),
            "docs/operations/project_structure.md": (
                "backend/r2_production_binding/",
                "ExecutionConfirmationClaimV1",
            ),
            "docs/operations/testing_checklist.md": (
                "tests.test_r2_execution_confirmation",
                "tests.test_r2_execution_confirmation_architecture",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
