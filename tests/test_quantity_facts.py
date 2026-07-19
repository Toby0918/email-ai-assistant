from __future__ import annotations

import unittest

from backend.email_agent.quantity_facts import (
    has_final_labeled_quantity_statement,
    labeled_quantity_candidate_occurrences,
    labeled_quantity_facts,
    labeled_quantity_occurrences,
)


class LabeledQuantityFactsTests(unittest.TestCase):
    def test_candidates_mark_only_invalid_labeled_moq_forms(self) -> None:
        valid = labeled_quantity_candidate_occurrences("MOQ 1200/1400 pcs")
        invalid = labeled_quantity_candidate_occurrences("MOQ 1200/1400 boxes")
        unitless_alternatives = labeled_quantity_candidate_occurrences("MOQ 1200/1400")
        unitless_member = labeled_quantity_candidate_occurrences("MOQ 1200")

        self.assertEqual(1, len(valid))
        self.assertIsNotNone(valid[0].fact)
        for candidates in (invalid, unitless_alternatives, unitless_member):
            with self.subTest(candidates=candidates):
                self.assertEqual(1, len(candidates))
                self.assertIsNone(candidates[0].fact)

    def test_labeled_occurrences_keep_their_original_spans(self) -> None:
        text = "Best MOQ is 1200/1400 pcs. Quantity: 1200 pcs."

        occurrences = labeled_quantity_occurrences(text)

        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0].fact.display, "MOQ 1200/1400 pcs")
        self.assertEqual(
            text[occurrences[0].start:occurrences[0].end],
            "Best MOQ is 1200/1400 pcs",
        )

    def test_strict_labeled_moq_slash_alternatives_are_canonicalized(self) -> None:
        facts = labeled_quantity_facts("Best MOQ is 1,200 / 1400 pcs.")

        self.assertEqual(("MOQ 1200/1400 pcs",), tuple(item.display for item in facts))
        self.assertEqual(
            ("quantity:moq:1200/1400", "quantity:moq-unit:1200/1400:pcs"),
            facts[0].signatures,
        )

    def test_only_labeled_final_values_in_the_same_clause_are_accepted(self) -> None:
        accepted = (
            "minimum order quantity: 1200 units;",
            "MOQ = 1200 sets.",
            "最低起订量：1200 件。",
        )
        rejected = (
            "1200/1400",
            "2026/07/17",
            "ratio 1/2",
            "+86 1200 1400",
            "MOQ 1200/1400 is pending confirmation.",
            "MOQ 1200 pcs, subject to confirmation.",
            "Best regards, MOQ 1200 pcs",
            "Price table: MOQ 1200 pcs | USD 10",
            "MOQ: 1200",
        )

        for text in accepted:
            with self.subTest(text=text):
                self.assertTrue(labeled_quantity_facts(text))
        for text in rejected:
            with self.subTest(text=text):
                self.assertEqual((), labeled_quantity_facts(text))

    def test_pending_moq_is_not_a_final_statement(self) -> None:
        self.assertFalse(
            has_final_labeled_quantity_statement(
                "MOQ 1200/1400 pcs is pending confirmation."
            )
        )

    def test_labeled_moq_in_contact_or_signature_clause_is_rejected(self) -> None:
        for text in (
            "Phone: +86 13900000000 MOQ 1200 pcs",
            "Phone +86 13900000000 MOQ 1200 pcs",
            "Mobile: +86 13900000000 MOQ 1200 pcs",
            "Email: contact@example.test MOQ 1200 pcs",
            "WeChat: https://example.test/contact MOQ 1200 pcs",
        ):
            with self.subTest(text=text):
                self.assertEqual((), labeled_quantity_facts(text))

    def test_compact_quotation_line_with_currency_and_amount_is_rejected(self) -> None:
        for text in (
            "MOQ 1200 pcs USD 10",
            "MOQ 1200 pcs $10.00",
            "MOQ 1200 pcs EUR 10.50",
        ):
            with self.subTest(text=text):
                self.assertEqual((), labeled_quantity_facts(text))

    def test_narrative_price_after_moq_is_not_treated_as_a_quotation_row(self) -> None:
        facts = labeled_quantity_facts("MOQ is 1200 pcs and price is USD 10.")

        self.assertEqual(("MOQ 1200 pcs",), tuple(item.display for item in facts))


if __name__ == "__main__":
    unittest.main()
