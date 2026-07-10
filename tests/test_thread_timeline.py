"""Business tests for deterministic conversation timeline construction."""

from __future__ import annotations

import unittest

from backend.email_agent.thread_timeline import build_conversation_timeline


class _TrackingText(str):
    def __new__(cls, value: str) -> "_TrackingText":
        instance = super().__new__(cls, value)
        instance.slice_stops: list[int | None] = []
        return instance

    def __getitem__(self, key: object) -> str:
        if isinstance(key, slice):
            self.slice_stops.append(key.stop)
        return super().__getitem__(key)


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

    def test_timeline_uses_chronology_when_every_timestamp_is_timezone_aware(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T11:00:00+00:00",
                "body_text": "Please confirm shipment ETA.",
            },
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T09:00:00+00:00",
                "body_text": "Please provide the product certificate.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertIn("shipment ETA", result["latest_external_request"])
        self.assertEqual(result["confidence"], "high")

    def test_timeline_preserves_dom_order_for_mixed_timezone_values(self) -> None:
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
        self.assertEqual(result["confidence"], "low")

    def test_timeline_lowers_confidence_for_all_naive_timestamps(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T09:00:00",
                "body_text": "Please provide the product certificate.",
            },
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T11:00:00",
                "body_text": "Please confirm shipment ETA.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertIn("shipment ETA", result["latest_external_request"])
        self.assertEqual(result["confidence"], "low")

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

    def test_timeline_uses_supplied_order_when_any_position_is_invalid(self) -> None:
        segments = [
            {
                "position": "not-a-position",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "not a time",
                "body_text": "Please provide the quotation.",
            },
            {
                "position": "-1",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "still not a time",
                "body_text": "Please provide the certificate.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertIn("certificate", result["latest_external_request"])
        self.assertEqual(result["confidence"], "low")

    def test_timeline_rejects_huge_position_without_throwing_or_reordering(self) -> None:
        segments = [
            {
                "position": "9" * 10_000,
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "not a time",
                "body_text": "Please provide the quotation.",
            },
            {
                "position": "0",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "still not a time",
                "body_text": "Please provide the certificate.",
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

    def test_external_commitment_language_is_not_labeled_as_internal(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "We will send the quotation request tomorrow.",
            }
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertEqual(result["latest_internal_commitment"], "")

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

    def test_outcome_resolves_only_matching_request_and_leaves_earlier_request_open(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T09:00:00+00:00",
                "body_text": "Please provide quotation RFQ-101.",
            },
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T10:00:00+00:00",
                "body_text": "Please provide the certificate for PO-202.",
            },
            {
                "position": "3",
                "from": "Sales <sales@cndlf.com>",
                "sent_at": "2026-07-10T11:00:00+00:00",
                "body_text": "PO-202 certificate has been sent and resolved.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("RFQ-101", result["latest_external_request"])
        self.assertIn("RFQ-101", result["open_items"][0]["item"])

    def test_ambiguous_outcome_does_not_resolve_independent_requests(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide the quotation.",
            },
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide the product certificate.",
            },
            {
                "position": "3",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "The request is resolved.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertIn("certificate", result["latest_external_request"])
        self.assertEqual(len(result["open_items"]), 1)

    def test_all_independent_requests_require_matching_outcomes_to_resolve(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation RFQ-101.",
            },
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide the certificate for PO-202.",
            },
            {
                "position": "3",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-101 quotation has been sent and resolved.",
            },
            {
                "position": "4",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "PO-202 certificate has been sent and resolved.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

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

    def test_header_recovers_sender_without_exposing_raw_header(self) -> None:
        segments = [
            {
                "position": "1",
                "header_text": "From: Buyer <buyer@example.com>\nTo: Sales <sales@cndlf.com>",
                "body_text": "Please provide the quotation.",
            }
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertNotIn("buyer@example.com", str(result))
        self.assertNotIn("From:", str(result))

    def test_subject_contributes_request_commitment_and_outcome_signals(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "subject": "RFQ-77 quotation request",
                "body_text": "Details attached.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "subject": "We will send RFQ-77 quotation",
                "body_text": "Noted.",
            },
            {
                "position": "3",
                "from": "Sales <sales@cndlf.com>",
                "subject": "RFQ-77 quotation resolved",
                "body_text": "Done.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertIn("RFQ-77", result["latest_external_request"])
        self.assertIn("RFQ-77", result["latest_internal_commitment"])

    def test_all_segment_fields_are_bounded_before_processing(self) -> None:
        tracked = {
            field: _TrackingText(value)
            for field, value in {
                "position": "1" * 1_000,
                "header_text": "From: Buyer <buyer@example.com>" + ("x" * 2_000),
                "from": "Buyer <buyer@example.com>" + ("x" * 2_000),
                "to": "Sales <sales@cndlf.com>" + ("x" * 2_000),
                "sent_at": "2026-07-10T09:00:00+00:00" + ("x" * 2_000),
                "timestamp_text": "2026-07-10 09:00" + ("x" * 2_000),
                "subject": "Neutral subject " + ("x" * 2_000),
                "body_text": "Neutral body " + ("x" * 25_000),
                "body_html": "<p>Neutral body</p>" + ("x" * 25_000),
            }.items()
        }

        result = build_conversation_timeline([tracked], ("cndlf.com",))

        self.assertEqual(set(result), self._timeline_keys())
        for value in tracked.values():
            self.assertTrue(value.slice_stops)

    def test_oversized_segment_list_ignores_entries_beyond_limit(self) -> None:
        segments: list[object] = [{"body_text": 7} for _ in range(50)]
        segments.append(
            {
                "position": "51",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide the quotation.",
            }
        )

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unknown")
        self.assertEqual(result["confidence"], "low")

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

    @staticmethod
    def _timeline_keys() -> set[str]:
        return {
            "previous_context",
            "current_status",
            "status_reason",
            "latest_external_request",
            "latest_internal_commitment",
            "open_items",
            "confidence",
        }


if __name__ == "__main__":
    unittest.main()
