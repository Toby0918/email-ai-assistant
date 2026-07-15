"""Strict KnowledgeCardV1 and non-verbatim gate tests."""

from __future__ import annotations

import unittest

from backend.private_knowledge.schema import (
    ACTION_TYPES,
    CATEGORIES,
    PRIORITIES,
    RISK_TYPES,
    KnowledgeCardV1,
    PrivateKnowledgeError,
    validate_non_verbatim,
)


def valid_card() -> dict[str, object]:
    return {
        "schema_version": "KnowledgeCardV1",
        "card_id": "11111111-2222-4333-8444-555555555555",
        "version": 1,
        "rule_type": "action",
        "language": "en",
        "applicability": {
            "accountability": "general",
            "direction": "inbound",
            "categories": ["order_followup"],
        },
        "generic_rule": "Verify current shipment status before replying.",
        "normalized_signals": ["delivery_status", "reply_requested"],
        "enum_mapping": {
            "priorities": ["normal"],
            "categories": ["order_followup"],
            "risks": ["delivery_risk"],
            "actions": ["check_delivery", "reply"],
        },
        "safe_reply_guidance": "Acknowledge the request without promising a date.",
        "evidence": {
            "conversation_bucket": "3-5",
            "counterparty_bucket": "2-3",
        },
        "privacy_check": {"status": "passed", "checked_at": "2026-07-14T12:00:00Z"},
        "review": {
            "creator": {
                "actor_ref": "actor-creator-001",
                "role": "creator",
                "approved_at": "2026-07-14T12:00:00Z",
                "card_version": 1,
            },
            "business": None,
            "privacy": None,
            "owner": None,
        },
        "lifecycle": {
            "status": "candidate",
            "created_at": "2026-07-14T12:00:00Z",
            "expires_at": "2026-08-13T12:00:00Z",
            "review_due_at": None,
        },
    }


class KnowledgeCardSchemaTests(unittest.TestCase):
    def test_exact_schema_accepts_only_bounded_enums_and_is_frozen(self) -> None:
        card = KnowledgeCardV1.from_mapping(valid_card())
        self.assertEqual(card.card_id, "11111111-2222-4333-8444-555555555555")
        self.assertEqual(card.normalized_signals, ("delivery_status", "reply_requested"))
        with self.assertRaises((AttributeError, TypeError)):
            card.version = 2  # type: ignore[misc]

        invalid = valid_card()
        invalid["unexpected"] = True
        with self.assertRaisesRegex(PrivateKnowledgeError, "schema_invalid"):
            KnowledgeCardV1.from_mapping(invalid)

    def test_local_enum_constants_match_analysis_contract_without_importing_it(self) -> None:
        self.assertEqual(PRIORITIES, {"urgent", "high", "normal", "low"})
        self.assertEqual(CATEGORIES, {
            "customer_inquiry", "order_followup", "payment", "contract",
            "complaint", "new_product_development", "internal", "marketing",
            "unknown",
        })
        self.assertEqual(RISK_TYPES, {
            "payment_risk", "delivery_risk", "contract_risk", "quality_risk",
            "security_risk", "commitment_risk", "prompt_injection_risk",
        })
        self.assertEqual(ACTION_TYPES, {
            "reply", "confirm", "prepare_quote", "check_inventory",
            "check_delivery", "escalate", "wait", "ignore",
        })

    def test_forbidden_identifiers_placeholders_exact_facts_and_profiles_are_rejected(self) -> None:
        forbidden = (
            "Email alex@example.test before replying.",
            "Use <PERSON_1> for this rule.",
            "Promise USD 1,234 on 2026-07-14.",
            "Customer profile prefers short replies.",
            "Restore the original value from the placeholder.",
            "Source hash 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.",
            "Use source record 11111111-2222-4333-8444-555555555555.",
        )
        for value in forbidden:
            mapping = valid_card()
            mapping["generic_rule"] = value
            with self.subTest(value=value), self.assertRaises(
                PrivateKnowledgeError
            ):
                KnowledgeCardV1.from_mapping(mapping)

    def test_non_verbatim_gate_rejects_latin_han_and_normalized_shared_runs(self) -> None:
        cases = (
            (
                {"generic_rule": "confirm current delivery status before making any external promise"},
                ["Please confirm current delivery status before making any external promise today."],
            ),
            ({"generic_rule": "收到询价后必须核对产品规格交期付款条件"}, ["收到询价后必须核对产品规格交期付款条件再回复"]),
            ({"generic_rule": "ABCDEF0123456789-XYZ-CONTENT"}, ["xx ABCDEF0123456789XYZCONTENT yy"]),
        )
        for content, sources in cases:
            with self.subTest(content=content), self.assertRaisesRegex(
                PrivateKnowledgeError, "verbatim_overlap"
            ):
                validate_non_verbatim(content, sources)


if __name__ == "__main__":
    unittest.main()
