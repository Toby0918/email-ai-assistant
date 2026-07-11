"""Tests for analysis result schema validation."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
