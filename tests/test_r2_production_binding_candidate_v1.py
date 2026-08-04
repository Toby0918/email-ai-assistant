"""Deterministic public production-binding candidate derivation."""

import inspect
import unittest

from backend.r2_final_master_closure import FinalMasterBindingV1
from backend.r2_final_master_closure.global_gate_registry import (
    gate_evidence_registry,
)
from backend.r2_production_binding import (
    OperatorRoleV2,
    ProductionBindingError,
    ProductionRoleV2,
    PublicKeyRoleV2,
    production_adapter_fingerprint_v1,
)
from backend.r2_production_composition import (
    build_production_binding_candidate_v1,
    production_adapter_catalog_v1,
)


class R2ProductionBindingCandidateV1Tests(unittest.TestCase):
    def test_builder_has_only_reviewed_inputs_and_is_deterministic(self):
        parameters = inspect.signature(
            build_production_binding_candidate_v1
        ).parameters
        final_master = FinalMasterBindingV1.create(
            final_commit_oid="a" * 40,
            final_tree_oid="b" * 40,
            source_package_fingerprint="c" * 64,
            runbook_fingerprint="d" * 64,
            workflow_fingerprint="e" * 64,
        )
        keys = {
            role: bytes([index + 17]) * 32
            for index, role in enumerate(PublicKeyRoleV2)
        }

        first = build_production_binding_candidate_v1(
            final_master_binding=final_master,
            verification_public_keys=keys,
        )
        second = build_production_binding_candidate_v1(
            final_master_binding=final_master,
            verification_public_keys=keys,
        )

        self.assertEqual(
            tuple(parameters),
            ("final_master_binding", "verification_public_keys"),
        )
        self.assertEqual(first, second)
        self.assertEqual(first.to_canonical_json(), second.to_canonical_json())
        self.assertEqual(
            {role for role, _value in first.operator_role_fingerprints},
            set(OperatorRoleV2),
        )
        self.assertEqual(
            {role for role, _value in first.production_role_fingerprints},
            set(ProductionRoleV2),
        )
        fingerprints = (
            *(value for _role, value in first.operator_role_fingerprints),
            *(value for _role, value in first.production_role_fingerprints),
        )
        self.assertEqual(len(fingerprints), len(set(fingerprints)))
        role_fingerprints = dict(first.production_role_fingerprints)
        for item in production_adapter_catalog_v1():
            self.assertEqual(
                role_fingerprints[item.production_role],
                production_adapter_fingerprint_v1(
                    item.command,
                    item.adapter_type,
                ),
            )

    def test_builder_rejects_duplicate_or_gate_verification_keys(self):
        final_master = FinalMasterBindingV1.create(
            final_commit_oid="a" * 40,
            final_tree_oid="b" * 40,
            source_package_fingerprint="c" * 64,
            runbook_fingerprint="d" * 64,
            workflow_fingerprint="e" * 64,
        )
        keys = {
            role: bytes([index + 17]) * 32
            for index, role in enumerate(PublicKeyRoleV2)
        }
        duplicate = dict(keys)
        duplicate[PublicKeyRoleV2.RECOVERY_VERIFICATION] = duplicate[
            PublicKeyRoleV2.EXECUTION_VERIFICATION
        ]
        reused = dict(keys)
        reused[PublicKeyRoleV2.PREFLIGHT_VERIFICATION] = (
            gate_evidence_registry()[0].verification_public_key
        )

        for candidate in (duplicate, reused):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ProductionBindingError):
                    build_production_binding_candidate_v1(
                        final_master_binding=final_master,
                        verification_public_keys=candidate,
                    )


if __name__ == "__main__":
    unittest.main()
