"""Backend configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str | None
    sqlite_path: str
    log_level: str
    llm_provider: str
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: int


def load_config() -> AppConfig:
    # Secrets stay on the backend and are loaded from the local environment only.
    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        sqlite_path=os.getenv("EMAIL_AGENT_SQLITE_PATH", "outputs/email_agent.sqlite3"),
        log_level=os.getenv("EMAIL_AGENT_LOG_LEVEL", "INFO"),
        llm_provider=os.getenv("EMAIL_AGENT_LLM_PROVIDER", "disabled").strip().lower() or "disabled",
        ollama_base_url=_trim_base_url(os.getenv("EMAIL_AGENT_OLLAMA_BASE_URL", "http://127.0.0.1:11434")),
        ollama_model=os.getenv("EMAIL_AGENT_OLLAMA_MODEL", "qwen3.6:latest").strip() or "qwen3.6:latest",
        ollama_timeout_seconds=_int_env("EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS", 30),
    )


def _trim_base_url(value: str) -> str:
    return value.strip().rstrip("/") or "http://127.0.0.1:11434"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default
