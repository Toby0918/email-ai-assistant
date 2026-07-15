"""Tests for identifier-free deterministic runtime knowledge rendering."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from backend.email_agent.private_knowledge_context import (
    MAX_KNOWLEDGE_CARDS,
    MAX_KNOWLEDGE_CHARACTERS,
    RenderedKnowledgeContext,
    _join_whole_card_payloads,
    render_private_knowledge_context,
)
from backend.private_knowledge.runtime_schema import RuntimeKnowledgeCard


def runtime_card(
    index: int,
    *,
    category: str = "order_followup",
    priority: str = "high",
    risk: str = "delivery_risk",
    action: str = "confirm",
    generic_rule: str = "check explicit deadlines before response",
    guidance: str = "ask for confirmation before making commitments",
) -> RuntimeKnowledgeCard:
    return RuntimeKnowledgeCard.from_mapping(
        {
            "schema_version": "RuntimeKnowledgeCardV1",
            "card_id": f"00000000-0000-4000-8000-{index:012d}",
            "version": 1,
            "rule_type": "classification",
            "language": "en",
            "applicability": {
                "accountability": "general",
                "direction": "any",
                "categories": [category],
            },
            "generic_rule": generic_rule,
            "normalized_signals": ["deadline_signal"],
            "enum_mapping": {
                "priorities": [priority],
                "categories": [category],
                "risks": [risk],
                "actions": [action],
            },
            "safe_reply_guidance": guidance,
        }
    )


def rule_result() -> dict[str, object]:
    return {
        "priority": "high",
        "category": "order_followup",
        "risk_flags": [{"type": "delivery_risk"}],
        "suggested_actions": [{"type": "confirm"}],
    }


class PrivateKnowledgeContextTests(unittest.TestCase):
    def test_limits_are_exact_and_whole_payload_selection_handles_4000_and_4001(self) -> None:
        self.assertEqual(MAX_KNOWLEDGE_CARDS, 8)
        self.assertEqual(MAX_KNOWLEDGE_CHARACTERS, 4_000)
        exact, exact_count = _join_whole_card_payloads(("x" * 4_000, "y"), 4_000)
        oversized, oversized_count = _join_whole_card_payloads(("x" * 4_001,), 4_000)

        self.assertEqual((len(exact), exact_count), (4_000, 1))
        self.assertNotIn("y", exact)
        self.assertEqual((oversized, oversized_count), ("", 0))

    def test_ninth_card_is_excluded_and_rendering_is_stable_across_input_order(self) -> None:
        cards = tuple(runtime_card(index) for index in range(1, 10))

        forward = render_private_knowledge_context(cards, rule_result())
        reverse = render_private_knowledge_context(tuple(reversed(cards)), rule_result())

        self.assertEqual(forward, reverse)
        self.assertEqual(forward.card_count, 8)
        self.assertLessEqual(len(forward.text), 4_000)
        self.assertEqual(len(forward.text.splitlines()), 8)

    def test_renderer_uses_only_relevant_generic_fields_and_omits_all_identifiers(self) -> None:
        selected = runtime_card(1)
        irrelevant = runtime_card(
            2,
            category="payment",
            priority="low",
            risk="payment_risk",
            action="wait",
        )

        rendered = render_private_knowledge_context((irrelevant, selected), rule_result())
        payload = json.loads(rendered.text)

        self.assertEqual(rendered.card_count, 1)
        self.assertEqual(payload["generic_rule"], selected.generic_rule)
        self.assertEqual(payload["safe_reply_guidance"], selected.safe_reply_guidance)
        forbidden = (
            "card_id", "snapshot_id", "vault_id", "schema_version", "version",
            "authority", "key_id", "path", "url", "binary", "locator",
            "placeholder", "mapping", "resolver", "restore",
        )
        lowered = rendered.text.lower()
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, lowered)
        self.assertNotIn(selected.card_id, rendered.text)
        self.assertNotIn(irrelevant.card_id, rendered.text)

    def test_directly_forged_runtime_card_fails_empty_after_defensive_revalidation(self) -> None:
        valid = runtime_card(1)
        forged = replace(valid, generic_rule="https://private.example.test/source")

        rendered = render_private_knowledge_context((valid, forged), rule_result())

        self.assertEqual(rendered, RenderedKnowledgeContext("", 0))
        self.assertNotIn("private.example.test", repr(rendered))

    def test_non_tuple_or_invalid_rule_result_fails_empty_without_exception_content(self) -> None:
        for cards, result in (([runtime_card(1)], rule_result()), ((runtime_card(1),), None)):
            with self.subTest(cards_type=type(cards).__name__, result=result):
                rendered = render_private_knowledge_context(cards, result)  # type: ignore[arg-type]
                self.assertEqual(rendered, RenderedKnowledgeContext("", 0))


if __name__ == "__main__":
    unittest.main()
