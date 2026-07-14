"""Logging configuration for backend code."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 2
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(
    level: str = "INFO", *, log_file: str | Path | None = None
) -> None:
    # Central logging keeps backend modules from using print() for operations.
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handlers: list[logging.Handler]
    if log_file is None:
        handlers = [logging.StreamHandler()]
    else:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers = [
            RotatingFileHandler(
                path,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
        ]
    logging.basicConfig(
        level=numeric_level,
        format=LOG_FORMAT,
        handlers=handlers,
        force=True,
    )
