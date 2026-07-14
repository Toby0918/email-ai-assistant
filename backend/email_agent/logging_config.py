"""Logging configuration for backend code."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .analysis_diagnostics import (
    FALLBACK_DETAILS,
    FALLBACK_EVENT_TEMPLATE,
    FALLBACK_REASON_CODES,
    FALLBACK_STAGES,
    SAFE_MODELS,
    SAFE_OUTPUT_MODES,
    SAFE_PROVIDERS,
)


LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 2
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DIAGNOSTIC_LOGGER_NAME = "backend.email_agent.analysis_diagnostics"
_CANONICAL_PROVIDERS = SAFE_PROVIDERS | {"unknown"}
_CANONICAL_MODELS = SAFE_MODELS | {"unknown"}
_CANONICAL_OUTPUT_MODES = SAFE_OUTPUT_MODES | {"unknown"}


class _FallbackEventFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if (
            record.name != DIAGNOSTIC_LOGGER_NAME
            or record.levelno != logging.WARNING
            or type(record.msg) is not str
            or record.msg != FALLBACK_EVENT_TEMPLATE
            or type(record.args) is not tuple
            or len(record.args) != 7
            or record.exc_info is not None
            or record.exc_text is not None
            or record.stack_info is not None
        ):
            return False
        code, stage, provider, model, output_mode, detail, elapsed_ms = record.args
        if type(detail) is not str or detail not in FALLBACK_DETAILS:
            return False
        if code != "envelope_invalid" and detail != "not_applicable":
            return False
        return (
            type(code) is str and code in FALLBACK_REASON_CODES
            and type(stage) is str and stage in FALLBACK_STAGES
            and type(provider) is str and provider in _CANONICAL_PROVIDERS
            and type(model) is str and model in _CANONICAL_MODELS
            and type(output_mode) is str
            and output_mode in _CANONICAL_OUTPUT_MODES
            and type(elapsed_ms) is int and elapsed_ms >= 0
        )


def configure_logging(
    level: str = "INFO", *, log_file: str | Path | None = None
) -> None:
    numeric_level = logging.getLevelNamesMapping().get(
        level.upper() if type(level) is str else "", logging.INFO
    )
    root = logging.getLogger()
    diagnostic = logging.getLogger(DIAGNOSTIC_LOGGER_NAME)
    for configured_logger in (root, diagnostic):
        for old_handler in configured_logger.handlers[:]:
            configured_logger.removeHandler(old_handler)
            old_handler.close()

    if log_file is None:
        handler: logging.Handler = logging.StreamHandler()
    else:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(_FallbackEventFilter())
    root.setLevel(numeric_level)
    diagnostic.setLevel(logging.WARNING)
    diagnostic.disabled = False
    diagnostic.propagate = False
    diagnostic.addHandler(handler)
