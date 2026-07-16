"""Backend configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:
    _load_dotenv = None


DEFAULT_DOTENV_PATH = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str | None
    sqlite_path: str
    log_level: str
    llm_provider: str
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: int
    attachment_temp_dir: str
    attachment_retention_hours: int
    attachment_max_files: int
    attachment_max_file_bytes: int
    attachment_max_total_bytes: int
    internal_email_domains: tuple[str, ...]
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_timeout_seconds: int = 10
    deepseek_output_mode: str = "conservative"
    private_knowledge_enabled: bool = False
    private_knowledge_authority_root: str = field(default="", repr=False)
    private_knowledge_snapshot_path: str = field(default="", repr=False)


def load_config(dotenv_path: str | Path | None = DEFAULT_DOTENV_PATH) -> AppConfig:
    # Secrets stay on the backend and are loaded from the local environment only.
    if dotenv_path is not None:
        _load_backend_dotenv(Path(dotenv_path))
    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_model=os.getenv("EMAIL_AGENT_DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
        or "deepseek-v4-flash",
        deepseek_timeout_seconds=min(_int_env("EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS", 10), 10),
        deepseek_output_mode=os.getenv("EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE", "conservative").strip().lower()
        or "conservative",
        sqlite_path=os.getenv("EMAIL_AGENT_SQLITE_PATH", "outputs/email_agent.sqlite3"),
        log_level=os.getenv("EMAIL_AGENT_LOG_LEVEL", "INFO"),
        llm_provider=os.getenv("EMAIL_AGENT_LLM_PROVIDER", "disabled").strip().lower() or "disabled",
        ollama_base_url=_trim_base_url(os.getenv("EMAIL_AGENT_OLLAMA_BASE_URL", "http://127.0.0.1:11434")),
        ollama_model=os.getenv("EMAIL_AGENT_OLLAMA_MODEL", "qwen3.6:latest").strip() or "qwen3.6:latest",
        ollama_timeout_seconds=_int_env("EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS", 30),
        attachment_temp_dir=os.getenv("EMAIL_AGENT_ATTACHMENT_TEMP_DIR", "outputs/attachment_temp"),
        attachment_retention_hours=_int_env("EMAIL_AGENT_ATTACHMENT_RETENTION_HOURS", 24),
        attachment_max_files=_int_env("EMAIL_AGENT_ATTACHMENT_MAX_FILES", 5),
        attachment_max_file_bytes=_int_env("EMAIL_AGENT_ATTACHMENT_MAX_FILE_BYTES", 10 * 1024 * 1024),
        attachment_max_total_bytes=_int_env("EMAIL_AGENT_ATTACHMENT_MAX_TOTAL_BYTES", 25 * 1024 * 1024),
        internal_email_domains=_csv_env("EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS", ("cndlf.com",)),
        private_knowledge_enabled=_true_env(
            "EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED"
        ),
        private_knowledge_authority_root=os.getenv(
            "EMAIL_AGENT_PRIVATE_KNOWLEDGE_AUTHORITY_ROOT", ""
        ),
        private_knowledge_snapshot_path=os.getenv(
            "EMAIL_AGENT_PRIVATE_KNOWLEDGE_SNAPSHOT_PATH", ""
        ),
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


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = tuple(value.strip().lower() for value in raw.split(",") if value.strip())
    return values or default


def _true_env(name: str) -> bool:
    raw = os.getenv(name)
    return isinstance(raw, str) and raw.strip().casefold() == "true"


def _load_backend_dotenv(dotenv_path: Path) -> None:
    if _load_dotenv is not None:
        _load_dotenv(dotenv_path=dotenv_path, override=False)
        return
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        key, value = _parse_dotenv_line(raw_line)
        if key and key not in os.environ:
            os.environ[key] = value


def _parse_dotenv_line(raw_line: str) -> tuple[str, str]:
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return "", ""
    if line.startswith("export "):
        line = line.removeprefix("export ").strip()
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    return key, value
