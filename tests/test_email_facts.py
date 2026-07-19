"""Tests for deterministic email fact extraction."""

from __future__ import annotations

import unittest

from backend.email_agent.email_facts import extract_email_facts


class EmailFactsTests(unittest.TestCase):
    def test_extracts_references_quantities_issues_actions_and_deadlines(self) -> None:
        facts = extract_email_facts(
            subject="Urgent response needed - PO 10138937872 quality issue",
            sender="customer@example.test",
            clean_body=(
                "For PO 10138937872, 3,000 pcs of material 1009890-G failed inspection. "
                "The 7.21mm +/- .05 hole has burrs and is out of tolerance. "
                "Please provide RCA and corrective action within 24 hours of receipt."
            ),
        )

        self.assertIn("PO 10138937872", facts.references)
        self.assertIn("1009890-G", facts.references)
        self.assertIn("3,000 pcs", facts.quantities)
        self.assertTrue(any("burrs" in issue.lower() for issue in facts.quality_issues))
        self.assertTrue(any("out of tolerance" in issue.lower() for issue in facts.quality_issues))
        self.assertTrue(any("RCA" in action for action in facts.requested_actions))
        self.assertTrue(any("corrective action" in action.lower() for action in facts.requested_actions))
        self.assertIn("within 24 hours", facts.deadlines)

    def test_extracts_logistics_tracking_request_without_full_body_dump(self) -> None:
        facts = extract_email_facts(
            subject="Booking follow up",
            sender="logistics@example.test",
            clean_body=(
                "Please check the original FE and tracking number 5562833721. "
                "The updated draft FE is correct, kindly support original FE stamp to us asap."
            ),
        )

        joined_actions = " ".join(facts.requested_actions).lower()
        self.assertIn("tracking number 5562833721", facts.references)
        self.assertIn("original fe", joined_actions)
        self.assertIn("asap", facts.deadlines)
        self.assertLessEqual(max(len(item) for item in facts.requested_actions), 140)

    def test_extracts_labeled_moq_as_a_quantity_fact(self) -> None:
        facts = extract_email_facts(
            subject="Order planning",
            sender="buyer@example.test",
            clean_body="Best MOQ is 1200/1400 pcs.",
        )

        self.assertIn("MOQ 1200/1400 pcs", facts.quantities)

    def test_generic_iso_date_requires_due_cue_and_does_not_consume_prose_as_zone(self) -> None:
        ordinary = extract_email_facts(
            subject="Invoice update",
            sender="billing@example.test",
            clean_body="Invoice issued 2026-07-10 and shipment planning follows.",
        )
        deadline = extract_email_facts(
            subject="Reply deadline",
            sender="buyer@example.test",
            clean_body="Please reply by 2026-07-10 09:30 and shipment planning follows.",
        )

        self.assertEqual(ordinary.deadlines, [])
        self.assertIn("2026-07-10 09:30", deadline.deadlines)
        self.assertNotIn("2026-07-10 09:30 and", deadline.deadlines)

    def test_deadline_timezone_suffix_uses_explicit_valid_forms(self) -> None:
        zones = ("UTC+08:00", "GMT-04:00", "PDT", "Asia/Shanghai")
        for zone in zones:
            with self.subTest(zone=zone):
                expected = f"2026-07-10 09:30 {zone}"
                facts = extract_email_facts(
                    subject="Reply deadline",
                    sender="buyer@example.test",
                    clean_body=f"Please reply by {expected}.",
                )
                self.assertIn(expected, facts.deadlines)


if __name__ == "__main__":
    unittest.main()
