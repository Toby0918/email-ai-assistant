"""Tests for local SQLite analysis persistence."""

from __future__ import annotations

import inspect
import json
import sqlite3
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.email_agent.database import connect, initialize_schema, save_analysis


PERSISTENCE_STAGE_SECONDS = 0.5
SQLITE_SCHEDULING_TOLERANCE_SECONDS = 0.2


class _InsertSignalingConnection:
    def __init__(
        self, connection: sqlite3.Connection, insert_started: threading.Event
    ) -> None:
        self._connection = connection
        self._insert_started = insert_started

    def execute(
        self, statement: str, parameters: tuple[object, ...] = ()
    ) -> sqlite3.Cursor:
        if statement.startswith("INSERT INTO email_analysis"):
            self._insert_started.set()
        return self._connection.execute(statement, parameters)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()


class _CommitFailOnceConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._fail_commit = True

    def execute(
        self, statement: str, parameters: tuple[object, ...] = ()
    ) -> sqlite3.Cursor:
        return self._connection.execute(statement, parameters)

    def commit(self) -> None:
        if self._fail_commit:
            self._fail_commit = False
            raise sqlite3.OperationalError("PRIVATE_COMMIT_DETAIL")
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()


class DatabaseTests(unittest.TestCase):
    def test_private_context_fields_are_not_persisted(self) -> None:
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        initialize_schema(connection)

        save_analysis(
            connection,
            subject="Synthetic",
            sender="sender@example.test",
            analysis={
                "summary": "Synthetic summary.",
                "runtime_cards": ["PRIVATE_CARD"],
                "private_context": "PRIVATE_CONTEXT",
                "placeholder_mapping": {"<EMAIL_1>": "private@example.test"},
                "card_id": "PRIVATE_CARD_ID",
                "snapshot_id": "PRIVATE_SNAPSHOT_ID",
                "vault_id": "PRIVATE_VAULT_ID",
            },
        )

        stored = connection.execute(
            "SELECT analysis_json FROM email_analysis"
        ).fetchone()[0]
        for marker in (
            "runtime_cards", "private_context", "placeholder_mapping",
            "card_id", "snapshot_id", "vault_id", "PRIVATE_", "<EMAIL_",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, stored)

    def test_connect_default_busy_timeout_is_below_two_seconds(self) -> None:
        connection = connect(":memory:")
        self.addCleanup(connection.close)

        timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

        self.assertLessEqual(timeout, 500)

    def test_save_analysis_recomputes_requested_busy_timeout_before_commit(self) -> None:
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        initialize_schema(connection)
        self.assertIn("busy_timeout_ms", inspect.signature(save_analysis).parameters)

        save_analysis(
            connection,
            subject="Delivery",
            sender="customer@example.test",
            analysis={"summary": "Customer asks about delivery."},
            busy_timeout_ms=37,
        )

        timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        self.assertGreaterEqual(timeout, 0)
        self.assertLess(timeout, 37)

    def test_file_backed_insert_then_commit_contention_uses_one_cumulative_deadline(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "cumulative-deadline.sqlite3"
            target = connect(str(database_path))
            initialize_schema(target)
            reader = sqlite3.connect(database_path, check_same_thread=False)
            writer = sqlite3.connect(database_path, check_same_thread=False)
            insert_started = threading.Event()
            signaling_target = _InsertSignalingConnection(target, insert_started)
            result: dict[str, object] = {}

            reader.execute("BEGIN")
            reader.execute("SELECT id FROM email_analysis").fetchall()
            writer.execute("BEGIN IMMEDIATE")

            def persist() -> None:
                started = time.monotonic()
                try:
                    save_analysis(
                        signaling_target,
                        subject="first-marker",
                        sender="synthetic@example.test",
                        analysis={"summary": "First marker."},
                        busy_timeout_ms=500,
                    )
                except sqlite3.Error as exc:
                    result["error"] = exc
                result["elapsed"] = time.monotonic() - started

            persistence_thread = threading.Thread(target=persist, daemon=True)
            try:
                persistence_thread.start()
                saw_insert = insert_started.wait(timeout=1.0)
                time.sleep(0.4)
                writer.rollback()
                persistence_thread.join(timeout=1.5)
                returned = not persistence_thread.is_alive()
                elapsed = float(result.get("elapsed", 10.0))
                error = result.get("error")
            finally:
                writer.rollback()
                reader.rollback()
                persistence_thread.join(timeout=2)
                target.rollback()
                writer.close()
                reader.close()
                target.close()

            self.assertTrue(saw_insert)
            self.assertTrue(returned)
            self.assertIsInstance(error, sqlite3.Error)
            self.assertLessEqual(
                elapsed,
                PERSISTENCE_STAGE_SECONDS + SQLITE_SCHEDULING_TOLERANCE_SECONDS,
            )

    def test_commit_failure_rolls_back_before_later_success(self) -> None:
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        initialize_schema(connection)
        failing_once = _CommitFailOnceConnection(connection)

        with self.assertRaises(sqlite3.Error):
            save_analysis(
                failing_once,
                subject="failed-marker",
                sender="synthetic@example.test",
                analysis={"summary": "Failed marker."},
            )
        transaction_after_failure = connection.in_transaction

        save_analysis(
            failing_once,
            subject="successful-marker",
            sender="synthetic@example.test",
            analysis={"summary": "Successful marker."},
        )
        stored_subjects = [
            row[0]
            for row in connection.execute(
                "SELECT subject FROM email_analysis ORDER BY id"
            ).fetchall()
        ]

        self.assertFalse(transaction_after_failure)
        self.assertEqual(stored_subjects, ["successful-marker"])

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
            "schema_version": "deepseek_analysis_v1",
            "field_evidence": {"/analysis/summary": ["thread:0"]},
            "attachment_augmentations": [{"source_id": "attachment:0"}],
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
                    "path": "C:/private/key-fact", "source_id": "thread:0",
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
                    "open_item_id": "open:0",
                }],
                "confidence": "medium",
                "token": "TIMELINE_PRIVATE_TOKEN",
            },
            "attachment_insights": [],
            "risk_flags": [{
                "type": "delivery_risk", "level": "medium", "evidence": "交期未确认。",
                "recommendation": "先核查。", "raw": "RISK_RAW_SECRET",
                "evidence_sources": ["thread:0"],
            }],
            "suggested_actions": [{
                "type": "check_delivery", "description": "核查交付。", "owner_hint": "sales",
                "due_hint": "today", "path": "/private/action",
                "timeline_interpretation": {"private": True},
            }],
            "reply_draft": {
                "subject": "Re: Delivery", "body": "Hello, we are checking.",
                "needs_human_review": True, "review_reasons": ["需要人工审核。"],
                "token": "DRAFT_PRIVATE_TOKEN", "source_id": "thread:0",
            },
            "analysis_engine": {
                "source": "rule_fallback", "label": "Rule fallback",
                "context_scope": "current_only", "context_limited": True,
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
        self.assertNotIn("context_scope", stored["analysis_engine"])
        self.assertNotIn("context_limited", stored["analysis_engine"])
        for secret in (
            "STEP_PRIVATE_TOKEN", "C:/private/key-fact", "private.example/recommendation",
            "DECISION_RAW_SECRET", "private.example/timeline", "TIMELINE_PRIVATE_TOKEN",
            "RISK_RAW_SECRET", "/private/action", "DRAFT_PRIVATE_TOKEN", "private.example/engine",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, stored_json)
        for provider_key in (
            "schema_version", "field_evidence", "evidence_sources", "source_id",
            "open_item_id", "timeline_interpretation", "attachment_augmentations",
        ):
            with self.subTest(provider_key=provider_key):
                self.assertNotIn(provider_key, stored_json)


if __name__ == "__main__":
    unittest.main()
