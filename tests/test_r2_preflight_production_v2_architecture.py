"""Static guards for the dormant six-verb preflight surface."""

import inspect
import unittest

from backend.r2_preflight_process.production_v2 import (
    PreflightProductionStatusV2,
    dormant_preflight_production_v2,
    main,
    run_preflight_production_v2,
)


class R2PreflightProductionV2ArchitectureTests(unittest.TestCase):
    def test_status_migration_has_no_envelope_or_authority_status(self):
        names = set(PreflightProductionStatusV2.__members__)
        self.assertIn("DORMANT_NO_ISSUE39_APPROVAL", names)
        self.assertTrue(
            {
                "BLOCKED_TTY",
                "BLOCKED_ACKNOWLEDGEMENT",
                "BLOCKED_EXECUTION_CONFIRMATION",
                "BLOCKED_FINGERPRINT",
                "BLOCKED_REPLAY",
                "BLOCKED_ACTION",
            }
            <= names
        )
        self.assertTrue({"BLOCKED_ENVELOPE", "BLOCKED_AUTHORITY"}.isdisjoint(names))

    def test_public_roots_have_no_confirmation_or_adapter_selector(self):
        self.assertEqual(
            set(inspect.signature(dormant_preflight_production_v2).parameters),
            {"argv"},
        )
        self.assertEqual(set(inspect.signature(main).parameters), {"argv", "bootstrap"})
        parameters = set(inspect.signature(run_preflight_production_v2).parameters)
        self.assertTrue(
            parameters.isdisjoint(
                {"candidate", "claim", "path", "root", "selector", "issuer", "payload"}
            )
        )


if __name__ == "__main__":
    unittest.main()
