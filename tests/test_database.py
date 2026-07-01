"""Tests for local SQLite analysis persistence."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
