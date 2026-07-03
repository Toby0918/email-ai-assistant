"""Tests for the local HTTP API server."""

from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.request
from unittest.mock import patch

from backend.email_agent.server import create_server


class ServerTests(unittest.TestCase):
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
