"""Tests for local SQLite analysis persistence."""

from __future__ import annotations

import json
import sqlite3
import unittest

from backend.email_agent.database import initialize_schema, save_analysis


class DatabaseTests(unittest.TestCase):
    def test_save_analysis_persists_structured_result(self) -> None:
        connection = sqlite3.connect(":memory:")
        initialize_schema(connection)

        saved_id = save_analysis(
            connection,
            subject="Delivery",
            sender="customer@example.com",
            analysis={"summary": "Customer asks about delivery."},
        )

        row = connection.execute(
            "SELECT id, subject, sender, analysis_json FROM email_analysis"
        ).fetchone()
        self.assertEqual(row[0], saved_id)
        self.assertEqual(row[1], "Delivery")
        self.assertEqual(row[2], "customer@example.com")
        self.assertIn("Customer asks about delivery.", row[3])

    def test_save_analysis_does_not_persist_clean_email_body(self) -> None:
        connection = sqlite3.connect(":memory:")
        initialize_schema(connection)

        save_analysis(
            connection,
            subject="Delivery",
            sender="customer@example.com",
            analysis={
                "summary": "Customer asks about delivery.",
                "clean_body": "Please confirm the confidential delivery date.",
            },
        )

        stored_json = connection.execute(
            "SELECT analysis_json FROM email_analysis"
        ).fetchone()[0]
        self.assertNotIn("clean_body", stored_json)
        self.assertNotIn("confidential delivery date", stored_json)

    def test_save_analysis_projects_attachment_insights_and_unknown_top_level_fields(self) -> None:
        connection = sqlite3.connect(":memory:")
        initialize_schema(connection)

        save_analysis(
            connection,
            subject="RFQ 42",
            sender="customer@example.test",
            analysis={
                "summary": "客户请求审阅 RFQ 42。",
                "attachment_insights": [{
                    "filename": "request.pdf",
                    "type": "pdf",
                    "status": "parsed",
                    "summary": "PDF: RFQ 42.",
                    "key_facts": ["RFQ 42"],
                    "limitations": [],
                    "path": "C:/private/request.pdf",
                    "raw_text": "RAW_ATTACHMENT_SECRET",
                    "private_url": "https://mail.example.test/private-download",
                    "cookie": "SESSION_COOKIE_SECRET",
                    "token": "PRIVATE_TOKEN_SECRET",
                }],
                "raw_attachment_text": "TOP_LEVEL_ATTACHMENT_SECRET",
                "private_download_url": "https://mail.example.test/private-top-level",
                "mailbox_token": "TOP_LEVEL_TOKEN_SECRET",
            },
        )

        stored_json = connection.execute(
            "SELECT analysis_json FROM email_analysis"
        ).fetchone()[0]
        stored = json.loads(stored_json)
        self.assertEqual(set(stored), {"summary", "attachment_insights"})
        self.assertEqual(
            set(stored["attachment_insights"][0]),
            {"filename", "type", "status", "summary", "key_facts", "limitations"},
        )
        for secret in (
            "C:/private/request.pdf",
            "RAW_ATTACHMENT_SECRET",
            "private-download",
            "SESSION_COOKIE_SECRET",
            "PRIVATE_TOKEN_SECRET",
            "TOP_LEVEL_ATTACHMENT_SECRET",
            "private-top-level",
            "TOP_LEVEL_TOKEN_SECRET",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, stored_json)

    def test_save_analysis_recursively_projects_every_nested_schema_object(self) -> None:
        connection = sqlite3.connect(":memory:")
        initialize_schema(connection)
        analysis = {
            "summary": "客户请求确认交付。",
            "priority": "normal",
            "priority_reason": "需要内部核查。",
            "category": "order_followup",
            "tags": ["delivery"],
            "decision_brief": {
                "one_line_conclusion": "核查后回复。",
                "requested_outcome": "确认交付。",
                "next_steps": [{
                    "step": "核查交付。", "owner_hint": "sales", "due_hint": "today",
                    "source": "latest_message", "token": "STEP_PRIVATE_TOKEN",
                }],
                "key_facts": [{
                    "label": "PO", "value": "PO 42", "source": "latest_message",
                    "path": "C:/private/key-fact",
                }],
                "must_check": ["交期"],
                "missing_info": ["库存"],
                "reply_recommendation": {
                    "should_reply": True, "reply_type": "provide_info", "reason": "需回复。",
                    "private_url": "https://private.example/recommendation",
                },
                "confidence": "medium",
                "raw": "DECISION_RAW_SECRET",
            },
            "conversation_timeline": {
                "previous_context": "客户此前询问。",
                "current_status": "unresolved",
                "status_reason": "仍待确认。",
                "latest_external_request": "请确认交付。",
                "latest_internal_commitment": "销售将核查。",
                "open_items": [{
                    "item": "核查交付", "owner_hint": "sales", "due_hint": "today",
                    "source": "thread", "private_url": "https://private.example/timeline",
                }],
                "confidence": "medium",
                "token": "TIMELINE_PRIVATE_TOKEN",
            },
            "attachment_insights": [],
            "risk_flags": [{
                "type": "delivery_risk", "level": "medium", "evidence": "交期未确认。",
                "recommendation": "先核查。", "raw": "RISK_RAW_SECRET",
            }],
            "suggested_actions": [{
                "type": "check_delivery", "description": "核查交付。", "owner_hint": "sales",
                "due_hint": "today", "path": "/private/action",
            }],
            "reply_draft": {
                "subject": "Re: Delivery", "body": "Hello, we are checking.",
                "needs_human_review": True, "review_reasons": ["需要人工审核。"],
                "token": "DRAFT_PRIVATE_TOKEN",
            },
            "analysis_engine": {
                "source": "rule_fallback", "label": "Rule fallback",
                "private_url": "https://private.example/engine",
            },
        }

        save_analysis(connection, "Delivery", "customer@example.test", analysis)
        stored_json = connection.execute(
            "SELECT analysis_json FROM email_analysis"
        ).fetchone()[0]
        stored = json.loads(stored_json)

        self.assertEqual(
            set(stored["decision_brief"]),
            {
                "one_line_conclusion", "requested_outcome", "next_steps", "key_facts",
                "must_check", "missing_info", "reply_recommendation", "confidence",
            },
        )
        self.assertEqual(
            set(stored["decision_brief"]["next_steps"][0]),
            {"step", "owner_hint", "due_hint", "source"},
        )
        self.assertEqual(
            set(stored["decision_brief"]["key_facts"][0]),
            {"label", "value", "source"},
        )
        self.assertEqual(
            set(stored["decision_brief"]["reply_recommendation"]),
            {"should_reply", "reply_type", "reason"},
        )
        self.assertEqual(
            set(stored["conversation_timeline"]["open_items"][0]),
            {"item", "owner_hint", "due_hint", "source"},
        )
        self.assertEqual(
            set(stored["risk_flags"][0]),
            {"type", "level", "evidence", "recommendation"},
        )
        self.assertEqual(
            set(stored["suggested_actions"][0]),
            {"type", "description", "owner_hint", "due_hint"},
        )
        self.assertEqual(
            set(stored["reply_draft"]),
            {"subject", "body", "needs_human_review", "review_reasons"},
        )
        self.assertEqual(set(stored["analysis_engine"]), {"source", "label"})
        for secret in (
            "STEP_PRIVATE_TOKEN", "C:/private/key-fact", "private.example/recommendation",
            "DECISION_RAW_SECRET", "private.example/timeline", "TIMELINE_PRIVATE_TOKEN",
            "RISK_RAW_SECRET", "/private/action", "DRAFT_PRIVATE_TOKEN", "private.example/engine",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, stored_json)


if __name__ == "__main__":
    unittest.main()
