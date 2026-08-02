"""Public contract tests for the Issue #74 main-publication tracer."""

from __future__ import annotations

import unittest

from backend.r2_main_publication import (
    ExpectedInheritedDaclProjectionV1,
    MainPublicationCrashGap,
    MainPublicationRestartOutcome,
    PostMoveMainAclConformanceReceiptV1,
    PreMoveMainAclReadinessObservationV1,
)


class R2MainPublicationContractTests(unittest.TestCase):
    def test_contracts_reject_direct_or_unvalidated_construction(self) -> None:
        for contract in (
            ExpectedInheritedDaclProjectionV1,
            PreMoveMainAclReadinessObservationV1,
            PostMoveMainAclConformanceReceiptV1,
        ):
            with self.subTest(contract=contract.__name__):
                with self.assertRaises(TypeError):
                    contract()

    def test_restart_and_gap_vocabularies_are_closed(self) -> None:
        self.assertEqual(
            {item.value for item in MainPublicationRestartOutcome},
            {"SAFE_ABORT", "ROLLBACK_REQUIRED", "INCIDENT_STOP"},
        )
        self.assertEqual(
            {item.value for item in MainPublicationCrashGap},
            {
                "after_intent",
                "after_effect",
                "after_scan",
                "after_observation",
                "after_commit",
            },
        )

    def test_public_contract_repr_never_discloses_fingerprints(self) -> None:
        from backend.r2_main_publication.contracts import (
            _projection,
            _readiness,
            _receipt,
        )

        projection = _projection(
            root_dacl_fingerprint="1" * 64,
            directory_dacl_fingerprint="2" * 64,
            file_dacl_fingerprint="3" * 64,
        )
        readiness = _readiness(
            source_root_identity_fingerprint="4" * 64,
            inventory_fingerprint="5" * 64,
            object_count=7,
            observed_at_epoch=100,
            expires_at_epoch=120,
        )
        receipt = _receipt(
            projection_fingerprint=projection.projection_fingerprint,
            main_identity_fingerprint="6" * 64,
            inventory_fingerprint="7" * 64,
            journal_head_fingerprint="8" * 64,
            object_count=10,
        )

        rendered = repr((projection, readiness, receipt))
        for marker in ("1" * 64, "4" * 64, "8" * 64):
            self.assertNotIn(marker, rendered)
        self.assertEqual(receipt.status, "MAIN_PUBLISHED")
        self.assertLessEqual(
            readiness.expires_at_epoch - readiness.observed_at_epoch,
            30,
        )
        self.assertTrue(readiness.double_stable)
        self.assertTrue(readiness.single_use)
        self.assertTrue(receipt.owner_group_exact)
        self.assertTrue(receipt.dacl_whole_tree_exact)
        self.assertFalse(receipt.content_observed)


if __name__ == "__main__":
    unittest.main()
