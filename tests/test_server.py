"""Tests for the local HTTP API server."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import unittest
import urllib.request
from dataclasses import replace
from email.message import Message
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.email_agent.analysis_budget import AnalysisBudget
from backend.email_agent.config import load_config
from backend.email_agent.server import EmailAssistantHandler, create_server


# No existing API code names persistence failure, so pin one conservative,
# persistence-specific generic object without returning partial analysis fields.
PERSISTENCE_ERROR = {
    "ok": False,
    "error": {
        "code": "PERSISTENCE_FAILED",
        "message": "Analysis result could not be saved.",
    },
}


class ServerTests(unittest.TestCase):
    @staticmethod
    def _post_analysis(server: object) -> dict[str, object]:
        url = f"http://127.0.0.1:{server.server_port}/api/analyze-current-email"
        body = json.dumps({
            "user_confirmed": True,
            "subject": r"C:\private\customer-subject",
            "from": "private-sender@example.test",
            "body_text": "PRIVATE_EMAIL_BODY",
        }).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _private_success() -> dict[str, object]:
        return {
            "ok": True,
            "request_id": "PRIVATE_PROVIDER_REQUEST_ID",
            "analysis": {
                "summary": "Synthetic result.",
                "field_evidence": {"/analysis/summary": ["PRIVATE_PROVIDER_DETAIL"]},
                "provider_debug": "PRIVATE_PROVIDER_DETAIL",
            },
        }

    @staticmethod
    def _direct_handler(
        *,
        host_values: tuple[str, ...] = ("127.0.0.1:8765",),
        content_type_values: tuple[str, ...] = ("application/json",),
        body: bytes = b'{"user_confirmed": true}',
    ) -> EmailAssistantHandler:
        headers = Message()
        for value in host_values:
            headers["Host"] = value
        for value in content_type_values:
            headers["Content-Type"] = value
        headers["Content-Length"] = str(len(body))
        handler = object.__new__(EmailAssistantHandler)
        handler.path = "/api/analyze-current-email"
        handler.headers = headers
        handler.server = SimpleNamespace(
            server_port=8765,
            attachment_config=load_config(dotenv_path=None),
        )
        handler.rfile = Mock()
        handler.rfile.read.return_value = body
        handler._save_result = Mock()
        handler._send_json = Mock()
        return handler

    def test_analyze_endpoint_rejects_unsupported_media_before_read_or_analysis(self) -> None:
        cases = (
            (),
            ("text/plain",),
            ("application/x-www-form-urlencoded",),
            ("application/problem+json",),
            ("application/jsonnot",),
            ("application/json, text/plain",),
            ("application/json", "text/plain"),
        )
        for values in cases:
            with self.subTest(values=values):
                handler = self._direct_handler(content_type_values=values)
                with patch("backend.email_agent.server.handle_analyze_current_email") as analyze:
                    handler.do_POST()

                handler.rfile.read.assert_not_called()
                analyze.assert_not_called()
                handler._save_result.assert_not_called()
                response, status = handler._send_json.call_args.args
                self.assertEqual(response["error"]["code"], "UNSUPPORTED_MEDIA_TYPE")
                self.assertEqual(status.value, 415)

    def test_analyze_endpoint_accepts_only_exact_json_media_types(self) -> None:
        for value in (
            "application/json",
            "application/json;charset=utf-8",
            "Application/JSON; Charset=UTF-8",
        ):
            with self.subTest(value=value):
                handler = self._direct_handler(content_type_values=(value,))
                with patch(
                    "backend.email_agent.server.handle_analyze_current_email",
                    return_value={"ok": False, "error": {"code": "SYNTHETIC"}},
                ) as analyze:
                    handler.do_POST()

                handler.rfile.read.assert_called_once()
                analyze.assert_called_once()

    def test_budget_starts_immediately_before_read_and_same_object_reaches_api(self) -> None:
        handler = self._direct_handler()
        budget = AnalysisBudget.start(clock=lambda: 0.0)
        events: list[str] = []

        handler._read_json = Mock(
            side_effect=lambda: events.append("read") or {"user_confirmed": True}
        )
        with patch(
            "backend.email_agent.server.AnalysisBudget.start",
            side_effect=lambda: events.append("start") or budget,
        ) as start, patch(
            "backend.email_agent.server.handle_analyze_current_email",
            side_effect=lambda *_args, **_kwargs: events.append("api")
            or {"ok": False, "error": {"code": "SYNTHETIC"}},
        ) as analyze:
            handler.do_POST()

        self.assertEqual(events, ["start", "read", "api"])
        start.assert_called_once_with()
        self.assertIs(analyze.call_args.kwargs["budget"], budget)

    def test_same_budget_object_reaches_persistence(self) -> None:
        handler = self._direct_handler()
        budget = AnalysisBudget.start(clock=lambda: 0.0)
        payload = {"user_confirmed": True, "subject": "Synthetic"}
        analysis = {"summary": "Synthetic result."}
        handler._read_json = Mock(return_value=payload)
        handler._save_result.return_value = 17

        with patch(
            "backend.email_agent.server.AnalysisBudget.start", return_value=budget
        ), patch(
            "backend.email_agent.server.handle_analyze_current_email",
            return_value={"ok": True, "request_id": "local-test", "analysis": analysis},
        ):
            handler.do_POST()

        self.assertIn("budget", handler._save_result.call_args.kwargs)
        self.assertIs(handler._save_result.call_args.kwargs["budget"], budget)
        response = handler._send_json.call_args.args[0]
        self.assertEqual(response["saved_id"], 17)

    def test_python_database_lock_contention_returns_within_bounded_stage(self) -> None:
        config = replace(load_config(dotenv_path=None), llm_provider="disabled")
        server = create_server(
            host="127.0.0.1", port=0, database_path=":memory:", config=config
        )
        service_thread = threading.Thread(target=server.serve_forever, daemon=True)
        result: dict[str, object] = {}
        server.database_lock.acquire()
        service_thread.start()

        def invoke() -> None:
            try:
                result["response"] = self._post_analysis(server)
            except Exception as exc:
                result["exception"] = exc

        request_thread = threading.Thread(target=invoke, daemon=True)
        try:
            with patch(
                "backend.email_agent.server.handle_analyze_current_email",
                return_value=self._private_success(),
            ):
                started = time.monotonic()
                request_thread.start()
                request_thread.join(timeout=1.75)
                returned_while_locked = not request_thread.is_alive()
                elapsed = time.monotonic() - started
                server.database_lock.release()
                request_thread.join(timeout=5)

            if "exception" in result:
                raise result["exception"]
            self.assertTrue(returned_while_locked)
            self.assertLess(elapsed, 2.0)
            self.assertEqual(result["response"], PERSISTENCE_ERROR)
            stored_count = server.database.execute(
                "SELECT COUNT(*) FROM email_analysis"
            ).fetchone()[0]
            self.assertEqual(stored_count, 0)
        finally:
            if server.database_lock.locked():
                server.database_lock.release()
            server.shutdown()
            server.server_close()
            service_thread.join(timeout=5)
            server.database.close()

    def test_sqlite_lock_contention_returns_generic_error_within_bounded_stage(self) -> None:
        config = replace(load_config(dotenv_path=None), llm_provider="disabled")
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "analysis.sqlite3"
            server = create_server(
                host="127.0.0.1",
                port=0,
                database_path=str(database_path),
                config=config,
            )
            service_thread = threading.Thread(target=server.serve_forever, daemon=True)
            blocker = sqlite3.connect(database_path, check_same_thread=False)
            blocker.execute("BEGIN EXCLUSIVE")
            result: dict[str, object] = {}
            service_thread.start()

            def invoke() -> None:
                try:
                    result["response"] = self._post_analysis(server)
                except Exception as exc:
                    result["exception"] = exc

            request_thread = threading.Thread(target=invoke, daemon=True)
            try:
                with patch(
                    "backend.email_agent.server.handle_analyze_current_email",
                    return_value=self._private_success(),
                ):
                    started = time.monotonic()
                    request_thread.start()
                    request_thread.join(timeout=1.75)
                    returned_while_locked = not request_thread.is_alive()
                    elapsed = time.monotonic() - started
                    blocker.rollback()
                    request_thread.join(timeout=5)

                if "exception" in result:
                    raise result["exception"]
                self.assertTrue(returned_while_locked)
                self.assertLess(elapsed, 2.0)
                self.assertEqual(result["response"], PERSISTENCE_ERROR)
                stored_count = server.database.execute(
                    "SELECT COUNT(*) FROM email_analysis"
                ).fetchone()[0]
                self.assertEqual(stored_count, 0)
                self.assertNotIn(str(database_path), json.dumps(result["response"]))
            finally:
                blocker.rollback()
                blocker.close()
                server.shutdown()
                server.server_close()
                service_thread.join(timeout=5)
                server.database.close()

    def test_analyze_endpoint_rejects_untrusted_host_before_read_or_analysis(self) -> None:
        cases = (
            (),
            ("127.0.0.1:8765", "localhost:8765"),
            ("127.0.0.1:8765, attacker.example",),
            ("attacker.example:8765",),
            ("0.0.0.0:8765",),
            ("192.168.1.10:8765",),
            ("8.8.8.8:8765",),
            ("localhost@attacker.example:8765",),
            ("localhost:notaport",),
            ("127.0.0.1:9999",),
        )
        for values in cases:
            with self.subTest(values=values):
                handler = self._direct_handler(host_values=values)
                with patch("backend.email_agent.server.handle_analyze_current_email") as analyze:
                    handler.do_POST()

                handler.rfile.read.assert_not_called()
                analyze.assert_not_called()
                handler._save_result.assert_not_called()
                response, status = handler._send_json.call_args.args
                self.assertEqual(response["error"]["code"], "INVALID_HOST")
                self.assertEqual(status.value, 403)
                for value in values:
                    self.assertNotIn(value, response["error"]["message"])

    def test_analyze_endpoint_accepts_localhost_and_ipv4_loopback_host(self) -> None:
        for value in (
            "localhost",
            "localhost:8765",
            "127.0.0.1",
            "127.0.0.1:8765",
            "127.0.0.2:8765",
        ):
            with self.subTest(value=value):
                handler = self._direct_handler(host_values=(value,))
                with patch(
                    "backend.email_agent.server.handle_analyze_current_email",
                    return_value={"ok": False, "error": {"code": "SYNTHETIC"}},
                ) as analyze:
                    handler.do_POST()

                handler.rfile.read.assert_called_once()
                analyze.assert_called_once()

    def test_rejected_network_boundaries_never_persist_analysis(self) -> None:
        server = create_server(host="127.0.0.1", port=0, database_path=":memory:")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        body = json.dumps({"user_confirmed": True, "body_text": "synthetic"})
        cases = (
            (
                {"Host": f"127.0.0.1:{server.server_port}", "Content-Type": "text/plain"},
                415,
                "UNSUPPORTED_MEDIA_TYPE",
            ),
            (
                {"Host": f"attacker.example:{server.server_port}", "Content-Type": "application/json"},
                403,
                "INVALID_HOST",
            ),
        )
        try:
            for headers, expected_status, expected_code in cases:
                with self.subTest(expected_code=expected_code):
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    connection.request(
                        "POST",
                        "/api/analyze-current-email",
                        body=body,
                        headers=headers,
                    )
                    response = connection.getresponse()
                    payload = json.loads(response.read().decode("utf-8"))
                    connection.close()
                    self.assertEqual(response.status, expected_status)
                    self.assertEqual(payload["error"]["code"], expected_code)
                    stored_count = server.database.execute(
                        "SELECT COUNT(*) FROM email_analysis"
                    ).fetchone()[0]
                    self.assertEqual(stored_count, 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_create_server_rejects_non_loopback_host_before_bind(self) -> None:
        rejected = (
            "0.0.0.0",
            "192.168.1.10",
            "8.8.8.8",
            "attacker.example",
            "localhost@attacker.example",
            "::1",
        )
        for host in rejected:
            with self.subTest(host=host):
                with patch("backend.email_agent.server.EmailAssistantServer") as server_type:
                    with self.assertRaisesRegex(
                        ValueError,
                        "supported loopback address",
                    ) as caught:
                        create_server(host=host, port=8765, database_path=":memory:")
                    server_type.assert_not_called()
                    self.assertNotIn(host, str(caught.exception))

    def test_create_server_allows_localhost_and_ipv4_loopback_hosts(self) -> None:
        for host in ("localhost", "127.0.0.1", "127.0.0.2"):
            with self.subTest(host=host):
                with patch("backend.email_agent.server.EmailAssistantServer") as server_type:
                    created = create_server(host=host, port=8765, database_path=":memory:")
                self.assertIs(created, server_type.return_value)
                server_type.assert_called_once()

    def test_analyze_endpoint_rejects_negative_content_length_without_reading_body(self) -> None:
        handler = self._direct_handler()
        handler.headers.replace_header("Content-Length", "-1")

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
        config = replace(load_config(dotenv_path=None), llm_provider="disabled")
        server = create_server(
            host="127.0.0.1", port=0, database_path=":memory:", config=config
        )
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
