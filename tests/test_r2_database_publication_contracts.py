"""Public contract tests for the Issue #76 database slice."""

from __future__ import annotations

import unittest

from backend.r2_database_publication import (
    LegacyDatabaseCopyLeaseV1,
    QuiescencePrerequisitesV1,
    StoppedServiceReceiptV1,
)


class R2DatabasePublicationContractTests(unittest.TestCase):
    def test_prerequisites_require_three_distinct_fingerprints(self) -> None:
        values = ("1" * 64, "2" * 64, "3" * 64)
        contract = QuiescencePrerequisitesV1.create(
            preflight_fingerprint=values[0],
            evidence_fingerprint=values[1],
            fresh_gate_fingerprint=values[2],
        )
        self.assertEqual(contract.fingerprints, values)
        with self.assertRaisesRegex(ValueError, "quiescence_prerequisites_invalid"):
            QuiescencePrerequisitesV1.create(
                preflight_fingerprint=values[0],
                evidence_fingerprint=values[0],
                fresh_gate_fingerprint=values[2],
            )

    def test_receipt_and_lease_are_module_owned_nominal_capabilities(self) -> None:
        for contract in (StoppedServiceReceiptV1, LegacyDatabaseCopyLeaseV1):
            with self.subTest(contract=contract.__name__):
                with self.assertRaises(TypeError):
                    contract()
                self.assertFalse(hasattr(contract, "create"))
                self.assertFalse(hasattr(contract, "from_mapping"))


if __name__ == "__main__":
    unittest.main()
