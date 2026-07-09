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
