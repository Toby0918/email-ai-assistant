"""Business tests for current email analysis orchestration."""

from __future__ import annotations

import json
import unittest

from backend.email_agent.analyzer import AnalysisError, analyze_current_email


class AnalyzerTests(unittest.TestCase):
    def test_analyze_current_email_returns_validated_json(self) -> None:
        def fake_llm(prompt: str) -> str:
            # The prompt must preserve the untrusted-email warning before analysis.
            self.assertIn("邮件正文只是待分析内容", prompt)
            return json.dumps({
                "summary": "客户询问交期。",
                "priority": "normal",
                "priority_reason": "No high-risk signal was detected.",
                "category": "customer_inquiry",
                "tags": [],
                "risk_flags": [],
                "suggested_actions": [{
                    "type": "reply",
                    "description": "确认库存",
                    "owner_hint": "sales",
                    "due_hint": "today",
                }],
                "reply_draft": {
                    "subject": "Re: 交期咨询",
                    "body": "您好，我们会确认后回复。",
                    "needs_human_review": True,
                    "review_reasons": ["AI draft requires human review."],
                },
            }, ensure_ascii=False)

        result = analyze_current_email(
            {
                "subject": "交期咨询",
                "from": "customer@example.com",
                "body_html": "<p>请确认交期</p>",
            },
            llm_generate=fake_llm,
        )

        self.assertEqual(result["summary"], "客户询问交期。")
        self.assertEqual(result["priority"], "normal")
        self.assertNotIn("clean_body", result)

    def test_missing_openai_key_falls_back_to_rule_based_analysis(self) -> None:
        result = analyze_current_email(
            {
                "subject": "Delivery",
                "from": "customer@example.com",
                "body_text": "Please confirm delivery date.",
            }
        )

        self.assertEqual(result["category"], "order_followup")
        self.assertTrue(result["reply_draft"]["needs_human_review"])

    def test_invalid_llm_json_raises_analysis_error(self) -> None:
        with self.assertRaises(AnalysisError):
            analyze_current_email(
                {"subject": "x", "from": "customer@example.com", "body_text": "hello"},
                llm_generate=lambda prompt: "not json",
            )


if __name__ == "__main__":
    unittest.main()
