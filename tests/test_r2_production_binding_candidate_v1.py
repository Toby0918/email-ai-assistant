"""Deterministic public production-binding V3 candidate derivation."""

import inspect
import unittest

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    OperatorRoleV2,
    ProductionBindingError,
    ProductionRoleV2,
    production_adapter_fingerprint_v1,
)
from backend.r2_production_composition import (
    build_production_binding_candidate_v1,
    production_adapter_catalog_v1,
)
from tests.r2_execution_confirmation_fixture import final_master_binding


class R2ProductionBindingCandidateV1Tests(unittest.TestCase):
    def test_builder_has_only_frozen_final_master_input_and_is_deterministic(self):
        parameters = inspect.signature(
            build_production_binding_candidate_v1
        ).parameters
        final_master = final_master_binding()

        first = build_production_binding_candidate_v1(
            final_master_binding=final_master,
        )
        second = build_production_binding_candidate_v1(
            final_master_binding=final_master,
        )

        self.assertEqual(tuple(parameters), ("final_master_binding",))
        self.assertIs(type(first), ApprovedCutoverBindingV3)
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

    def test_builder_changes_with_frozen_master_and_rejects_forged_input(self):
        first = build_production_binding_candidate_v1(
            final_master_binding=final_master_binding(commit="a" * 40),
        )
        second = build_production_binding_candidate_v1(
            final_master_binding=final_master_binding(commit="f" * 40),
        )

        self.assertNotEqual(first.binding_fingerprint, second.binding_fingerprint)
        with self.assertRaisesRegex(
            ProductionBindingError,
            "R2_PRODUCTION_BINDING_INVALID",
        ):
            build_production_binding_candidate_v1(
                final_master_binding=object(),
            )


if __name__ == "__main__":
    unittest.main()
