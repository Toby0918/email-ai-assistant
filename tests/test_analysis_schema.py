"""Tests for analysis result schema validation."""

from __future__ import annotations

from copy import deepcopy
import unittest

from backend.email_agent.analysis_schema import AnalysisValidationError, validate_analysis_result


def valid_analysis() -> dict[str, object]:
    # Keep this sample aligned with docs/data/analysis_result_schema.md.
    return {
        "summary": "Customer asks for delivery timing.",
        "priority": "normal",
        "priority_reason": "No urgent deadline or complaint found.",
        "category": "customer_inquiry",
        "tags": ["delivery"],
        "decision_brief": {
            "one_line_conclusion": "客户要求确认交期，需要先核查订单状态再回复。",
            "requested_outcome": "对方希望获得确认后的交付日期。",
            "next_steps": [
                {
                    "step": "核查订单交付状态并准备回复。",
                    "owner_hint": "sales",
                    "due_hint": "today",
                    "source": "latest_message",
                }
            ],
            "key_facts": [
                {
                    "label": "请求",
                    "value": "确认交期",
                    "source": "latest_message",
                }
            ],
            "must_check": ["订单交付状态"],
            "missing_info": ["当前系统交付日期"],
            "reply_recommendation": {
                "should_reply": True,
                "reply_type": "provide_info",
                "reason": "客户正在等待确认后的交期信息。",
            },
            "confidence": "medium",
        },
        "conversation_timeline": {
            "previous_context": "已整理当前可见会话。",
            "current_status": "unresolved",
            "status_reason": "客户仍在等待交期确认。",
            "latest_external_request": "客户要求确认订单交期。",
            "latest_internal_commitment": "",
            "open_items": [
                {
                    "item": "核查订单交期并回复客户。",
                    "owner_hint": "sales",
                    "due_hint": "today",
                    "source": "thread",
                }
            ],
            "confidence": "medium",
        },
        "attachment_insights": [
            {
                "filename": "delivery.pdf",
                "type": "pdf",
                "status": "metadata_only",
                "summary": "PDF attachment metadata only.",
                "key_facts": [],
                "limitations": ["PDF text could not be parsed."],
            }
        ],
        "risk_flags": [
            {
                "type": "delivery_risk",
                "level": "low",
                "evidence": "Customer asks about delivery.",
                "recommendation": "Confirm the delivery estimate before replying.",
            }
        ],
        "suggested_actions": [
            {
                "type": "reply",
                "description": "Reply with confirmed delivery information.",
                "owner_hint": "sales",
                "due_hint": "today",
            }
        ],
        "reply_draft": {
            "subject": "Re: Delivery timing",
            "body": "Hello, we will confirm the delivery timing and reply shortly.",
            "needs_human_review": True,
            "review_reasons": ["AI-generated draft requires human review."],
        },
    }


def _set_nested_value(root: object, path: tuple[object, ...], value: object) -> None:
    current = root
    for key in path[:-1]:
        if isinstance(key, int) and isinstance(current, list):
            current = current[key]
        elif isinstance(key, str) and isinstance(current, dict):
            current = current[key]
        else:
            raise AssertionError(f"invalid test path: {path}")
    final = path[-1]
    if isinstance(final, int) and isinstance(current, list):
        current[final] = value
    elif isinstance(final, str) and isinstance(current, dict):
        current[final] = value
    else:
        raise AssertionError(f"invalid test path: {path}")


class AnalysisSchemaTests(unittest.TestCase):
    def test_validate_analysis_result_accepts_complete_schema(self) -> None:
        result = validate_analysis_result(valid_analysis())

        self.assertEqual(result["priority"], "normal")
        self.assertEqual(result["decision_brief"]["confidence"], "medium")

    def test_validate_analysis_result_rejects_invalid_reply_recommendation_type(self) -> None:
        analysis = valid_analysis()
        decision_brief = dict(analysis["decision_brief"])
        reply_recommendation = dict(decision_brief["reply_recommendation"])
        reply_recommendation["reply_type"] = "auto_send"
        decision_brief["reply_recommendation"] = reply_recommendation
        analysis["decision_brief"] = decision_brief

        with self.assertRaises(AnalysisValidationError):
            validate_analysis_result(analysis)

    def test_validate_analysis_result_requires_timeline_and_attachment_insights(self) -> None:
        for missing_field in ("conversation_timeline", "attachment_insights"):
            with self.subTest(missing_field=missing_field):
                analysis = valid_analysis()
                analysis.pop(missing_field)

                with self.assertRaises(AnalysisValidationError):
                    validate_analysis_result(analysis)

    def test_validate_analysis_result_rejects_invalid_attachment_status(self) -> None:
        analysis = valid_analysis()
        insight = dict(analysis["attachment_insights"][0])  # type: ignore[index]
        insight["status"] = "trusted"
        analysis["attachment_insights"] = [insight]

        with self.assertRaises(AnalysisValidationError):
            validate_analysis_result(analysis)

    def test_validate_analysis_result_rejects_invalid_timeline_source(self) -> None:
        analysis = valid_analysis()
        timeline = dict(analysis["conversation_timeline"])  # type: ignore[arg-type]
        open_item = dict(timeline["open_items"][0])  # type: ignore[index]
        open_item["source"] = "mailbox_scan"
        timeline["open_items"] = [open_item]
        analysis["conversation_timeline"] = timeline

        with self.assertRaises(AnalysisValidationError):
            validate_analysis_result(analysis)

    def test_validate_analysis_result_rejects_non_string_decision_brief_fields(self) -> None:
        paths = (
            ("decision_brief", "one_line_conclusion"),
            ("decision_brief", "requested_outcome"),
            ("decision_brief", "next_steps", 0, "step"),
            ("decision_brief", "next_steps", 0, "owner_hint"),
            ("decision_brief", "next_steps", 0, "due_hint"),
            ("decision_brief", "next_steps", 0, "source"),
            ("decision_brief", "key_facts", 0, "label"),
            ("decision_brief", "key_facts", 0, "value"),
            ("decision_brief", "key_facts", 0, "source"),
            ("decision_brief", "must_check", 0),
            ("decision_brief", "missing_info", 0),
            ("decision_brief", "reply_recommendation", "reason"),
        )
        for path in paths:
            with self.subTest(path=path):
                analysis = valid_analysis()
                _set_nested_value(analysis, path, {"not": "a string"})

                with self.assertRaises(AnalysisValidationError):
                    validate_analysis_result(analysis)

    def test_validate_analysis_result_requires_one_to_four_decision_steps(self) -> None:
        for count in (0, 5):
            with self.subTest(count=count):
                analysis = valid_analysis()
                decision_brief = analysis["decision_brief"]  # type: ignore[assignment]
                original = decision_brief["next_steps"][0]  # type: ignore[index]
                decision_brief["next_steps"] = [deepcopy(original) for _ in range(count)]  # type: ignore[index]

                with self.assertRaises(AnalysisValidationError):
                    validate_analysis_result(analysis)

    def test_validate_analysis_result_accepts_new_product_development_category(self) -> None:
        analysis = valid_analysis()
        analysis["category"] = "new_product_development"

        result = validate_analysis_result(analysis)

        self.assertEqual(result["category"], "new_product_development")

    def test_validate_analysis_result_rejects_invalid_priority(self) -> None:
        analysis = valid_analysis()
        analysis["priority"] = "medium"

        with self.assertRaises(AnalysisValidationError):
            validate_analysis_result(analysis)

    def test_validate_analysis_result_requires_human_review(self) -> None:
        analysis = valid_analysis()
        reply_draft = dict(analysis["reply_draft"])
        reply_draft["needs_human_review"] = False
        analysis["reply_draft"] = reply_draft

        with self.assertRaises(AnalysisValidationError):
            validate_analysis_result(analysis)

    def test_validate_analysis_result_rejects_non_string_public_nested_fields(self) -> None:
        paths = (
            ("tags", 0),
            ("risk_flags", 0, "evidence"),
            ("risk_flags", 0, "recommendation"),
            ("suggested_actions", 0, "description"),
            ("suggested_actions", 0, "owner_hint"),
            ("suggested_actions", 0, "due_hint"),
            ("reply_draft", "subject"),
            ("reply_draft", "body"),
            ("reply_draft", "review_reasons", 0),
        )
        for path in paths:
            with self.subTest(path=path):
                analysis = valid_analysis()
                _set_nested_value(analysis, path, {"not": "a string"})

                with self.assertRaises(AnalysisValidationError):
                    validate_analysis_result(analysis)

    def test_validate_analysis_result_preserves_valid_public_key_sets(self) -> None:
        result = validate_analysis_result(valid_analysis())

        self.assertEqual(set(result), {
            "summary", "priority", "priority_reason", "category", "tags",
            "decision_brief", "conversation_timeline", "attachment_insights",
            "risk_flags", "suggested_actions", "reply_draft",
        })
        self.assertEqual(
            set(result["risk_flags"][0]),
            {"type", "level", "evidence", "recommendation"},
        )
        self.assertEqual(
            set(result["suggested_actions"][0]),
            {"type", "description", "owner_hint", "due_hint"},
        )
        self.assertEqual(
            set(result["reply_draft"]),
            {"subject", "body", "needs_human_review", "review_reasons"},
        )


if __name__ == "__main__":
    unittest.main()
