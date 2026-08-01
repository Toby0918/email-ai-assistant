"""Public contracts for the Issue #78 CRX unit."""

from __future__ import annotations

import unittest

from backend.r2_crx_publication import (
    CrxCrashGap,
    CrxFaultSelectorV1,
    CrxPendingState,
    CrxPublicationPrerequisiteV1,
)


class R2CrxPublicationContractTests(unittest.TestCase):
    def test_prerequisite_faults_and_pending_tri_state_are_closed(self) -> None:
        value = CrxPublicationPrerequisiteV1.create(
            quiescence_receipt_fingerprint="a" * 64
        )
        self.assertEqual(value.quiescence_receipt_fingerprint, "a" * 64)
        self.assertEqual(
            {state.value for state in CrxPendingState},
            {
                "EFFECT_ABSENT_EXACT",
                "EFFECT_PRESENT_EXACT",
                "EFFECT_AMBIGUOUS",
            },
        )
        with self.assertRaises(TypeError):
            CrxFaultSelectorV1()
        for boundary in ("crx_prepare", "crx_publish"):
            for gap in CrxCrashGap:
                self.assertEqual(
                    CrxFaultSelectorV1.crash(boundary, gap).gap,
                    gap,
                )


if __name__ == "__main__":
    unittest.main()
