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
                "position": "1",
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

    def test_identical_messages_at_distinct_positions_are_preserved(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please provide quotation RFQ-111.",
            },
            {
                "position": "2",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please provide quotation RFQ-111.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertIn("2条", result["previous_context"])

    def test_identical_messages_without_valid_positions_are_preserved(self) -> None:
        segments = [
            {
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please provide quotation RFQ-112.",
            },
            {
                "position": "invalid",
                "from": "Buyer <buyer@example.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "Please provide quotation RFQ-112.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

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

    def test_one_segment_tracks_quotation_and_certificate_as_atomic_requests(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide RFQ-501 quotation and certificate PART-902.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-501 quotation has been sent and resolved.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("certificate", result["latest_external_request"])
        self.assertIn("PART-902", result["latest_external_request"])
        self.assertNotIn("RFQ-501", result["latest_external_request"])
        self.assertIn("PART-902", result["open_items"][0]["item"])

    def test_clause_local_outcomes_do_not_resolve_pending_clause(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide RFQ-701 quotation and certificate PART-702.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-701 quotation completed; PART-702 certificate pending.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("PART-702", result["latest_external_request"])
        self.assertIn("阻塞", result["status_reason"])

    def test_internal_conjunction_outcomes_are_clause_local(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide RFQ-711 quotation and certificate PART-712.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-711 quotation completed and PART-712 certificate pending.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("PART-712", result["latest_external_request"])
        self.assertIn("阻塞", result["status_reason"])

    def test_internal_comma_outcomes_are_clause_local(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation RFQ-1 and certificate PART-2.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-1 quotation completed, PART-2 certificate pending.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("PART-2", result["latest_external_request"])
        self.assertIn("阻塞", result["status_reason"])

    def test_internal_contrasting_outcomes_are_clause_local(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation RFQ-1 and certificate PART-2.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-1 quotation completed but PART-2 certificate pending.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("PART-2", result["latest_external_request"])
        self.assertIn("阻塞", result["status_reason"])

    def test_chinese_contrasting_outcomes_are_clause_local(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "请提供RFQ-3报价以及PART-4证书。",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-3报价已完成但是PART-4证书待确认。",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("PART-4", result["latest_external_request"])
        self.assertIn("阻塞", result["status_reason"])

    def test_numeric_comma_without_own_evidence_adds_no_outcome(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation RFQ-5.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-5 quotation completed, quantity 1,000 units recorded.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_numeric_comma_keeps_outcome_context(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation RFQ-5.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-5 quotation for 1,000 units completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_parenthetical_commas_keep_outcome_context(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation RFQ-5.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-5 quotation, as agreed, completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_clause_with_completion_and_blocker_cannot_resolve_request(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide RFQ-801 quotation.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-801 quotation completed but pending approval.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertIn("阻塞", result["status_reason"])

    def test_punctuation_detail_clause_does_not_inherit_request_intent(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide RFQ-901 quotation. Certificate PART-902 is attached.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-901 quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_comma_detail_clause_does_not_inherit_request_intent(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": (
                    "Please provide RFQ-901 quotation, "
                    "certificate PART-902 is attached for reference"
                ),
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-901 quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_bare_comma_requested_list_keeps_inherited_intent(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide RFQ-903 quotation, certificate PART-904.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-903 quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("PART-904", result["latest_external_request"])

    def test_request_intent_does_not_flow_backward_from_later_fragment(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Quotation is completed and please provide certificate PART-922.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "PART-922 certificate completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_request_intent_flows_forward_to_conjunction_fragment(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please quote RFQ-931 and provide certificate PO-932.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-931 quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("PO-932", result["latest_external_request"])

    def test_conjunction_detail_does_not_inherit_request_intent(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": (
                    "Please provide quotation RFQ-1 and "
                    "certificate PART-2 is attached."
                ),
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-1 quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_contrasting_detail_does_not_inherit_request_intent(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": (
                    "Please provide quotation RFQ-1 but "
                    "certificate PART-2 is attached."
                ),
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-1 quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_chinese_contrasting_detail_does_not_inherit_request_intent(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "请提供RFQ-3报价但是PART-4证书已附。",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-3报价已完成。",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_bare_conjunction_requested_list_keeps_inherited_intent(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation RFQ-3 and certificate PART-4.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-3 quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "partially_resolved")
        self.assertIn("PART-4", result["latest_external_request"])

    def test_chinese_simultaneous_requests_are_tracked_separately(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "请提供RFQ-601报价，同时提供PART-602证书。",
            }
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertIn("PART-602", result["latest_external_request"])
        self.assertNotIn("RFQ-601", result["latest_external_request"])

    def test_request_atom_cap_forces_manual_review_and_low_confidence(self) -> None:
        clauses = [f"Please confirm PART-{index:03d}" for index in range(1, 16)]
        clauses.extend(
            [
                "Please provide quotation RFQ-016",
                "Please provide quotation RFQ-017",
            ]
        )
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T09:00:00+00:00",
                "body_text": "; ".join(clauses) + ".",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "sent_at": "2026-07-10T10:00:00+00:00",
                "body_text": "The quotation is completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertEqual(result["confidence"], "low")
        self.assertIn("省略", result["status_reason"])
        self.assertIn("人工复核", result["open_items"][0]["item"])

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

    def test_equivalent_subject_and_body_request_is_tracked_once(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "subject": "RFQ-10 quotation request",
                "body_text": "Please send quotation RFQ-10",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-10 quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_equivalent_topic_only_subject_and_body_request_is_tracked_once(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "subject": "Quotation request",
                "body_text": "Please provide quotation",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "Quotation completed",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_repeated_topic_only_body_requests_remain_distinct(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation. Please provide quotation.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "Quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertEqual(len(result["open_items"]), 1)

    def test_same_identity_body_requests_remain_distinct(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": (
                    "Please provide RFQ-11 quotation for product A. "
                    "Please provide RFQ-11 quotation for product B."
                ),
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "RFQ-11 quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertEqual(len(result["open_items"]), 1)

    def test_external_acknowledgement_does_not_create_request(self) -> None:
        result = build_conversation_timeline(
            [
                {
                    "position": "1",
                    "from": "Buyer <buyer@example.com>",
                    "body_text": "Thanks, we received your request and quotation",
                }
            ],
            ("cndlf.com",),
        )

        self.assertEqual(result["current_status"], "unknown")
        self.assertEqual(result["latest_external_request"], "")
        self.assertEqual(result["open_items"], [])

    def test_topic_specific_acknowledgement_does_not_create_request(self) -> None:
        result = build_conversation_timeline(
            [
                {
                    "position": "1",
                    "from": "Buyer <buyer@example.com>",
                    "body_text": "Thanks, quotation request received.",
                }
            ],
            ("cndlf.com",),
        )

        self.assertEqual(result["current_status"], "unknown")
        self.assertEqual(result["latest_external_request"], "")
        self.assertEqual(result["open_items"], [])

    def test_confirm_receipt_acknowledgement_does_not_create_request(self) -> None:
        result = build_conversation_timeline(
            [
                {
                    "position": "1",
                    "from": "Buyer <buyer@example.com>",
                    "body_text": "We confirm quotation received.",
                }
            ],
            ("cndlf.com",),
        )

        self.assertEqual(result["current_status"], "unknown")
        self.assertEqual(result["latest_external_request"], "")
        self.assertEqual(result["open_items"], [])

    def test_please_confirm_remains_a_request(self) -> None:
        result = build_conversation_timeline(
            [
                {
                    "position": "1",
                    "from": "Buyer <buyer@example.com>",
                    "body_text": "Please confirm quotation.",
                }
            ],
            ("cndlf.com",),
        )

        self.assertEqual(result["current_status"], "unresolved")
        self.assertEqual(len(result["open_items"]), 1)

    def test_topic_specific_subject_only_request_remains_valid(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "subject": "Quotation request",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "Quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_acknowledgement_sentence_does_not_hide_later_request_title(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Thanks, received. Quotation request.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "Quotation completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")
        self.assertEqual(result["open_items"], [])

    def test_threads_without_external_requests_have_unknown_status(self) -> None:
        cases = {
            "outcome_only": "RFQ-900 is resolved.",
            "blocker_only": "Unable to proceed because information is missing.",
            "commitment_only": "We will check internally tomorrow.",
            "acknowledgement_only": "Thanks, received.",
        }

        for name, body in cases.items():
            with self.subTest(name=name):
                result = build_conversation_timeline(
                    [{"from": "Staff <staff@cndlf.com>", "body_text": body}],
                    ("cndlf.com",),
                )

                self.assertEqual(result["current_status"], "unknown")
                self.assertEqual(result["open_items"], [])

        commitment = build_conversation_timeline(
            [{"from": "Staff <staff@cndlf.com>", "body_text": cases["commitment_only"]}],
            ("cndlf.com",),
        )
        self.assertIn("将跟进", commitment["latest_internal_commitment"])

    def test_external_outcome_topic_without_request_intent_is_unknown(self) -> None:
        result = build_conversation_timeline(
            [
                {
                    "from": "Buyer <buyer@example.com>",
                    "body_text": "RFQ-900 quotation is resolved.",
                }
            ],
            ("cndlf.com",),
        )

        self.assertEqual(result["current_status"], "unknown")
        self.assertEqual(result["open_items"], [])

    def test_external_completion_cannot_resolve_prior_request(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation RFQ-941.",
            },
            {
                "position": "2",
                "from": "Partner <partner@example.net>",
                "body_text": "RFQ-941 completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertEqual(len(result["open_items"]), 1)

    def test_external_pending_language_cannot_block_prior_request(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please provide quotation RFQ-942.",
            },
            {
                "position": "2",
                "from": "Partner <partner@example.net>",
                "body_text": "RFQ-942 pending.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertNotIn("阻塞", result["status_reason"])

    def test_ordinary_po_so_words_do_not_resolve_a_request(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please review the possible quotation.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "A possible solution from support is completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertNotIn("POSSIBLE", result["status_reason"].upper())
        self.assertNotIn("SOLUTION", result["status_reason"].upper())

    def test_part_identifier_with_digit_can_match_one_request(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": "Please confirm PART-204.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": "PART-204 is completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "resolved")

    def test_oversized_identifier_token_cannot_match_an_outcome(self) -> None:
        oversized_identifier = "RFQ-" + ("A" * 40) + "1"
        segments = [
            {
                "position": "1",
                "from": "Buyer <buyer@example.com>",
                "body_text": f"Please confirm {oversized_identifier}.",
            },
            {
                "position": "2",
                "from": "Sales <sales@cndlf.com>",
                "body_text": f"{oversized_identifier} is completed.",
            },
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertEqual(len(result["open_items"]), 1)

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

    def test_character_truncation_requires_manual_review(self) -> None:
        hidden_request_cases = {
            "cleaned_body": {
                "body_text": (
                    "Please provide quotation RFQ-1. "
                    + ("x" * 2_050)
                    + " Please provide certificate PO-2."
                )
            },
            "html_source": {
                "body_html": (
                    "<p>Please provide quotation RFQ-1.</p><script>"
                    + ("x" * 20_000)
                    + "</script><p>Please provide certificate PO-2.</p>"
                )
            },
        }

        for name, body_fields in hidden_request_cases.items():
            with self.subTest(name=name):
                segments = [
                    {
                        "position": "1",
                        "from": "Buyer <buyer@example.com>",
                        "sent_at": "2026-07-10T09:00:00+00:00",
                        **body_fields,
                    },
                    {
                        "position": "2",
                        "from": "Sales <sales@cndlf.com>",
                        "sent_at": "2026-07-10T10:00:00+00:00",
                        "body_text": "RFQ-1 quotation completed.",
                    },
                ]

                result = build_conversation_timeline(segments, ("cndlf.com",))

                self.assertEqual(result["current_status"], "unresolved")
                self.assertEqual(result["confidence"], "low")
                self.assertIn("人工复核", result["open_items"][0]["item"])

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
        self.assertIn("省略", result["status_reason"])
        self.assertIn("人工复核", result["open_items"][0]["item"])

    def test_segment_cap_prevents_false_full_resolution(self) -> None:
        segments: list[dict[str, str]] = []
        for index in range(1, 26):
            request_id = f"PART-{index:03d}"
            segments.extend(
                [
                    {
                        "position": str((index * 2) - 1),
                        "from": "Buyer <buyer@example.com>",
                        "sent_at": "2026-07-10T09:00:00+00:00",
                        "body_text": f"Please confirm {request_id}.",
                    },
                    {
                        "position": str(index * 2),
                        "from": "Sales <sales@cndlf.com>",
                        "sent_at": "2026-07-10T09:00:00+00:00",
                        "body_text": f"{request_id} completed.",
                    },
                ]
            )
        segments.append(
            {
                "position": "51",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T09:00:00+00:00",
                "body_text": "Please confirm PART-999.",
            }
        )

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unresolved")
        self.assertEqual(result["confidence"], "low")
        self.assertIn("省略", result["status_reason"])
        self.assertIn("人工复核", result["open_items"][0]["item"])

    def test_segment_cap_without_visible_requests_is_unknown_with_manual_review(self) -> None:
        segments = [
            {
                "position": str(index),
                "from": "Staff <staff@cndlf.com>",
                "sent_at": "2026-07-10T09:00:00+00:00",
                "body_text": "Thanks, received.",
            }
            for index in range(1, 51)
        ]
        segments.append(
            {
                "position": "51",
                "from": "Buyer <buyer@example.com>",
                "sent_at": "2026-07-10T09:00:00+00:00",
                "body_text": "Please provide quotation RFQ-999.",
            }
        )

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unknown")
        self.assertEqual(result["confidence"], "low")
        self.assertIn("省略", result["status_reason"])
        self.assertIn("人工复核", result["open_items"][0]["item"])

    def test_blocker_without_external_request_keeps_status_unknown(self) -> None:
        segments = [
            {
                "position": "1",
                "from": "Operations <ops@cndlf.com>",
                "timestamp_text": "2026-07-10 09:00",
                "body_text": "无法确认库存，待确认后才能回复。",
            }
        ]

        result = build_conversation_timeline(segments, ("cndlf.com",))

        self.assertEqual(result["current_status"], "unknown")
        self.assertEqual(result["open_items"], [])

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
