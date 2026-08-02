"""Architecture and authority-separation guards for final-master closure."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import backend.r2_final_master_closure as closure
from backend.cutover_contracts.authorization import REAL_AUTHORIZATION_TYPES


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_final_master_closure"


class R2FinalMasterClosureArchitectureTests(unittest.TestCase):
    def test_public_interface_is_exact_and_contains_no_authority_type(self):
        self.assertEqual(
            set(closure.__all__),
            {
                "ClosureGate",
                "ClosureGap",
                "ClosureGapRegistrationV1",
                "FinalMasterBindingV1",
                "FinalMasterClosureError",
                "FinalMasterClosureStatus",
                "FindingClassification",
                "GateEvidenceProducerV1",
                "GateEvidenceRegistrationV1",
                "GlobalGateStatusV1",
                "R2ClosureGateReceiptV1",
                "R2ClosureGapProofV1",
                "R2FinalMasterClosureReceiptV1",
                "R2GlobalGateCoordinatorV1",
                "R2GlobalGateEvidenceV1",
                "ReviewDomainV1",
                "closure_gate_registry",
                "closure_gap_registry",
                "closure_map_fingerprint",
                "finding_classification_registry",
                "gate_evidence_registry",
            },
        )
        exported_types = {
            value
            for name in closure.__all__
            if isinstance((value := getattr(closure, name)), type)
        }
        self.assertTrue(exported_types.isdisjoint(REAL_AUTHORIZATION_TYPES))

    def test_package_is_pure_and_cannot_create_ticket_or_host_effect(self):
        allowed_absolute_imports = {
            "__future__",
            "ast",
            "dataclasses",
            "enum",
            "hashlib",
            "json",
        }
        forbidden_calls = {
            "exec",
            "eval",
            "compile",
            "__import__",
            "open",
            "print",
        }
        for path in sorted(PACKAGE.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = {
                node.module.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module is not None
            }
            imports.update(
                alias.name.split(".")[0]
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
                self.assertLessEqual(imports, allowed_absolute_imports)
                self.assertTrue(calls.isdisjoint(forbidden_calls))

    def test_normative_docs_define_the_finite_non_authorizing_contract(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "R2FinalMasterClosureReceiptV1",
                "ELIGIBLE_FOR_SINGLE_FINAL_MASTER_REVIEW",
                "exactly eight closure gaps",
                "evidence only",
            ),
            "docs/constraints/architecture_constraints.md": (
                "backend/r2_final_master_closure",
                "receipt-to-authority conversion",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 final-master closure guards",
                "fourteen gate kinds",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #86 final-master closure contract rules",
                "closed eight-value finding taxonomy",
            ),
            "docs/operations/project_structure.md": (
                "backend/r2_final_master_closure/",
                "R2FinalMasterClosureReceiptV1",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_final_master_closure_contracts.py",
                "test_r2_final_master_closure_architecture.py",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
