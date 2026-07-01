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
