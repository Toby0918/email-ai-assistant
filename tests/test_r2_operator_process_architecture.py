"""Issue #110 mechanical guards for physically dormant process roots."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATOR = ROOT / "backend" / "r2_operator_process"
ROOTS = tuple(
    ROOT / "backend" / name
    for name in (
        "r2_preflight_process",
        "r2_evidence_process",
        "r2_transaction_process",
    )
)
REMOVED = {
    "backend/r2_operator_process/envelope.py",
    "backend/r2_operator_process/dormant_context.py",
    "backend/r2_preflight_process/entry.py",
    "backend/r2_evidence_process/entry.py",
    "backend/r2_transaction_process/entry.py",
}


class R2OperatorProcessArchitectureTests(unittest.TestCase):
    def test_removed_authority_and_entry_surfaces_are_absent(self):
        self.assertEqual(
            {item.name for item in OPERATOR.glob("*.py")},
            {"__init__.py", "production_v2.py"},
        )
        self.assertTrue(all(not (ROOT / relative).exists() for relative in REMOVED))

    def test_each_main_imports_only_its_local_production_main(self):
        for package in ROOTS:
            tree = ast.parse((package / "__main__.py").read_text(encoding="utf-8"))
            imports = [
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ]
            with self.subTest(package=package.name):
                self.assertEqual(len(imports), 1)
                self.assertIsInstance(imports[0], ast.ImportFrom)
                self.assertEqual(imports[0].module, "production_v2")
                self.assertEqual(imports[0].level, 1)
                self.assertEqual([alias.name for alias in imports[0].names], ["main"])

    def test_roots_are_disjoint_and_contain_no_removed_trust_model(self):
        forbidden_text = (
            "ApprovedCutoverBindingV2",
            "DurableAuthorityClaimV2",
            "PublicKeyRoleV2",
            "ProductionAuthorityEnvelope",
            "AuthorizationEnvelope",
            "Ed25519",
            "verify_production_authority",
            "DORMANT_NO_EXTERNAL_ISSUER",
        )
        for package in (OPERATOR, *ROOTS):
            source = "\n".join(
                item.read_text(encoding="utf-8") for item in package.glob("*.py")
            )
            imports = _imports(package)
            with self.subTest(package=package.name):
                for forbidden in forbidden_text:
                    self.assertNotIn(forbidden, source)
                self.assertFalse(
                    {other.name for other in ROOTS if other != package} & imports
                )

    def test_executable_graph_cannot_reach_input_confirmation_or_adapter(self):
        for package in ROOTS:
            source = "\n".join(
                (package / name).read_text(encoding="utf-8")
                for name in ("__init__.py", "__main__.py", "bootstrap_v2.py", "production_v2.py")
            )
            for forbidden in (
                ".testing",
                "SystemTerminal",
                "read_acknowledgement",
                "prepare_execution_confirmation",
                "confirm_execution_confirmation",
                "append_execution_confirmation_claim",
                ".invoke(",
            ):
                with self.subTest(package=package.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)


def _imports(package: Path) -> set[str]:
    observed: set[str] = set()
    for item in package.glob("*.py"):
        for node in ast.walk(ast.parse(item.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                observed.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                observed.add(node.module)
    return observed


if __name__ == "__main__":
    unittest.main()
