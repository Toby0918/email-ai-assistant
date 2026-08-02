"""Public contracts for the Issue #77 Runtime unit."""

from __future__ import annotations

import unittest

from backend.r2_runtime_publication import (
    PYTHON_VERSION,
    SQLITE_VERSION,
    RuntimeCrashGap,
    RuntimeFaultSelectorV1,
    RuntimePublicationPrerequisiteV1,
    RuntimeVerificationAuthority,
)


class R2RuntimePublicationContractTests(unittest.TestCase):
    def test_exact_versions_and_single_authority_are_canonical(self) -> None:
        self.assertEqual(PYTHON_VERSION, "3.12.13")
        self.assertEqual(SQLITE_VERSION, "3.50.4")
        self.assertEqual(
            RuntimeVerificationAuthority.CANONICAL_LOCK_SELF_VERIFICATION.value,
            "CANONICAL_LOCK_SELF_VERIFICATION_V1",
        )
        self.assertNotIn("pip", RuntimeVerificationAuthority.__members__)

    def test_prerequisite_and_fault_selector_are_closed(self) -> None:
        prerequisite = RuntimePublicationPrerequisiteV1.create(
            quiescence_receipt_fingerprint="a" * 64
        )
        self.assertEqual(prerequisite.quiescence_receipt_fingerprint, "a" * 64)
        with self.assertRaises(TypeError):
            RuntimeFaultSelectorV1()
        for boundary in ("runtime_prepare", "runtime_publish"):
            for gap in RuntimeCrashGap:
                self.assertEqual(
                    RuntimeFaultSelectorV1.crash(boundary, gap).gap,
                    gap,
                )


if __name__ == "__main__":
    unittest.main()
