"""Reviewed type identity for the three stateful production adapters."""

import types
import unittest

from backend.r2_production_binding import ProductionCommandV2
from backend.r2_production_binding.errors import ProductionBindingError
from backend.r2_production_binding._adapter_identity import (
    _adapter_type_surface_digest_v1,
    _snapshot_adapter_type_surface_v1,
    production_adapter_fingerprint_v1,
)
from backend.r2_production_composition import catalog as adapter_catalog
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


def _metadata_preserving_clone(function):
    substituted_globals = dict(function.__globals__)
    substituted_globals["require_adapter_context_v1"] = lambda *args: None
    clone = types.FunctionType(
        function.__code__,
        substituted_globals,
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    clone.__kwdefaults__ = function.__kwdefaults__
    clone.__annotations__ = dict(function.__annotations__)
    clone.__dict__.update(function.__dict__)
    clone.__qualname__ = function.__qualname__
    clone.__module__ = function.__module__
    return clone


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

    def test_live_adapter_surface_substitution_fails_before_action(self):
        binding, composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        adapter = PreflightProductionAdapterV1.create(
            binding=binding,
            composition=composition,
            evidence_publication_receipt=None,
            recovery_receipt=None,
        )
        bound = bind_production_adapter_v1(binding=binding, adapter=adapter)
        original = PreflightProductionAdapterV1.invoke
        self.addCleanup(
            setattr,
            PreflightProductionAdapterV1,
            "invoke",
            original,
        )

        PreflightProductionAdapterV1.invoke = _metadata_preserving_clone(original)

        with self.assertRaisesRegex(
            ProductionBindingError,
            "R2_PRODUCTION_BINDING_INVALID",
        ):
            reverify_bound_production_adapter_v1(
                binding=binding,
                slot=ProductionAdapterSlotV1.PREFLIGHT,
                bound=bound,
            )

    def test_prebinding_live_adapter_surface_substitution_is_rejected(self):
        binding, composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        original = PreflightProductionAdapterV1.invoke
        self.addCleanup(
            setattr,
            PreflightProductionAdapterV1,
            "invoke",
            original,
        )
        PreflightProductionAdapterV1.invoke = _metadata_preserving_clone(original)
        adapter = PreflightProductionAdapterV1.create(
            binding=binding,
            composition=composition,
            evidence_publication_receipt=None,
            recovery_receipt=None,
        )

        with self.assertRaisesRegex(
            ProductionBindingError,
            "R2_PRODUCTION_BINDING_INVALID",
        ):
            bind_production_adapter_v1(binding=binding, adapter=adapter)

    def test_registry_rebinding_cannot_rebaseline_adapter_substitution(self):
        binding, composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        original_invoke = PreflightProductionAdapterV1.invoke
        original_registry = adapter_catalog._REVIEWED_ADAPTER_SURFACES
        self.addCleanup(
            setattr,
            PreflightProductionAdapterV1,
            "invoke",
            original_invoke,
        )
        self.addCleanup(
            setattr,
            adapter_catalog,
            "_REVIEWED_ADAPTER_SURFACES",
            original_registry,
        )
        PreflightProductionAdapterV1.invoke = _metadata_preserving_clone(
            original_invoke
        )
        adapter_catalog._REVIEWED_ADAPTER_SURFACES = tuple(
            (
                adapter_type,
                _snapshot_adapter_type_surface_v1(adapter_type),
                _adapter_type_surface_digest_v1(adapter_type),
            )
            for adapter_type, _surface, _digest in original_registry
        )
        adapter = PreflightProductionAdapterV1.create(
            binding=binding,
            composition=composition,
            evidence_publication_receipt=None,
            recovery_receipt=None,
        )

        with self.assertRaisesRegex(
            ProductionBindingError,
            "R2_PRODUCTION_BINDING_INVALID",
        ):
            bind_production_adapter_v1(binding=binding, adapter=adapter)

    def test_bound_invocation_target_substitution_fails_before_action(self):
        binding, composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        adapter = PreflightProductionAdapterV1.create(
            binding=binding,
            composition=composition,
            evidence_publication_receipt=None,
            recovery_receipt=None,
        )
        bound = bind_production_adapter_v1(binding=binding, adapter=adapter)

        def substituted_invoke(*args, **kwargs):
            raise AssertionError("substituted invocation target executed")

        object.__setattr__(bound, "_invoke", substituted_invoke)

        with self.assertRaisesRegex(
            ProductionBindingError,
            "R2_PRODUCTION_BINDING_INVALID",
        ):
            reverify_bound_production_adapter_v1(
                binding=binding,
                slot=ProductionAdapterSlotV1.PREFLIGHT,
                bound=bound,
            )


if __name__ == "__main__":
    unittest.main()
