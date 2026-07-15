from __future__ import annotations

import unittest

from backend.email_agent.model_exact_fact_safety import (
    contains_model_authored_exact_fact,
)


class ModelExactFactSafetyTests(unittest.TestCase):
    def test_exact_identifiers_and_dates_are_detected_in_nested_values(self) -> None:
        cases = (
            {"summary": "Please review PO-FAKE9999."},
            {"items": ["Invoice INV-2026-001 needs review."]},
            "Please review PO1234.",
            "Please review POAB1234.",
            "Please review PO/ABC123.",
            "Please review PO_AB123.",
            "Please review PO.AB123.",
            "Please review PO=AB123.",
            "Please review PO No. 123.",
            "Please review PO ID ABC123.",
            "Please review PO Ref. ABC123.",
            "Please review PO (No. ABC123).",
            "Please review INV2026001.",
            "Please review INVABC2026.",
            "Please review PN1234.",
            "Please review PNAB12.",
            "Please review RFQ-1234.",
            "Please review RFQABC123.",
            "Please review contract ABC123.",
            "Please review contract/ABC123.",
            "Please review order/AB123.",
            "Please review order_AB123.",
            "Please review order ID ABC123.",
            "Please review order reference ABC123.",
            "Please review order (1234).",
            "Please review order (#1234).",
            "Please review invoice/AB123.",
            "Please review part/AB123.",
            "Please review tracking/AB123.",
            "Please review transaction/AB123.",
            "Please review order 1234.",
            "Please review part AB12.",
            "Please review order number 2.",
            "\u8ba2\u5355\u53f7\uff1aAB1234",
            "\u8ba2\u5355\u53f7/AB1234",
            "2026-08-31",
            "2026-08-31T10:30:00Z",
            "2026-08-31T10:30:00+08:00",
            "31/08/2026",
            "2026\u5e748\u670831\u65e5",
            "2026\u5e748\u670831\u53f7",
            "August 31, 2026",
            "31 August 2026",
            "31-Aug-2026",
            "Aug-31-2026",
            "Aug. 31, 2026",
            "31 Aug. 2026",
            "Sept. 30, 2026",
        )
        for value in cases:
            with self.subTest(value=value):
                self.assertTrue(contains_model_authored_exact_fact(value))

    def test_generic_semantics_and_relative_timing_remain_usable(self) -> None:
        cases = (
            "Please review the order status.",
            "Please review order 2 samples.",
            "Please read part 2 of the document.",
            "The policy2026 update is generic text.",
            "The Policy2026 update is generic text.",
            "Please review order (2 samples).",
            "Please read part (2 of the document).",
            "Please review order. 2 samples.",
            "Please review order 1000 samples.",
            "Please review order 1000 boxes.",
            "Please review order 1000 kg.",
            "Please review tracking 2026 results.",
            "Please review PO. 2 samples.",
            "Please review PO (2 samples).",
            "Use a purchase reference and a stated date.",
            "Please check delivery by Friday.",
            {"evidence_sources": ["thread:0", "attachment:1"]},
            ["customer_inquiry", "order_followup"],
        )
        for value in cases:
            with self.subTest(value=value):
                self.assertFalse(contains_model_authored_exact_fact(value))

    def test_excessive_nesting_fails_closed(self) -> None:
        value: object = "generic"
        for _index in range(34):
            value = [value]
        self.assertTrue(contains_model_authored_exact_fact(value))


if __name__ == "__main__":
    unittest.main()
