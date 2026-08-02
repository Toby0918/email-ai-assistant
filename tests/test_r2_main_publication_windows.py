"""Physical Windows proof for the Issue #74 main-publication tracer."""

from __future__ import annotations

import sys
import unittest

from backend.cutover_host_mutation.windows_security import WindowsSecurityApi
from backend.r2_main_publication import (
    MainPublicationBoundary,
    MainPublicationCrashGap,
    MainPublicationRestartOutcome,
    MainPublicationSelectorV1,
)
from backend.r2_main_publication.testing import bind_test_main_publication
from tests.r2_main_publication_fixture import build_main_publication_scenario


@unittest.skipUnless(sys.platform == "win32", "Windows NTFS sandbox required")
class R2MainPublicationWindowsTests(unittest.TestCase):
    def test_create_only_main_detects_then_repairs_preserved_dacls(self) -> None:
        scenario = build_main_publication_scenario()
        trace = None
        try:
            trace = bind_test_main_publication(scenario, observed_at_epoch=100)
            receipt = trace.execute(MainPublicationSelectorV1.none())

            self.assertEqual(receipt.status, "MAIN_PUBLISHED")
            self.assertTrue(trace.preserved_descriptor_mismatch_detected)
            self.assertTrue(trace.whole_tree_conforms())
            self.assertTrue(trace.owner_group_exact())
            self.assertEqual(trace.main_identity, receipt.main_identity_fingerprint)
            self.assertTrue(scenario.legacy.is_dir())
            self.assertFalse(scenario.source.exists())
            self.assertTrue(scenario.main.is_dir())
            self.assertEqual(trace.last_committed_boundary, "MAIN_PUBLISHED")
        finally:
            if trace is not None:
                trace.close()
            scenario.close()

    def test_each_gap_is_classified_and_exactly_rolled_back(self) -> None:
        for boundary in MainPublicationBoundary:
            for gap in MainPublicationCrashGap:
                expected = MainPublicationRestartOutcome.ROLLBACK_REQUIRED
                if (
                    boundary is MainPublicationBoundary.LEGACY_ANCHOR_RENAME
                    and gap is MainPublicationCrashGap.AFTER_INTENT
                ):
                    expected = MainPublicationRestartOutcome.SAFE_ABORT
                with self.subTest(boundary=boundary.value, gap=gap.value):
                    self._assert_gap_rolls_back(boundary, gap, expected)

    def _assert_gap_rolls_back(self, boundary, gap, expected) -> None:
        scenario = build_main_publication_scenario()
        trace = None
        try:
            trace = bind_test_main_publication(scenario, observed_at_epoch=100)
            anchor = trace.original_anchor_identity
            baseline = trace.original_selected_security
            selector = MainPublicationSelectorV1.create(
                boundary=boundary,
                gap=gap,
            )
            with self.assertRaisesRegex(RuntimeError, "main_publication_interrupted"):
                trace.execute(selector)

            self.assertIs(trace.classify_restart(), expected)
            trace.rollback()

            self.assertEqual(trace.current_source_identity(), anchor)
            self.assertEqual(trace.current_selected_security(), baseline)
            self.assertFalse(scenario.legacy.exists())
            self.assertFalse(scenario.main.exists())
            self.assertFalse(trace.followed_reparse_point)
        finally:
            if trace is not None:
                trace.close()
            scenario.close()

    def test_owner_and_group_are_native_equal_before_and_after(self) -> None:
        scenario = build_main_publication_scenario()
        trace = None
        try:
            trace = bind_test_main_publication(scenario, observed_at_epoch=100)
            before = trace.original_selected_security
            trace.execute(MainPublicationSelectorV1.none())
            after = trace.current_managed_selected_security()
            self.assertEqual(
                tuple((item.owner_fingerprint, item.group_fingerprint)
                      for item in before),
                tuple((item.owner_fingerprint, item.group_fingerprint)
                      for item in after),
            )
            self.assertIsNotNone(WindowsSecurityApi())
        finally:
            if trace is not None:
                trace.close()
            scenario.close()

    def test_readiness_is_single_use_and_collision_is_incident_stop(self) -> None:
        scenario = build_main_publication_scenario()
        trace = None
        try:
            trace = bind_test_main_publication(scenario, observed_at_epoch=100)
            selector = MainPublicationSelectorV1.create(
                boundary=MainPublicationBoundary.LEGACY_ANCHOR_RENAME,
                gap=MainPublicationCrashGap.AFTER_EFFECT,
            )
            with self.assertRaisesRegex(
                RuntimeError, "main_publication_interrupted"
            ):
                trace.execute(selector)
            scenario.source.mkdir()

            self.assertIs(
                trace.classify_restart(),
                MainPublicationRestartOutcome.INCIDENT_STOP,
            )
            with self.assertRaisesRegex(ValueError, "rollback_ambiguous"):
                trace.rollback()
            with self.assertRaisesRegex(ValueError, "readiness_consumed"):
                trace.execute(MainPublicationSelectorV1.none())
        finally:
            if trace is not None:
                trace.close()
            scenario.close()

    def test_expired_readiness_rejects_before_the_first_intent(self) -> None:
        scenario = build_main_publication_scenario()
        trace = None
        try:
            trace = bind_test_main_publication(
                scenario,
                observed_at_epoch=100,
                _clock=lambda: 120,
            )
            with self.assertRaisesRegex(ValueError, "readiness_expired"):
                trace.execute(MainPublicationSelectorV1.none())
            self.assertTrue(scenario.source.is_dir())
            self.assertFalse(scenario.legacy.exists())
            self.assertIs(
                trace.classify_restart(),
                MainPublicationRestartOutcome.SAFE_ABORT,
            )
        finally:
            if trace is not None:
                trace.close()
            scenario.close()


if __name__ == "__main__":
    unittest.main()
