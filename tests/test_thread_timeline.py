"""Business tests for deterministic conversation timeline construction."""

from __future__ import annotations

import unittest

from backend.email_agent.thread_timeline import build_conversation_timeline


class ThreadTimelineTests(unittest.TestCase):
    def test_timeline_marks_cndlf_sender_as_internal_and_latest_customer_request_open(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Sales <sales@cndlf.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "We will check the request.",
            },
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 10:00",
                "body_text": "请提供RFQ-42的报价，并在2026-07-12前回复。",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertIn("报价", result["latest_external_request"])
        self.assertEqual(result["open_items"][0]["owner_hint"], "internal_sales")
        self.assertEqual(result["open_items"][0]["due_hint"], "2026-07-12")
        self.assertEqual(result["open_items"][0]["source"], "thread")

    def test_timeline_uses_chronology_when_every_timestamp_is_reliable(self) -> None:
        segments = [
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T11:00:00",
                "body_text": "Please confirm shipment ETA.",
            },
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T09:00:00",
                "body_text": "Please provide the product certificate.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertIn("shipment ETA", result["latest_external_request"])
        self.assertEqual(result["confidence"], "high")

    def test_timeline_orders_mixed_iso_timezone_values_without_throwing(self) -> None:
        segments = [
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T11:00:00Z",
                "body_text": "Please confirm shipment ETA.",
            },
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T09:00:00",
                "body_text": "Please provide the product certificate.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertIn("shipment ETA", result["latest_external_request"])
        self.assertEqual(result["confidence"], "high")

    def test_timeline_preserves_dom_order_when_a_timestamp_is_invalid(self) -> None:
        segments = [
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "not a time",
                "body_text": "Please provide the certificate.",
            },
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please confirm the sample status.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertIn("certificate", result["latest_external_request"])
        self.assertEqual(result["confidence"], "low")

    def test_timeline_deduplicates_same_message_without_losing_distinct_messages(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please send the specification.\n> quoted history",
            },
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please send the specification.",
            },
            {
                "position": "3",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 10:00",
                "body_text": "Please provide the latest quotation.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertIn("quotation", result["latest_external_request"])
        self.assertIn("2条", result["previous_context"])

    def test_generic_acknowledgement_does_not_resolve_external_request(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please confirm the order quantity.",
            },
            {
                "position": "2",
                "from": "Support <support@CNdLf.CoM>",
                "timestamp_text": "2026-07-10 10:00",
                "body_text": "Received, we will check.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertIn("将跟进", result["latest_internal_commitment"])

    def test_explicit_outcome_resolves_request_and_surfaces_identifier(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please provide the RFQ-42 quotation.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "timestamp_text": "2026-07-10 11:00",
                "body_text": "RFQ-42 quotation has been sent and the request is resolved.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])
        self.assertIn("RFQ-42", result["status_reason"])

    def test_latest_repeated_request_stays_open_after_an_earlier_resolution(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please provide the quotation.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "timestamp_text": "2026-07-10 10:00",
                "body_text": "The quotation has been sent and the request is resolved.",
            },
            {
                "position": "3",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 11:00",
                "body_text": "Please provide the quotation.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertEqual(result["open_items"][0]["source"], "thread")

    def test_blocker_becomes_thread_open_item(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Operations <ops@cndlf.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "无法确认库存，待确认后才能回复。",
            }
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertIn("阻塞", result["status_reason"])
        self.assertEqual(result["open_items"][0]["source"], "thread")

    def test_invalid_only_input_returns_unknown_low_confidence_contract(self) -> None:
        result = build_conversation_timeline([None, "not a segment", {"body_text": 4}], ("cndlf.com",))

        self.assertEqual(
            set(result),
            {
                "previous_context",
                "current_status",
                "status_reason",
                "latest_external_request",
                "latest_internal_commitment",
                "open_items",
                "confidence",
            },
        )
        self.assertEqual(result["current_status"], "unknown")
        self.assertEqual(result["confidence"], "low")


if __name__ == "__main__":
    unittest.main()
