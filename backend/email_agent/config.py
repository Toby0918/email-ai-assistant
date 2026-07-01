"""Backend configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str | None
    sqlite_path: str
    log_level: str


def load_config() -> AppConfig:
    # Secrets stay on the backend and are loaded from the local environment only.
    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        sqlite_path=os.getenv("EMAIL_AGENT_SQLITE_PATH", "outputs/email_agent.sqlite3"),
        log_level=os.getenv("EMAIL_AGENT_LOG_LEVEL", "INFO"),
    )
