"""Task 4B regressions for deterministic current-email facts."""

from __future__ import annotations

import unittest

from backend.email_agent.email_facts import extract_email_facts
from backend.email_agent.rule_analyzer import build_rule_based_analysis


class EmailFactHygieneTests(unittest.TestCase):
    def test_order_words_without_numeric_structure_are_not_references(self) -> None:
        facts = extract_email_facts(
            "PO position and PO potential",
            "sender@example.test",
            "please confirm the label position and potential options.",
        )

        self.assertEqual(facts.references, [])

    def test_valid_synthetic_order_formats_are_still_references(self) -> None:
        facts = extract_email_facts(
            "PO-ABCD1234",
            "sender@example.test",
            "please confirm order number 8123456 and RFQ No. 11467.",
        )

        combined = " ".join(facts.references)
        self.assertIn("ABCD1234", combined)
        self.assertIn("8123456", combined)
        self.assertIn("11467", combined)

    def test_requests_split_on_newline_english_chinese_period_and_semicolon(self) -> None:
        facts = extract_email_facts(
            "synthetic request",
            "sender@example.test",
            (
                "Please confirm delivery\n"
                "Kindly provide certificate;请回复测试状态。"
                "Please check inventory；请确认包装。"
            ),
        )

        self.assertEqual(
            facts.requested_actions,
            [
                "Please confirm delivery",
                "Kindly provide certificate",
                "请回复测试状态",
                "Please check inventory",
                "请确认包装",
            ],
        )

    def test_signature_contacts_image_caption_and_quoted_history_do_not_enter_facts(self) -> None:
        body = (
            "Please investigate the damaged sample.\n"
            "Best regards,\n"
            "Synthetic Seller\n"
            "Mobile: +86 178 5555 1234\n"
            "Email: seller@example.test\n"
            "Website: https://example.test\n"
            "cid:image001.png\n"
            "From: old@example.test\n"
            "Please confirm old invoice INV-OLD1234."
        )

        facts = extract_email_facts("quality issue", "sender@example.test", body)
        result = build_rule_based_analysis("quality issue", "sender@example.test", body)
        serialized = str(result)

        self.assertEqual(facts.requested_actions, ["Please investigate the damaged sample"])
        self.assertEqual(facts.references, [])
        for forbidden in (
            "+86 178", "seller@example.test", "https://example.test",
            "image001", "INV-OLD1234", "old invoice",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
