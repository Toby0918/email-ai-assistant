"""Production graph contraction and reachability contract for Issue #91."""

from __future__ import annotations

import ast
import importlib
import inspect
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOTS = {
    "preflight": ("current-topology",),
    "evidence": ("publish",),
    "transaction": ("execute",),
}


class R2ProductionCompositionReachabilityTests(unittest.TestCase):
    def test_executable_roots_boot_only_v2_no_issuer_dormancy(self):
        for root, argv in ROOTS.items():
            package = ROOT / "backend" / f"r2_{root}_process"
            entry = (package / "__main__.py").read_text(encoding="utf-8")
            with self.subTest(root=root):
                self.assertIn("from .production_v2 import main", entry)
                self.assertNotIn("from .entry import", entry)
                self.assertNotIn("testing", entry)
                module = importlib.import_module(
                    f"backend.r2_{root}_process.production_v2"
                )
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = module.main(argv=argv)
                self.assertEqual(exit_code, 0)
                self.assertEqual(
                    output.getvalue(),
                    "DORMANT_NO_EXTERNAL_ISSUER accepted=0 rejected=0 "
                    + ("read_operations=0\n" if root == "preflight" else "published=0\n" if root == "evidence" else "mutations=0\n"),
                )

    def test_public_packages_export_only_verifier_side_v2_reachability(self):
        expected = {
            "preflight": {
                "PreflightProductionBootstrapV2",
                "dormant_preflight_production_v2",
                "run_preflight_production_v2",
            },
            "evidence": {
                "EvidenceProductionBootstrapV2",
                "dormant_evidence_production_v2",
                "run_evidence_production_v2",
            },
            "transaction": {
                "TransactionProductionBootstrapV2",
                "dormant_transaction_production_v2",
                "run_transaction_production_v2",
            },
        }
        for root, names in expected.items():
            package = importlib.import_module(f"backend.r2_{root}_process")
            production = importlib.import_module(
                f"backend.r2_{root}_process.production_v2"
            )
            with self.subTest(root=root):
                self.assertTrue(names.issubset(package.__all__))
                self.assertTrue(
                    set(package.__all__).isdisjoint(
                        {
                            "PreflightProductionRolesV2",
                            "EvidenceProductionRoleV2",
                            "TransactionProductionRolesV2",
                        }
                    )
                )
                parameters = set(
                    inspect.signature(
                        getattr(production, f"run_{root}_production_v2")
                    ).parameters
                )
                self.assertTrue(
                    parameters.isdisjoint(
                        {
                            "issuer",
                            "private_key",
                            "synthetic_context",
                            "test_binder",
                            "real_locked",
                        }
                    )
                )

    def test_production_import_graph_excludes_obsolete_locks_and_test_binders(self):
        for root in ROOTS:
            package = ROOT / "backend" / f"r2_{root}_process"
            paths = (package / "__main__.py", package / "production_v2.py")
            source = "".join(path.read_text(encoding="utf-8") for path in paths)
            imports = set()
            for path in paths:
                tree = ast.parse(path.read_text(encoding="utf-8"))
                imports.update(
                    node.module
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module
                )
            with self.subTest(root=root):
                self.assertNotIn("BLOCKED_NO_APPROVED_COMMAND", source)
                self.assertNotIn("real_locked", source)
                self.assertFalse(
                    any(
                        value.endswith((".entry", ".testing"))
                        or value in {"entry", "testing"}
                        for value in imports
                    )
                )

    def test_all_bootstraps_use_the_exact_receipt_revalidator(self):
        for root in ROOTS:
            source = (
                ROOT / "backend" / f"r2_{root}_process" / "bootstrap_v2.py"
            ).read_text(encoding="utf-8")
            with self.subTest(root=root):
                self.assertIn(
                    "require_reviewed_production_binding_receipt_v2(", source
                )

    def test_normative_docs_pin_obsolete_lock_contraction(self):
        expected = {
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #104 stateful Adapter binding remediation",
                "old ten-callback role seam is removed",
                "Production bootstraps reject synthetic bindings",
            ),
            "docs/constraints/architecture_constraints.md": (
                "Issue #104 production Adapter binding remediation",
                "stateful Adapter slots: preflight",
            ),
            "docs/constraints/linter_constraints.md": (
                "Issue #104 production Adapter guards",
                "complete owning-module source",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #104 production Adapter rules",
                "fourteen gate keys",
            ),
            "docs/operations/project_structure.md": (
                "Issue #104 V2 process-root Adapter reachability",
                "removed callback-role seam",
            ),
            "docs/operations/testing_checklist.md": (
                "Issue #104 production Adapter binding remediation",
                "test_r2_production_adapter_binding_v1.py",
            ),
        }
        for relative, phrases in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
