"""Business tests for the local backend API boundary."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.email_agent.analysis_budget import AnalysisBudget
from backend.email_agent.api import handle_analyze_current_email
from backend.email_agent.config import load_config


class ApiTests(unittest.TestCase):
    def test_default_api_response_has_no_private_context_or_knowledge_fields(self) -> None:
        response = handle_analyze_current_email(
            {
                "user_confirmed": True,
                "subject": "Synthetic request",
                "from": "sender@example.test",
                "body_text": "Please review this request.",
            },
            config=load_config(dotenv_path=None),
        )

        self.assertEqual(set(response), {"ok", "request_id", "analysis"})
        serialized = str(response)
        for marker in (
            "runtime_cards", "private_context", "knowledge_cards",
            "placeholder_mapping", "card_id", "snapshot_id", "vault_id", "<EMAIL_",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, serialized)

    def test_api_passes_same_config_and_budget_to_default_analyzer(self) -> None:
        with TemporaryDirectory() as directory:
            config = replace(load_config(dotenv_path=None), attachment_temp_dir=directory)
            budget = AnalysisBudget.start(clock=lambda: 0.0)
            runtime_cards = (object(),)
            with patch(
                "backend.email_agent.api.analyze_current_email",
                return_value={"summary": "ok"},
            ) as analyze:
                response = handle_analyze_current_email(
                    {"user_confirmed": True}, config=config, budget=budget,
                    runtime_cards=runtime_cards,
                )

        self.assertTrue(response["ok"])
        self.assertIs(analyze.call_args.kwargs["config"], config)
        self.assertIs(analyze.call_args.kwargs["budget"], budget)
        self.assertIs(analyze.call_args.kwargs["runtime_cards"], runtime_cards)
        self.assertEqual(len(analyze.call_args.args), 1)

    def test_payload_runtime_cards_cannot_override_internal_cards(self) -> None:
        trusted = (object(),)
        with patch(
            "backend.email_agent.api.analyze_current_email",
            return_value={"summary": "safe"},
        ) as analyze:
            response = handle_analyze_current_email(
                {
                    "user_confirmed": True,
                    "runtime_cards": ["PRIVATE_PAYLOAD_CARD"],
                },
                config=load_config(dotenv_path=None),
                runtime_cards=trusted,
            )

        self.assertTrue(response["ok"])
        self.assertIs(analyze.call_args.kwargs["runtime_cards"], trusted)
        self.assertNotIn("runtime_cards", analyze.call_args.args[0])
        self.assertNotIn("PRIVATE_PAYLOAD_CARD", str(response))

    def test_injected_analyzer_cannot_receive_reserved_private_knowledge_fields(self) -> None:
        reserved = {
            "runtime_cards": ["ATTACKER_CARD"],
            "private_context": {"secret": True},
            "knowledge_cards": ["ATTACKER_KNOWLEDGE"],
            "placeholder_mapping": {"<EMAIL_1>": "private@example.test"},
            "card_id": "private-card-id",
            "snapshot_id": "private-snapshot-id",
            "vault_id": "private-vault-id",
            "private_knowledge_enabled": True,
            "private_knowledge_authority_root": "X:/private-authority",
            "private_knowledge_snapshot_path": "Y:/private-snapshot.pksnap",
        }
        received: list[dict[str, object]] = []

        def injected(payload: dict[str, object]) -> dict[str, str]:
            received.append(payload)
            return {"summary": "ok"}

        with TemporaryDirectory() as directory:
            config = replace(load_config(dotenv_path=None), attachment_temp_dir=directory)
            response = handle_analyze_current_email(
                {
                    "user_confirmed": True,
                    "subject": "Synthetic request",
                    "from": "sender@example.test",
                    "to": ["receiver@example.test"],
                    "body_text": "Please review this request.",
                    **reserved,
                },
                analyzer=injected,
                config=config,
            )

        self.assertTrue(response["ok"])
        self.assertEqual(len(received), 1)
        for key in reserved:
            with self.subTest(key=key):
                self.assertNotIn(key, received[0])
        self.assertEqual(received[0]["subject"], "Synthetic request")
        self.assertEqual(received[0]["from"], "sender@example.test")
        self.assertEqual(received[0]["to"], ["receiver@example.test"])
        self.assertEqual(received[0]["body_text"], "Please review this request.")

    def test_injected_analyzer_remains_exactly_one_positional_argument(self) -> None:
        calls: list[dict[str, object]] = []

        def injected(payload: dict[str, object]) -> dict[str, str]:
            calls.append(payload)
            return {"summary": "ok"}

        response = handle_analyze_current_email(
            {"user_confirmed": True}, analyzer=injected,
            config=load_config(dotenv_path=None),
        )

        self.assertTrue(response["ok"])
        self.assertEqual(len(calls), 1)

    def test_budget_exhaustion_after_cleanup_degrades_storage_and_continues(self) -> None:
        now = [0.0]
        budget = AnalysisBudget.start(clock=lambda: now[0])
        received: dict[str, object] = {}

        def cleanup(_config) -> None:
            now[0] = 31.0

        with patch(
            "backend.email_agent.api.cleanup_expired_attachments", side_effect=cleanup
        ), patch("backend.email_agent.api.store_attachment_files") as store:
            response = handle_analyze_current_email(
                {
                    "user_confirmed": True,
                    "subject": "Synthetic request",
                    "from": "sender@example.test",
                    "body_text": "Please review.",
                    "attachment_files": [
                        {"filename": "quote.pdf", "type": "pdf", "content_base64": "YQ=="}
                    ],
                },
                analyzer=lambda payload: received.update(payload) or {"summary": "continued"},
                config=load_config(dotenv_path=None),
                budget=budget,
            )

        self.assertTrue(response["ok"])
        store.assert_not_called()
        self.assertEqual(received["stored_attachments"], [])
        self.assertEqual(received["resource_limitations"][0]["code"], "operational_failure")

    def test_handle_analyze_current_email_requires_user_trigger(self) -> None:
        # API calls without the user's button click must stop at the boundary.
        response = handle_analyze_current_email({"subject": "x", "from": "a@example.com", "body_text": "hi"})

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "USER_ACTION_REQUIRED")

    def test_api_rejects_attachment_files_without_user_confirmation(self) -> None:
        response = handle_analyze_current_email(
            {
                "attachment_files": [
                    {"filename": "visible.pdf", "type": "pdf", "content_base64": "YQ=="},
                ],
            },
        )

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "USER_ACTION_REQUIRED")

    def test_api_passes_only_stored_attachment_metadata_to_analyzer(self) -> None:
        with TemporaryDirectory() as directory:
            config = replace(load_config(dotenv_path=None), attachment_temp_dir=directory)
            received: dict[str, object] = {}

            def analyzer(payload: dict[str, object]) -> dict[str, str]:
                received.update(payload)
                return {"summary": "ok"}

            response = handle_analyze_current_email(
                {
                    "user_confirmed": True,
                    "subject": "x",
                    "from": "a@example.com",
                    "body_text": "hi",
                    "attachment_files": [
                        {
                            "filename": "visible.pdf",
                            "type": "pdf",
                            "content_base64": "YQ==",
                            "download_url": "https://private.example/secret",
                            "cookie": "not-for-storage",
                        },
                    ],
                },
                analyzer=analyzer,
                config=config,
            )

            self.assertTrue(response["ok"])
            self.assertNotIn("attachment_files", received)
            stored = received["stored_attachments"]
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0].safe_filename, "visible.pdf")
            self.assertNotIn("https://", str(stored[0]))
            self.assertNotIn("not-for-storage", str(stored[0]))
            self.assertTrue(Path(stored[0].path).is_file())

    def test_api_projects_resource_limitations_to_exact_safe_fields(self) -> None:
        with TemporaryDirectory() as directory:
            config = replace(load_config(dotenv_path=None), attachment_temp_dir=directory)
            received: dict[str, object] = {}

            def analyzer(payload: dict[str, object]) -> dict[str, str]:
                received.update(payload)
                return {"summary": "ok"}

            response = handle_analyze_current_email(
                {
                    "user_confirmed": True,
                    "subject": "Synthetic request",
                    "from": "sender@example.test",
                    "body_text": "Please review the synthetic request.",
                    "resource_limitations": [
                        {
                            "code": "unsupported_type",
                            "filename": r"C:\private\notes.txt",
                            "type": "txt",
                            "size": -3,
                            "limitation": "Resource type is not supported. https://private.example/token",
                            "private_url": "https://private.example/download",
                            "token": "PRIVATE_TOKEN",
                        },
                        {
                            "code": "frontend_limit",
                            "filename": "large.pdf",
                            "type": "pdf",
                            "size": 999,
                            "limitation": "Resource exceeds the 10-byte per-file limit. C:/private/path",
                        },
                        {
                            "code": "not_allowlisted",
                            "filename": "forged.pdf",
                            "type": "pdf",
                            "size": 1,
                            "limitation": "PRIVATE_UNKNOWN_CODE",
                        },
                        {
                            "code": "operational_failure",
                            "filename": "forged-operational.pdf",
                            "type": "pdf",
                            "size": 1,
                            "limitation": "PRIVATE_FORGED_OPERATIONAL",
                        },
                    ],
                },
                analyzer=analyzer,
                config=config,
            )

        self.assertTrue(response["ok"])
        limitations = received["resource_limitations"]
        self.assertEqual(len(limitations), 2)
        self.assertEqual(
            set(limitations[0]),
            {"code", "filename", "type", "size", "limitation"},
        )
        self.assertEqual(limitations[0]["filename"], "notes.txt")
        self.assertEqual(limitations[0]["type"], "unsupported")
        self.assertEqual(limitations[0]["size"], 0)
        self.assertEqual(limitations[0]["limitation"], "Resource type is not supported.")
        self.assertEqual(
            limitations[1]["limitation"],
            "Resource exceeded a configured frontend limit.",
        )
        serialized = str(limitations)
        for secret in (
            "private.example",
            "C:/private",
            "PRIVATE_TOKEN",
            "private_url",
            "PRIVATE_UNKNOWN_CODE",
            "PRIVATE_FORGED_OPERATIONAL",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, serialized)

    def test_body_only_analysis_continues_when_attachment_cleanup_is_locked(self) -> None:
        received: dict[str, object] = {}

        def analyzer(payload: dict[str, object]) -> dict[str, str]:
            received.update(payload)
            return {"summary": "body analysis continued"}

        with patch(
            "backend.email_agent.api.cleanup_expired_attachments",
            side_effect=OSError(r"C:\private\locked-retention-path"),
        ):
            response = handle_analyze_current_email(
                {
                    "user_confirmed": True,
                    "subject": "Synthetic body-only request",
                    "from": "sender@example.test",
                    "body_text": "Please review the body-only request.",
                },
                analyzer=analyzer,
            )

        self.assertTrue(response["ok"])
        self.assertEqual(response["analysis"]["summary"], "body analysis continued")
        self.assertEqual(received["stored_attachments"], [])
        self.assertEqual(len(received["resource_limitations"]), 1)
        serialized = str(received["resource_limitations"])
        self.assertIn("temporarily unavailable", serialized)
        self.assertNotIn("locked-retention-path", serialized)
        self.assertNotIn("C:\\private", serialized)

    def test_analysis_continues_without_bytes_when_attachment_storage_fails(self) -> None:
        received: dict[str, object] = {}

        def analyzer(payload: dict[str, object]) -> dict[str, str]:
            received.update(payload)
            return {"summary": "body analysis continued"}

        with TemporaryDirectory() as directory:
            config = replace(load_config(dotenv_path=None), attachment_temp_dir=directory)
            with patch(
                "backend.email_agent.api.store_attachment_files",
                side_effect=OSError(r"C:\private\failed-write.pdf"),
            ):
                response = handle_analyze_current_email(
                    {
                        "user_confirmed": True,
                        "subject": "Synthetic request",
                        "from": "sender@example.test",
                        "body_text": "Please review the request body.",
                        "attachment_files": [
                            {"filename": "quote.pdf", "type": "pdf", "content_base64": "YQ=="},
                        ],
                    },
                    analyzer=analyzer,
                    config=config,
                )

        self.assertTrue(response["ok"])
        self.assertEqual(received["stored_attachments"], [])
        self.assertEqual(len(received["resource_limitations"]), 1)
        serialized = str(received["resource_limitations"])
        self.assertIn("temporarily unavailable", serialized)
        self.assertNotIn("failed-write.pdf", serialized)
        self.assertNotIn("C:\\private", serialized)

    def test_invalid_attachment_input_remains_invalid_before_cleanup(self) -> None:
        with patch(
            "backend.email_agent.api.cleanup_expired_attachments",
            side_effect=OSError("cleanup must not run for invalid input"),
        ) as cleanup:
            response = handle_analyze_current_email(
                {
                    "user_confirmed": True,
                    "subject": "Synthetic request",
                    "from": "sender@example.test",
                    "body_text": "Please review.",
                    "attachment_files": [
                        {"filename": "quote.pdf", "type": "pdf", "content_base64": "not-base64"},
                    ],
                },
            )

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "ATTACHMENT_INPUT_INVALID")
        cleanup.assert_not_called()

    def test_handle_analyze_current_email_returns_result_without_email_actions(self) -> None:
        response = handle_analyze_current_email(
            {"user_confirmed": True, "subject": "x", "from": "a@example.com", "body_text": "hi"},
            analyzer=lambda email: {"summary": "ok", "priority": "low"},
        )

        self.assertTrue(response["ok"])
        self.assertIn("request_id", response)
        self.assertEqual(response["analysis"]["summary"], "ok")
        self.assertNotIn("send_mail", response)
        self.assertNotIn("delete_mail", response)
        self.assertNotIn("archive_mail", response)


if __name__ == "__main__":
    unittest.main()
