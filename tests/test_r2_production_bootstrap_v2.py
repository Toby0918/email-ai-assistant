"""Issue #110 default-dormant production bootstrap guarantees."""

import inspect
import io
import unittest
from contextlib import redirect_stdout

from backend.r2_evidence_process.production_v2 import main as evidence_main
from backend.r2_preflight_process.production_v2 import main as preflight_main
from backend.r2_preflight_process.testing import SyntheticPreflightProductionV2
from backend.r2_production_binding import ApprovedCutoverBindingV3
from backend.r2_production_composition import (
    ProductionAdapterSlotV1,
    require_reviewed_bound_production_adapter_v1,
)
from backend.r2_transaction_process.production_v2 import main as transaction_main
from tests.test_r2_production_composition_v1 import _preflight_context


class _PoisonBootstrap:
    def __getattribute__(self, name):
        raise AssertionError(f"bootstrap became reachable: {name}")


class R2ProductionBootstrapV2Tests(unittest.TestCase):
    def test_main_surfaces_are_unconditionally_dormant_and_noninjectable(self):
        cases = (
            (preflight_main, ("current-topology",), "read_operations=0\n"),
            (evidence_main, ("publish",), "published=0\n"),
            (transaction_main, ("execute",), "mutations=0\n"),
        )
        for main, argv, suffix in cases:
            for bootstrap in (None, _PoisonBootstrap()):
                with self.subTest(main=main.__module__, injected=bootstrap is not None):
                    parameters = set(inspect.signature(main).parameters)
                    self.assertTrue(
                        parameters.isdisjoint(
                            {
                                "terminal",
                                "observed_at_epoch",
                                "binding",
                                "adapter",
                                "candidate",
                                "claim",
                            }
                        )
                    )
                    output = io.StringIO()
                    with redirect_stdout(output):
                        code = main(argv=argv, bootstrap=bootstrap)
                    self.assertEqual(code, 0)
                    self.assertEqual(
                        output.getvalue(),
                        "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 "
                        + suffix,
                    )

    def test_synthetic_adapter_marker_remains_rejected(self):
        binding, _composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        self.assertIs(type(binding), ApprovedCutoverBindingV3)
        synthetic = SyntheticPreflightProductionV2.create(
            binding=binding,
            observed_at_epoch=lambda: 2_300_000_000,
        )

        with self.assertRaises(Exception):
            require_reviewed_bound_production_adapter_v1(
                binding=binding,
                slot=ProductionAdapterSlotV1.PREFLIGHT,
                bound=synthetic._adapter,
            )


if __name__ == "__main__":
    unittest.main()
