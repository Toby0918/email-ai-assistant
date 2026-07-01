"""Business tests for the local backend API boundary."""

from __future__ import annotations

import unittest

from backend.email_agent.api import handle_analyze_current_email


class ApiTests(unittest.TestCase):
    def test_handle_analyze_current_email_requires_user_trigger(self) -> None:
        # API calls without the user's button click must stop at the boundary.
        response = handle_analyze_current_email({"subject": "x", "from": "a@example.com", "body_text": "hi"})

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "USER_ACTION_REQUIRED")

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
