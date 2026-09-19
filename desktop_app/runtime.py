"""Own a fresh local service and its lifetime without the legacy launcher."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import urllib.request
from dataclasses import replace
from pathlib import Path

from backend.email_agent.config import build_standalone_verification_config
from backend.email_agent.server import EmailAssistantServer


def default_data_root() -> Path:
    return project_root() / "Data"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        # Distribution is Project/Program/EmailAssistant/EmailAssistant.exe.
        return Path(sys.executable).resolve().parents[2]
    return Path(__file__).resolve().parents[1]


class DesktopRuntime:
    """Start/stop one loopback service with independent, explicit configuration."""

    def __init__(self, data_root: Path, *, port: int = 8765):
        if sys.version_info[:3] != (3, 14, 7):
            raise RuntimeError("RUNTIME_VERSION_MISMATCH")
        self.data_root = Path(data_root).absolute()
        self.port = port
        self._server = None
        self._thread = None
        self._base_config = replace(build_standalone_verification_config(
            sqlite_path=self.data_root / "analysis.sqlite3",
            attachment_temp_dir=self.data_root / "attachment_temp",
        ), internal_email_domains=())
        self.provider = "disabled"

    @property
    def url(self) -> str:
        if self._server is None:
            raise RuntimeError("SERVICE_NOT_RUNNING")
        return f"http://127.0.0.1:{self._server.server_port}"

    def start(self) -> None:
        if self._server is not None:
            return
        self.data_root.mkdir(parents=True, exist_ok=True)
        server = EmailAssistantServer(
            ("127.0.0.1", self.port), database_path=self._base_config.sqlite_path,
            config=self._base_config, runtime_cards=(),
        )
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    def configure_provider(self, provider: str, api_key: str = "") -> None:
        if provider not in {"disabled", "openai", "deepseek"}:
            raise ValueError("PROVIDER_INVALID")
        if provider != "disabled" and (not api_key.strip() or len(api_key) > 512):
            raise ValueError("API_KEY_REQUIRED")
        if self._server is None:
            raise RuntimeError("SERVICE_NOT_RUNNING")
        self._server.attachment_config = replace(
            self._base_config, llm_provider=provider,
            openai_api_key=api_key.strip() if provider == "openai" else None,
            deepseek_api_key=api_key.strip() if provider == "deepseek" else None,
        )
        self.provider = provider

    def analyze(self, payload: dict) -> dict:
        request = urllib.request.Request(
            self.url + "/api/analyze-current-email",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        # A proxy environment must never redirect current-email content off loopback.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=60) as response:
            return json.load(response)

    def close(self) -> None:
        server = self._server
        if server is None:
            return
        server.shutdown()
        server.server_close()
        with server.database_lock:
            server.database.close()
        server.attachment_config = self._base_config
        self._server = None
        self._thread = None
        self.provider = "disabled"
