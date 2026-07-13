"""Tests for deterministic grounding across every model-led text leaf."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from backend.email_agent.model_grounding import (
    GroundingViolation,
    find_grounding_violations,
)
from backend.email_agent.prompt_context import EvidenceSource


def valid_envelope() -> dict[str, Any]:
    return {
        "schema_version": "deepseek_analysis_v1",
        "analysis": {
            "summary": "General review.",
            "priority": "normal",
            "priority_reason": "Needs attention.",
            "category": "unknown",
            "tags": ["review"],
            "decision_brief": {
                "one_line_conclusion": "Review the request.",
                "requested_outcome": "Clarify next steps.",
                "next_steps": [
                    {
                        "step": "Review details.",
                        "owner_hint": "Sales",
                        "due_hint": "",
                        "source": "thread",
                    }
                ],
                "key_facts": [
                    {"label": "Topic", "value": "General request", "source": "thread"}
                ],
                "must_check": ["Review details."],
                "missing_info": ["More details needed."],
                "reply_recommendation": {
                    "should_reply": True,
                    "reply_type": "acknowledge",
                    "reason": "A response is appropriate.",
                },
                "confidence": "medium",
            },
            "timeline_interpretation": {
                "previous_context": "A prior exchange exists.",
                "status_reason": "The request remains open.",
                "open_item_annotations": [
                    {"open_item_id": "open:0", "item": "Review details."}
                ],
                "evidence_sources": [],
            },
            "risk_flags": [
                {
                    "type": "other",
                    "level": "low",
                    "evidence": "Potential issue.",
                    "recommendation": "Review first.",
                }
            ],
            "suggested_actions": [
                {
                    "type": "review",
                    "description": "Review the request.",
                    "owner_hint": "Sales",
                    "due_hint": "",
                }
            ],
            "reply_draft": {
                "subject": "Re: Request",
                "body": "Thank you. We will review the request.",
                "needs_human_review": True,
                "review_reasons": ["Review before sending."],
            },
        },
        "attachment_augmentations": [],
        "field_evidence": {},
    }


APPROVED_TEXT_POINTERS = (
    "/analysis/summary",
    "/analysis/priority_reason",
    "/analysis/tags/0",
    "/analysis/decision_brief/one_line_conclusion",
    "/analysis/decision_brief/requested_outcome",
    "/analysis/decision_brief/next_steps/0/step",
    "/analysis/decision_brief/next_steps/0/owner_hint",
    "/analysis/decision_brief/next_steps/0/due_hint",
    "/analysis/decision_brief/key_facts/0/label",
    "/analysis/decision_brief/key_facts/0/value",
    "/analysis/decision_brief/must_check/0",
    "/analysis/decision_brief/missing_info/0",
    "/analysis/decision_brief/reply_recommendation/reason",
    "/analysis/timeline_interpretation/previous_context",
    "/analysis/timeline_interpretation/status_reason",
    "/analysis/timeline_interpretation/open_item_annotations/0/item",
    "/analysis/risk_flags/0/evidence",
    "/analysis/risk_flags/0/recommendation",
    "/analysis/suggested_actions/0/description",
    "/analysis/suggested_actions/0/owner_hint",
    "/analysis/suggested_actions/0/due_hint",
    "/analysis/reply_draft/subject",
    "/analysis/reply_draft/body",
    "/analysis/reply_draft/review_reasons/0",
    "/attachment_augmentations/0/summary",
    "/attachment_augmentations/0/key_facts/0",
)


def set_pointer(root: dict[str, Any], pointer: str, value: str) -> None:
    current: Any = root
    tokens = pointer.removeprefix("/").split("/")
    for token in tokens[:-1]:
        current = current[int(token)] if isinstance(current, list) else current[token]
    final = tokens[-1]
    if isinstance(current, list):
        current[int(final)] = value
    else:
        current[final] = value


def add_attachment_augmentation(
    envelope: dict[str, Any],
    *,
    summary: str = "Drawing reviewed.",
    key_facts: list[str] | None = None,
    evidence_sources: list[str] | None = None,
) -> None:
    envelope["attachment_augmentations"] = [
        {
            "source_id": "attachment:0",
            "summary": summary,
            "key_facts": key_facts if key_facts is not None else [],
            "evidence_sources": (
                evidence_sources if evidence_sources is not None else ["attachment:0"]
            ),
        }
    ]


class ModelGroundingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = {
            "thread:0": EvidenceSource(
                "thread:0", "thread", "General synthetic request.", "thread"
            ),
            "thread:1": EvidenceSource(
                "thread:1",
                "thread",
                "PO 1013970520 due 2026-07-20 USD 1,250 qty 24 pcs 12 x 30 mm.",
                "thread",
            ),
            "attachment:0": EvidenceSource(
                "attachment:0",
                "attachment",
                "General synthetic drawing.",
                "attachment:synthetic.pdf",
                attachment_index=0,
                parsed=True,
            ),
        }

    def test_unsupported_critical_fact_is_checked_in_every_approved_leaf(self) -> None:
        critical = "PO 999999 completed on 2027-08-09 for USD 9,999 qty 77 pcs."

        for pointer in APPROVED_TEXT_POINTERS:
            with self.subTest(pointer=pointer):
                envelope = valid_envelope()
                if pointer.startswith("/attachment_augmentations"):
                    add_attachment_augmentation(
                        envelope, key_facts=["General drawing detail."]
                    )
                set_pointer(envelope, pointer, critical)
                source_id = (
                    "attachment:0"
                    if pointer.startswith("/attachment_augmentations")
                    else "thread:0"
                )
                field_evidence = {pointer: (source_id,)}
                if pointer.startswith("/attachment_augmentations"):
                    field_evidence = {
                        "/attachment_augmentations/0/summary": (source_id,),
                        "/attachment_augmentations/0/key_facts/0": (source_id,),
                    }
                violations = find_grounding_violations(
                    envelope,
                    field_evidence,
                    self.sources,
                )
                self.assertEqual(
                    [violation.pointer for violation in violations],
                    [pointer],
                )

    def test_supported_critical_fact_categories_normalize_against_same_source(self) -> None:
        cases = (
            ("identifier", "PO 1013970520 remains open.", "订单号: 1013970520"),
            ("amount", "Amount is RMB 1,250.00.", "CNY 1250"),
            ("date", "Due 2026-07-20.", "Deadline 2026/07/20"),
            ("quantity", "Quantity 24 pcs.", "qty: 24 PCS"),
            ("measurement", "Size is 12 x 30 mm.", "12×30 MM"),
            ("positive outcome", "RFQ-42 is completed.", "RFQ-42 completed."),
            ("negative outcome", "RFQ-42 is not completed.", "RFQ-42 not completed."),
            (
                "consequential commitment",
                "We guarantee delivery by 2026-07-20.",
                "We guarantee delivery by 2026/07/20.",
            ),
        )

        for label, model_text, grounding_text in cases:
            with self.subTest(label=label):
                envelope = valid_envelope()
                envelope["analysis"]["summary"] = model_text
                sources = dict(self.sources)
                sources["thread:0"] = EvidenceSource(
                    "thread:0", "thread", grounding_text, "thread"
                )
                self.assertEqual(
                    find_grounding_violations(
                        envelope,
                        {"/analysis/summary": ("thread:0",)},
                        sources,
                    ),
                    (),
                )

    def test_missing_or_wrong_source_evidence_is_a_violation(self) -> None:
        envelope = valid_envelope()
        envelope["analysis"]["summary"] = "PO 1013970520 requires review."

        missing = find_grounding_violations(envelope, {}, self.sources)
        wrong = find_grounding_violations(
            envelope,
            {"/analysis/summary": ("thread:0",)},
            self.sources,
        )
        supported = find_grounding_violations(
            envelope,
            {"/analysis/summary": ("thread:1",)},
            self.sources,
        )

        self.assertEqual([item.pointer for item in missing], ["/analysis/summary"])
        self.assertEqual([item.pointer for item in wrong], ["/analysis/summary"])
        self.assertEqual(supported, ())

    def test_every_claimed_source_must_support_the_same_fact(self) -> None:
        envelope = valid_envelope()
        envelope["analysis"]["summary"] = "PO 1013970520 requires review."

        violations = find_grounding_violations(
            envelope,
            {"/analysis/summary": ("thread:1", "thread:0")},
            self.sources,
        )

        self.assertEqual([item.pointer for item in violations], ["/analysis/summary"])

    def test_unknown_source_is_a_violation_even_for_noncritical_text(self) -> None:
        envelope = valid_envelope()

        violations = find_grounding_violations(
            envelope,
            {"/analysis/summary": ("unknown:PRIVATE_SOURCE",)},
            self.sources,
        )

        self.assertEqual([item.pointer for item in violations], ["/analysis/summary"])
        self.assertNotIn("PRIVATE_SOURCE", violations[0].reason)

    def test_nonparsed_attachment_cannot_support_critical_facts(self) -> None:
        envelope = valid_envelope()
        add_attachment_augmentation(envelope)
        pointer = "/attachment_augmentations/0/summary"
        set_pointer(envelope, pointer, "Part PART-302 measures 12 x 30 mm.")
        sources = dict(self.sources)
        sources["attachment:0"] = EvidenceSource(
            "attachment:0",
            "attachment",
            "Part PART-302 measures 12 x 30 mm.",
            "attachment:synthetic.pdf",
            attachment_index=0,
            parsed=False,
        )

        blocked = find_grounding_violations(
            envelope, {pointer: ("attachment:0",)}, sources
        )
        parsed = find_grounding_violations(
            envelope, {pointer: ("attachment:0",)}, self._parsed_source(sources)
        )

        self.assertEqual([item.pointer for item in blocked], [pointer])
        self.assertEqual(parsed, ())

    def test_attachment_augmentation_requires_its_own_attachment_source(self) -> None:
        envelope = valid_envelope()
        add_attachment_augmentation(envelope)
        pointer = "/attachment_augmentations/0/summary"
        fact = "Part PART-302 measures 12 x 30 mm."
        set_pointer(envelope, pointer, fact)
        sources = dict(self.sources)
        sources["thread:1"] = EvidenceSource(
            "thread:1", "thread", fact, "thread"
        )
        sources["attachment:0"] = EvidenceSource(
            "attachment:0",
            "attachment",
            fact,
            "attachment:synthetic.pdf",
            attachment_index=0,
            parsed=True,
        )

        wrong = find_grounding_violations(
            envelope, {pointer: ("thread:1",)}, sources
        )
        supported = find_grounding_violations(
            envelope, {pointer: ("attachment:0",)}, sources
        )

        self.assertEqual([item.pointer for item in wrong], [pointer])
        self.assertEqual(supported, ())

    def test_noncritical_attachment_leaf_requires_own_pointer_and_object_evidence(self) -> None:
        pointer = "/attachment_augmentations/0/summary"
        cases = (
            ("missing pointer", ["attachment:0"], {}, self.sources),
            (
                "wrong object evidence",
                ["thread:1"],
                {pointer: ("attachment:0",)},
                self.sources,
            ),
            (
                "wrong attachment",
                ["attachment:0"],
                {pointer: ("attachment:1",)},
                {
                    **self.sources,
                    "attachment:1": EvidenceSource(
                        "attachment:1",
                        "attachment",
                        "Drawing reviewed.",
                        "attachment:other.pdf",
                        attachment_index=1,
                        parsed=True,
                    ),
                },
            ),
            (
                "own source missing",
                ["attachment:0"],
                {pointer: ("attachment:0",)},
                {key: value for key, value in self.sources.items() if key != "attachment:0"},
            ),
            (
                "own source wrong kind",
                ["attachment:0"],
                {pointer: ("attachment:0",)},
                {
                    **self.sources,
                    "attachment:0": EvidenceSource(
                        "attachment:0", "thread", "Drawing reviewed.", "thread"
                    ),
                },
            ),
            (
                "own source unparsed",
                ["attachment:0"],
                {pointer: ("attachment:0",)},
                {
                    **self.sources,
                    "attachment:0": EvidenceSource(
                        "attachment:0",
                        "attachment",
                        "Drawing reviewed.",
                        "attachment:synthetic.pdf",
                        attachment_index=0,
                        parsed=False,
                    ),
                },
            ),
        )

        for label, object_evidence, field_evidence, sources in cases:
            with self.subTest(label=label):
                envelope = valid_envelope()
                add_attachment_augmentation(
                    envelope,
                    summary="Drawing reviewed.",
                    evidence_sources=object_evidence,
                )
                violations = find_grounding_violations(
                    envelope, field_evidence, sources
                )
                self.assertEqual(
                    [item.pointer for item in violations],
                    [pointer],
                )
                self.assertNotIn("Drawing reviewed", violations[0].reason)

    def test_attachment_object_evidence_cannot_override_critical_own_field_evidence(self) -> None:
        pointer = "/attachment_augmentations/0/summary"
        fact = "Part PART-302 measures 12 x 30 mm."
        envelope = valid_envelope()
        add_attachment_augmentation(
            envelope,
            summary=fact,
            evidence_sources=["thread:1"],
        )
        sources = {
            **self.sources,
            "attachment:0": EvidenceSource(
                "attachment:0",
                "attachment",
                fact,
                "attachment:synthetic.pdf",
                attachment_index=0,
                parsed=True,
            ),
        }

        violations = find_grounding_violations(
            envelope, {pointer: ("attachment:0",)}, sources
        )

        self.assertEqual([item.pointer for item in violations], [pointer])

    def test_every_noncritical_attachment_key_fact_requires_own_evidence(self) -> None:
        envelope = valid_envelope()
        add_attachment_augmentation(
            envelope,
            key_facts=["General fact one.", "General fact two."],
        )
        evidence = {
            "/attachment_augmentations/0/summary": ("attachment:0",),
            "/attachment_augmentations/0/key_facts/0": ("attachment:0",),
        }

        missing = find_grounding_violations(envelope, evidence, self.sources)
        evidence["/attachment_augmentations/0/key_facts/1"] = ("attachment:0",)
        valid = find_grounding_violations(envelope, evidence, self.sources)

        self.assertEqual(
            [item.pointer for item in missing],
            ["/attachment_augmentations/0/key_facts/1"],
        )
        self.assertEqual(valid, ())

    def test_single_value_measurement_and_chinese_negated_outcome_are_critical(self) -> None:
        cases = (
            "Weight is 24 kg.",
            "RFQ-42尚未完成。",
        )

        for text in cases:
            with self.subTest(text=text):
                envelope = valid_envelope()
                envelope["analysis"]["summary"] = text
                violations = find_grounding_violations(envelope, {}, self.sources)
                self.assertEqual(
                    [item.pointer for item in violations],
                    ["/analysis/summary"],
                )

    def test_safe_procedural_review_language_needs_no_evidence(self) -> None:
        cases = (
            "I will review the request.",
            "We will review the request.",
            "We will check delivery feasibility.",
            "We will verify the payment status.",
            "我方将审核请求。",
            "我们将审核交期。",
            "我们会核实付款状态。",
            "我们会核实一下付款状态。",
            "我方将复核当前支付状态。",
        )

        for text in cases:
            with self.subTest(text=text):
                envelope = valid_envelope()
                envelope["analysis"]["reply_draft"]["body"] = text
                self.assertEqual(
                    find_grounding_violations(envelope, {}, self.sources),
                    (),
                )

    def test_unsupported_consequential_commitment_categories_are_violations(self) -> None:
        cases = (
            "I accept the contract terms.",
            "We can guarantee quality.",
            "We will review price and confirm delivery.",
            "We guarantee the quoted price.",
            "We will deliver the order.",
            "We will pay the invoice.",
            "We accept the contract terms.",
            "We guarantee product quality.",
            "We accept legal liability.",
            "我们承诺价格。",
            "我们保证交付。",
            "我接受合同条款。",
            "我们可以保证质量。",
            "我方将审核价格并确认交付。",
        )

        for text in cases:
            with self.subTest(text=text):
                envelope = valid_envelope()
                envelope["analysis"]["reply_draft"]["body"] = text
                violations = find_grounding_violations(envelope, {}, self.sources)
                self.assertEqual(
                    [item.pointer for item in violations],
                    ["/analysis/reply_draft/body"],
                )

    def test_passive_consequential_claims_require_grounding(self) -> None:
        cases = (
            "The price is guaranteed at USD 100.",
            "Delivery is confirmed for 2026-07-20.",
            "Payment is approved.",
            "The contract is accepted.",
            "Product quality is final.",
            "The legal terms are agreed.",
            "Delivery is scheduled for 2026-07-20.",
        )
        for text in cases:
            with self.subTest(text=text):
                envelope = valid_envelope()
                envelope["analysis"]["reply_draft"]["body"] = text
                violations = find_grounding_violations(envelope, {}, self.sources)
                self.assertEqual(
                    [item.pointer for item in violations],
                    ["/analysis/reply_draft/body"],
                )

    def test_passive_requests_questions_negations_and_reviews_need_no_evidence(self) -> None:
        cases = (
            "Please confirm delivery.",
            "Customer asks whether price is final.",
            "Delivery is not confirmed.",
            "Check whether payment is approved.",
        )
        for text in cases:
            with self.subTest(text=text):
                envelope = valid_envelope()
                envelope["analysis"]["reply_draft"]["body"] = text
                self.assertEqual(
                    find_grounding_violations(envelope, {}, self.sources),
                    (),
                )

    def test_positive_and_negated_outcomes_are_not_interchangeable(self) -> None:
        envelope = valid_envelope()
        envelope["analysis"]["summary"] = "RFQ-42 is not completed."
        sources = dict(self.sources)
        sources["thread:0"] = EvidenceSource(
            "thread:0", "thread", "RFQ-42 is completed.", "thread"
        )

        violations = find_grounding_violations(
            envelope,
            {"/analysis/summary": ("thread:0",)},
            sources,
        )

        self.assertEqual([item.pointer for item in violations], ["/analysis/summary"])

    def test_outcome_negation_is_scoped_to_the_current_clause(self) -> None:
        cases = (
            ("No delay; shipment completed.", "Shipment completed."),
            ("Payment is not completed.", "Payment is not completed."),
            ("没有延误；货物已完成。", "货物已完成。"),
            ("付款尚未完成。", "付款尚未完成。"),
        )

        for model_text, grounding_text in cases:
            with self.subTest(model_text=model_text):
                envelope = valid_envelope()
                envelope["analysis"]["summary"] = model_text
                sources = dict(self.sources)
                sources["thread:0"] = EvidenceSource(
                    "thread:0", "thread", grounding_text, "thread"
                )
                self.assertEqual(
                    find_grounding_violations(
                        envelope,
                        {"/analysis/summary": ("thread:0",)},
                        sources,
                    ),
                    (),
                )

    def test_relative_deadlines_require_same_source_evidence(self) -> None:
        cases = (
            "Please reply within 3 days.",
            "Please reply within 24 hours.",
            "Please reply by Friday.",
            "请在3天内回复。",
            "请在周五前回复。",
        )

        for text in cases:
            with self.subTest(text=text):
                envelope = valid_envelope()
                envelope["analysis"]["summary"] = text
                sources = dict(self.sources)
                sources["thread:1"] = EvidenceSource(
                    "thread:1", "thread", text, "thread"
                )
                missing = find_grounding_violations(envelope, {}, sources)
                wrong = find_grounding_violations(
                    envelope,
                    {"/analysis/summary": ("thread:0",)},
                    sources,
                )
                supported = find_grounding_violations(
                    envelope,
                    {"/analysis/summary": ("thread:1",)},
                    sources,
                )
                self.assertEqual(
                    [item.pointer for item in missing], ["/analysis/summary"]
                )
                self.assertEqual(
                    [item.pointer for item in wrong], ["/analysis/summary"]
                )
                self.assertEqual(supported, ())

    def test_distinct_outcome_categories_are_not_interchangeable(self) -> None:
        envelope = valid_envelope()
        envelope["analysis"]["summary"] = "RFQ-42 was delivered."
        sources = dict(self.sources)
        sources["thread:0"] = EvidenceSource(
            "thread:0", "thread", "RFQ-42 was completed.", "thread"
        )

        violations = find_grounding_violations(
            envelope,
            {"/analysis/summary": ("thread:0",)},
            sources,
        )

        self.assertEqual([item.pointer for item in violations], ["/analysis/summary"])

    def test_violations_are_deterministic_sorted_and_never_echo_model_text(self) -> None:
        envelope = valid_envelope()
        private = "PRIVATE_MODEL_TEXT PO 999999 USD 9,999"
        envelope["analysis"]["summary"] = private
        envelope["analysis"]["reply_draft"]["body"] = private

        first = find_grounding_violations(envelope, {}, self.sources)
        second = find_grounding_violations(copy.deepcopy(envelope), {}, self.sources)

        self.assertEqual(first, second)
        self.assertEqual(
            [item.pointer for item in first],
            sorted(item.pointer for item in first),
        )
        self.assertTrue(all("PRIVATE_MODEL_TEXT" not in item.reason for item in first))

    def test_provider_owned_and_nonapproved_text_is_not_grounding_authority(self) -> None:
        envelope = valid_envelope()
        envelope["schema_version"] = "PO 999999"
        envelope["analysis"]["priority"] = "USD 9,999"
        envelope["analysis"]["decision_brief"]["next_steps"][0]["source"] = (
            "PO 999999"
        )

        self.assertEqual(find_grounding_violations(envelope, {}, self.sources), ())

    def test_grounding_violation_is_frozen_slotted_and_generic(self) -> None:
        violation = GroundingViolation("/analysis/summary", "Generic reason.")

        self.assertTrue(GroundingViolation.__dataclass_params__.frozen)
        self.assertFalse(hasattr(violation, "__dict__"))

    @staticmethod
    def _parsed_source(
        sources: dict[str, EvidenceSource],
    ) -> dict[str, EvidenceSource]:
        result = dict(sources)
        current = result["attachment:0"]
        result["attachment:0"] = EvidenceSource(
            current.source_id,
            current.kind,
            current.grounding_text,
            current.public_source,
            attachment_index=current.attachment_index,
            parsed=True,
        )
        return result


if __name__ == "__main__":
    unittest.main()
