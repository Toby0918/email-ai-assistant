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


if __name__ == "__main__":
    unittest.main()
