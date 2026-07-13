"""Local HTTP server for the first-version assistant window."""

from __future__ import annotations

import json
import mimetypes
import re
import sqlite3
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address, ip_address
from pathlib import Path
from typing import Any

from .analysis_budget import AnalysisBudget
from .api import handle_analyze_current_email
from .config import AppConfig, load_config
from .database import (
    PersistenceConnectionPoisoned,
    connect,
    initialize_schema,
    save_analysis,
)


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = ROOT / "frontend" / "local_debug_page"
INVALID_HOST_MESSAGE = "Request Host is not allowed."
UNSUPPORTED_MEDIA_TYPE_MESSAGE = "Content-Type must be application/json."
PERSISTENCE_MAX_SECONDS = 0.5
PERSISTENCE_RESPONSE_FLOOR_SECONDS = 0.25
PERSISTENCE_ERROR_CODE = "PERSISTENCE_FAILED"
PERSISTENCE_ERROR_MESSAGE = "Analysis result could not be saved."


class EmailAssistantServer(ThreadingHTTPServer):
    """HTTP server carrying local persistence state for request handlers."""

    def __init__(
        self,
        address: tuple[str, int],
        database_path: str | None = None,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(address, EmailAssistantHandler)
        self.database = connect(database_path)
        self.database_lock = threading.Lock()
        self.attachment_config = config or load_config()
        initialize_schema(self.database)


class EmailAssistantHandler(BaseHTTPRequestHandler):
    server: EmailAssistantServer

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._send_json({"ok": True, "status": "ok"})
            return
        self._serve_frontend()

    def do_POST(self) -> None:
        if self.path != "/api/analyze-current-email":
            self._send_json({"ok": False, "error": {"code": "NOT_FOUND"}}, HTTPStatus.NOT_FOUND)
            return
        boundary_error = self._request_boundary_error()
        if boundary_error is not None:
            code, message, status = boundary_error
            self._send_json(
                {"ok": False, "error": {"code": code, "message": message}},
                status,
            )
            return
        content_length_error = self._content_length_error()
        if content_length_error is not None:
            code, message, status = content_length_error
            self._send_json(
                {"ok": False, "error": {"code": code, "message": message}},
                status,
            )
            return
        budget = AnalysisBudget.start()
        payload = self._read_json()
        response = handle_analyze_current_email(
            payload, config=self.server.attachment_config, budget=budget
        )
        if response.get("ok"):
            saved_id = self._save_result(
                payload, response["analysis"], budget=budget
            )
            if saved_id is None:
                response = _persistence_error()
            else:
                response["saved_id"] = saved_id
        self._send_json(response)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress request logs so sample email content never appears in stdout.
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _content_length_error(self) -> tuple[str, str, HTTPStatus] | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return "INVALID_CONTENT_LENGTH", "Content-Length must be a non-negative integer.", HTTPStatus.BAD_REQUEST
        if content_length < 0:
            return "INVALID_CONTENT_LENGTH", "Content-Length must be a non-negative integer.", HTTPStatus.BAD_REQUEST
        max_encoded_attachment_bytes = ((self.server.attachment_config.attachment_max_total_bytes + 2) // 3) * 4
        if content_length > max_encoded_attachment_bytes + 64 * 1024:
            return (
                "REQUEST_TOO_LARGE",
                "Request exceeds the local attachment limit.",
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        return None

    def _request_boundary_error(self) -> tuple[str, str, HTTPStatus] | None:
        host_values = self._header_values("Host")
        if len(host_values) != 1 or not _allowed_request_host(
            host_values[0],
            self.server.server_port,
        ):
            return "INVALID_HOST", INVALID_HOST_MESSAGE, HTTPStatus.FORBIDDEN
        media_values = self._header_values("Content-Type")
        if len(media_values) != 1 or not _is_json_media_type(media_values[0]):
            return (
                "UNSUPPORTED_MEDIA_TYPE",
                UNSUPPORTED_MEDIA_TYPE_MESSAGE,
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )
        return None

    def _header_values(self, name: str) -> list[str]:
        get_all = getattr(self.headers, "get_all", None)
        if callable(get_all):
            return [str(value) for value in get_all(name, [])]
        value = self.headers.get(name)
        return [] if value is None else [str(value)]

    def _save_result(
        self,
        payload: dict[str, Any],
        analysis: dict[str, Any],
        *,
        budget: AnalysisBudget,
    ) -> int | None:
        deadline = budget.stage_deadline(
            PERSISTENCE_MAX_SECONDS,
            reserve_seconds=PERSISTENCE_RESPONSE_FLOOR_SECONDS,
        )
        lock_timeout = budget.remaining_until(deadline)
        if lock_timeout <= 0 or not self.server.database_lock.acquire(
            timeout=lock_timeout
        ):
            return None
        try:
            busy_timeout_ms = int(budget.remaining_until(deadline) * 1000)
            database = self.server.database
            if busy_timeout_ms <= 0 or database is None:
                return None
            return save_analysis(
                database,
                subject=str(payload.get("subject") or ""),
                sender=str(payload.get("from") or ""),
                analysis=analysis,
                busy_timeout_ms=busy_timeout_ms,
            )
        except PersistenceConnectionPoisoned:
            self.server.database = None
            return None
        except sqlite3.Error:
            return None
        finally:
            self.server.database_lock.release()

    def _serve_frontend(self) -> None:
        path = FRONTEND_ROOT / ("index.html" if self.path in {"/", "/index.html"} else self.path.lstrip("/"))
        if not path.exists() or FRONTEND_ROOT not in path.resolve().parents:
            self._send_json({"ok": False, "error": {"code": "NOT_FOUND"}}, HTTPStatus.NOT_FOUND)
            return
        content = path.read_bytes()
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    database_path: str | None = None,
    config: AppConfig | None = None,
) -> EmailAssistantServer:
    bind_host = validate_local_server_host(host)
    return EmailAssistantServer((bind_host, port), database_path=database_path, config=config)


def _persistence_error() -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": PERSISTENCE_ERROR_CODE,
            "message": PERSISTENCE_ERROR_MESSAGE,
        },
    }


def run_server(host: str = "127.0.0.1", port: int = 8765, database_path: str | None = None) -> None:
    server = create_server(host=host, port=port, database_path=database_path)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _allowed_request_host(value: str, server_port: int) -> bool:
    if value != value.strip() or "," in value or value.count(":") > 1:
        return False
    hostname, separator, port_text = value.partition(":")
    if separator:
        if not re.fullmatch(r"[0-9]{1,5}", port_text):
            return False
        port = int(port_text)
        if not 1 <= port <= 65535 or port != server_port:
            return False
    if hostname.casefold() == "localhost":
        return True
    try:
        address = ip_address(hostname)
    except ValueError:
        return False
    return isinstance(address, IPv4Address) and address.is_loopback


def _is_json_media_type(value: str) -> bool:
    if value != value.strip() or "," in value:
        return False
    parts = value.split(";")
    if parts[0].strip().casefold() != "application/json":
        return False
    if len(parts) == 1:
        return True
    return len(parts) == 2 and bool(
        re.fullmatch(r"\s*charset\s*=\s*(?:\"?utf-8\"?)\s*", parts[1], re.IGNORECASE)
    )


def validate_local_server_host(host: str) -> str:
    """Return a canonical supported bind host or raise a generic error."""
    if not isinstance(host, str) or host != host.strip():
        raise ValueError("Server host must be a supported loopback address.")
    if host.casefold() == "localhost":
        return "localhost"
    try:
        address = ip_address(host)
    except ValueError:
        raise ValueError("Server host must be a supported loopback address.") from None
    if not isinstance(address, IPv4Address) or not address.is_loopback:
        raise ValueError("Server host must be a supported loopback address.")
    return str(address)
