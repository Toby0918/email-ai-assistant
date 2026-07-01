"""Logging configuration for backend code."""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    # Central logging keeps backend modules from using print() for operations.
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
