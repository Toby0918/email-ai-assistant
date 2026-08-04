"""Reviewed type identity for the three stateful production adapters."""

import unittest

from backend.r2_production_binding import ProductionCommandV2
from backend.r2_production_binding._adapter_identity import (
    production_adapter_fingerprint_v1,
)
from backend.r2_production_composition import (
    PreflightProductionAdapterV1,
    ProductionAdapterSlotV1,
    bind_production_adapter_v1,
    reverify_bound_production_adapter_v1,
)
from tests.test_r2_production_composition_v1 import _preflight_context


class _ReviewedAdapter:
    __slots__ = ()

    def invoke(self, *args, **kwargs):
        return args, kwargs


class R2ProductionAdapterBindingV1Tests(unittest.TestCase):
    def test_adapter_identity_is_stable_and_command_domain_bound(self):
        topology = production_adapter_fingerprint_v1(
            ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
            _ReviewedAdapter,
        )
        publication = production_adapter_fingerprint_v1(
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            _ReviewedAdapter,
        )

        self.assertEqual(
            production_adapter_fingerprint_v1(
                ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
                _ReviewedAdapter,
            ),
            topology,
        )
        self.assertNotEqual(topology, publication)
        self.assertEqual(len(topology), 64)

    def test_reviewed_adapter_binding_reverifies_exact_type_and_slot(self):
        binding, composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        adapter = PreflightProductionAdapterV1.create(
            binding=binding,
            composition=composition,
            evidence_publication_receipt=None,
            recovery_receipt=None,
        )

        bound = bind_production_adapter_v1(binding=binding, adapter=adapter)

        self.assertIs(
            reverify_bound_production_adapter_v1(
                binding=binding,
                slot=ProductionAdapterSlotV1.PREFLIGHT,
                bound=bound,
            ),
            bound,
        )
        with self.assertRaises(Exception):
            reverify_bound_production_adapter_v1(
                binding=binding,
                slot=ProductionAdapterSlotV1.EVIDENCE,
                bound=bound,
            )


if __name__ == "__main__":
    unittest.main()
