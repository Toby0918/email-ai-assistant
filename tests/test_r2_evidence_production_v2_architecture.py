"""Static guards for the dormant evidence-production surface."""

import inspect
import unittest

from backend.r2_evidence_process.production_v2 import (
    EvidenceProductionStatusV2,
    dormant_evidence_production_v2,
    main,
    run_evidence_production_v2,
)


class R2EvidenceProductionV2ArchitectureTests(unittest.TestCase):
    def test_status_migration_has_no_envelope_or_authority_status(self):
        names = set(EvidenceProductionStatusV2.__members__)
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
            set(inspect.signature(dormant_evidence_production_v2).parameters), {"argv"}
        )
        self.assertEqual(set(inspect.signature(main).parameters), {"argv", "bootstrap"})
        parameters = set(inspect.signature(run_evidence_production_v2).parameters)
        self.assertTrue(
            parameters.isdisjoint(
                {"candidate", "claim", "path", "root", "target", "issuer", "payload"}
            )
        )


if __name__ == "__main__":
    unittest.main()
