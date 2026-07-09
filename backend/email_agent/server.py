"""Local HTTP server for the first-version assistant window."""

from __future__ import annotations

import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .api import handle_analyze_current_email
from .config import AppConfig, load_config
from .database import connect, initialize_schema, save_analysis


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = ROOT / "frontend" / "local_debug_page"


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
        if self._content_length_exceeds_limit():
            self._send_json(
                {"ok": False, "error": {"code": "REQUEST_TOO_LARGE", "message": "Request exceeds the local attachment limit."}},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
            return
        payload = self._read_json()
        response = handle_analyze_current_email(payload, config=self.server.attachment_config)
        if response.get("ok"):
            response["saved_id"] = self._save_result(payload, response["analysis"])
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

    def _content_length_exceeds_limit(self) -> bool:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return True
        max_encoded_attachment_bytes = ((self.server.attachment_config.attachment_max_total_bytes + 2) // 3) * 4
        return content_length > max_encoded_attachment_bytes + 64 * 1024

    def _save_result(self, payload: dict[str, Any], analysis: dict[str, Any]) -> int:
        with self.server.database_lock:
            return save_analysis(
                self.server.database,
                subject=str(payload.get("subject") or ""),
                sender=str(payload.get("from") or ""),
                analysis=analysis,
            )

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
    # Bind locally by default; this server is for first-version development only.
    return EmailAssistantServer((host, port), database_path=database_path, config=config)


def run_server(host: str = "127.0.0.1", port: int = 8765, database_path: str | None = None) -> None:
    server = create_server(host=host, port=port, database_path=database_path)
    try:
        server.serve_forever()
    finally:
        server.server_close()
