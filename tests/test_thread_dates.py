"""Tests for deterministic deadline-cue extraction."""

from __future__ import annotations

import unittest

from backend.email_agent.thread_dates import unambiguous_due_hint


class ThreadDateTests(unittest.TestCase):
    def test_generic_iso_date_requires_deadline_cue(self) -> None:
        self.assertEqual(
            unambiguous_due_hint("Invoice issued 2026-07-10 and shipment planning follows."),
            "",
        )

    def test_generic_iso_date_with_deadline_cue_is_kept(self) -> None:
        self.assertEqual(
            unambiguous_due_hint("Please reply by 2026-07-10."),
            "2026-07-10",
        )


if __name__ == "__main__":
    unittest.main()
