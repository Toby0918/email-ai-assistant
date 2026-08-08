"""Issue #110 production reachability remains unconditionally dormant."""

import importlib
import inspect
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOTS = {
    "preflight": (("current-topology",), "read_operations=0\n"),
    "evidence": (("publish",), "published=0\n"),
    "transaction": (("execute",), "mutations=0\n"),
}


class _PoisonBootstrap:
    def __getattribute__(self, name):
        raise AssertionError(f"bootstrap became reachable: {name}")


class R2ProductionCompositionReachabilityTests(unittest.TestCase):
    def test_roots_return_issue39_dormancy_without_touching_injected_state(self):
        for root, (argv, suffix) in ROOTS.items():
            module = importlib.import_module(
                f"backend.r2_{root}_process.production_v2"
            )
            for bootstrap in (None, _PoisonBootstrap()):
                with self.subTest(root=root, injected=bootstrap is not None):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        code = module.main(argv=argv, bootstrap=bootstrap)
                    self.assertEqual(code, 0)
                    self.assertEqual(
                        output.getvalue(),
                        "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 "
                        + suffix,
                    )

    def test_public_roots_expose_no_confirmation_or_unlock_input(self):
        forbidden_parameters = {
            "terminal",
            "observed_at_epoch",
            "candidate",
            "claim",
            "acknowledgement",
            "fingerprint",
            "adapter",
            "binding",
            "issuer",
            "private_key",
        }
        for root in ROOTS:
            package = importlib.import_module(f"backend.r2_{root}_process")
            production = importlib.import_module(
                f"backend.r2_{root}_process.production_v2"
            )
            with self.subTest(root=root):
                self.assertTrue(
                    set(package.__all__).isdisjoint(
                        {
                            "ExecutionConfirmationCandidateV1",
                            "ExecutionConfirmationClaimV1",
                            "prepare_execution_confirmation_v1",
                            "confirm_execution_confirmation_v1",
                        }
                    )
                )
                self.assertTrue(
                    set(inspect.signature(production.main).parameters)
                    .isdisjoint(forbidden_parameters)
                )

    def test_production_modules_do_not_import_confirmation_primitive(self):
        for root in ROOTS:
            source = (
                ROOT / "backend" / f"r2_{root}_process" / "production_v2.py"
            ).read_text(encoding="utf-8")
            with self.subTest(root=root):
                self.assertIn("DORMANT_NO_ISSUE39_APPROVAL", source)
                self.assertNotIn("prepare_execution_confirmation_v1", source)
                self.assertNotIn("confirm_execution_confirmation_v1", source)
                self.assertNotIn("ExecutionConfirmationCandidateV1", source)


if __name__ == "__main__":
    unittest.main()
