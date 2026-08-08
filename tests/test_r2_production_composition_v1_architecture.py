"""Architecture guards for the three-stateful-Adapter production seam."""

import ast
import inspect
import unittest
from pathlib import Path

import backend.r2_production_composition as production_composition
from backend.r2_production_composition import (
    build_production_binding_candidate_v1,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_production_composition"


class R2ProductionCompositionV1ArchitectureTests(unittest.TestCase):
    def test_package_is_the_only_three_adapter_deep_seam(self):
        self.assertEqual(
            {path.name for path in PACKAGE.glob("*.py")},
            {
                "__init__.py",
                "adapter_binding.py",
                "binding_candidate.py",
                "catalog.py",
                "evidence.py",
                "preflight.py",
                "transaction.py",
            },
        )
        self.assertEqual(
            {
                name
                for name in production_composition.__all__
                if name in {
                    "EvidenceProductionAdapterV1",
                    "PreflightProductionAdapterV1",
                    "TransactionProductionAdapterV1",
                }
            },
            {
                "EvidenceProductionAdapterV1",
                "PreflightProductionAdapterV1",
                "TransactionProductionAdapterV1",
            },
        )
        source = "".join(
            path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
        )
        for obsolete in (
            "R2BoundProductionCallableV2",
            "bind_production_callable_v2",
            "production_callable_fingerprint_v2",
        ):
            self.assertNotIn(obsolete, source)
        for completion in (
            "complete_preflight_read_v2",
            "complete_reviewed_evidence_publication_v2",
            "complete_transaction_action_v2",
        ):
            self.assertNotIn(completion, source)

    def test_candidate_builder_has_no_arbitrary_identity_or_host_input(self):
        self.assertEqual(
            tuple(inspect.signature(build_production_binding_candidate_v1).parameters),
            ("final_master_binding",),
        )
        forbidden_parameters = {
            "operation_fingerprint",
            "operator_role_fingerprints",
            "production_role_fingerprints",
            "path",
            "root",
            "host",
            "private_key",
            "verification_public_keys",
        }
        self.assertTrue(
            set(inspect.signature(build_production_binding_candidate_v1).parameters)
            .isdisjoint(forbidden_parameters)
        )
        source = (PACKAGE / "binding_candidate.py").read_text(encoding="utf-8")
        for forbidden in (
            "Ed25519PrivateKey",
            ".sign(",
            "private_bytes",
            "PublicKeyRoleV2",
            "verification_public_keys",
            "ApprovedCutoverBindingV2",
            "DurableAuthorityClaimV2",
            "subprocess",
            "socket",
            "open(",
            "os.environ",
            "mailbox",
            "vault",
        ):
            self.assertNotIn(forbidden, source)

    def test_dormant_processes_cannot_import_or_reach_adapter_seam(self):
        packages = (
            "r2_preflight_process",
            "r2_evidence_process",
            "r2_transaction_process",
        )
        for package in packages:
            path = ROOT / "backend" / package / "production_v2.py"
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            imports = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }
            with self.subTest(package=package):
                self.assertNotIn("backend.r2_production_composition", imports)
                self.assertIn("DORMANT_NO_ISSUE39_APPROVAL", source)
                self.assertNotIn("R2BoundProductionAdapterV1", source)
                self.assertNotIn(".invoke(", source)
                self.assertNotIn("role_binding", source)


if __name__ == "__main__":
    unittest.main()
