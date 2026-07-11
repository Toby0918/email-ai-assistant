"""Business tests for the local backend API boundary."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.email_agent.api import handle_analyze_current_email
from backend.email_agent.config import load_config


class ApiTests(unittest.TestCase):
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
                            "filename": r"C:\private\notes.txt",
                            "type": "txt",
                            "size": -3,
                            "limitation": "Resource type is not supported. https://private.example/token",
                            "private_url": "https://private.example/download",
                            "token": "PRIVATE_TOKEN",
                        },
                        {
                            "filename": "large.pdf",
                            "type": "pdf",
                            "size": 999,
                            "limitation": "Resource exceeds the 10-byte per-file limit. C:/private/path",
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
            {"filename", "type", "size", "limitation"},
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
        for secret in ("private.example", "C:/private", "PRIVATE_TOKEN", "private_url"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, serialized)

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
