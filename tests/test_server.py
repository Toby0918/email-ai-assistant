"""Tests for the local HTTP API server."""

from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.request
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.email_agent.config import load_config
from backend.email_agent.server import EmailAssistantHandler, create_server


class ServerTests(unittest.TestCase):
    def test_analyze_endpoint_rejects_negative_content_length_without_reading_body(self) -> None:
        handler = object.__new__(EmailAssistantHandler)
        handler.path = "/api/analyze-current-email"
        handler.headers = {"Content-Length": "-1"}
        handler.server = SimpleNamespace(attachment_config=load_config(dotenv_path=None))
        handler.rfile = Mock()
        handler._send_json = Mock()

        handler.do_POST()

        handler.rfile.read.assert_not_called()
        response, status = handler._send_json.call_args.args
        self.assertEqual(response["error"]["code"], "INVALID_CONTENT_LENGTH")
        self.assertEqual(status.value, 400)

    def test_health_endpoint_returns_ok(self) -> None:
        server = create_server(host="127.0.0.1", port=0, database_path=":memory:")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            self.assertTrue(data["ok"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_analyze_endpoint_requires_user_confirmation(self) -> None:
        server = create_server(host="127.0.0.1", port=0, database_path=":memory:")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/analyze-current-email"
            body = json.dumps({"subject": "x", "from": "a@example.com", "body_text": "hi"}).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with patch.dict(os.environ, {"EMAIL_AGENT_LLM_PROVIDER": "disabled"}):
                with urllib.request.urlopen(request, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
            self.assertFalse(data["ok"])
            self.assertEqual(data["error"]["code"], "USER_ACTION_REQUIRED")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_analyze_endpoint_returns_analysis_and_saved_id(self) -> None:
        server = create_server(host="127.0.0.1", port=0, database_path=":memory:")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/analyze-current-email"
            body = json.dumps({
                "user_confirmed": True,
                "subject": "Delivery",
                "from": "customer@example.com",
                "body_text": "Please confirm delivery date.",
            }).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with patch.dict(os.environ, {"EMAIL_AGENT_LLM_PROVIDER": "disabled"}):
                with urllib.request.urlopen(request, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
            self.assertTrue(data["ok"])
            self.assertIn("request_id", data)
            self.assertIn("analysis", data)
            self.assertGreaterEqual(data["saved_id"], 1)
            stored_json = server.database.execute(
                "SELECT analysis_json FROM email_analysis WHERE id = ?",
                (data["saved_id"],),
            ).fetchone()[0]
            self.assertNotIn("clean_body", stored_json)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
