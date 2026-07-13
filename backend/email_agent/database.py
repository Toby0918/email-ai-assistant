"""SQLite persistence boundary for analysis results."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .analysis_projection import project_analysis_for_storage
from .config import load_config


# Local SQLite is for debug/history only, not for live mailbox integration.
SCHEMA = """
CREATE TABLE IF NOT EXISTS email_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class PersistenceConnectionPoisoned(sqlite3.DatabaseError):
    """Raised when a failed transaction cannot be rolled back or closed."""


def connect(
    path: str | None = None,
    *,
    busy_timeout_seconds: float = 0.5,
) -> sqlite3.Connection:
    if path == ":memory:":
        return sqlite3.connect(
            ":memory:", timeout=busy_timeout_seconds, check_same_thread=False
        )
    database_path = Path(path or load_config().sqlite_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(
        database_path, timeout=busy_timeout_seconds, check_same_thread=False
    )


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.execute(SCHEMA)
    connection.commit()


def save_analysis(
    connection: sqlite3.Connection,
    subject: str,
    sender: str,
    analysis: dict[str, Any],
    *,
    busy_timeout_ms: int = 500,
) -> int:
    deadline = time.monotonic() + max(0, busy_timeout_ms) / 1000
    # Persist only the documented structured result and projected attachment insights.
    stored_analysis = project_analysis_for_storage(analysis)
    try:
        _set_busy_timeout_until(connection, deadline)
        cursor = connection.execute(
            "INSERT INTO email_analysis (subject, sender, analysis_json) VALUES (?, ?, ?)",
            (subject, sender, json.dumps(stored_analysis, ensure_ascii=False)),
        )
        _set_busy_timeout_until(connection, deadline)
        connection.commit()
    except sqlite3.Error:
        if not _rollback_after_failure(connection):
            raise PersistenceConnectionPoisoned(
                "Persistence connection could not be quarantined."
            ) from None
        raise
    return int(cursor.lastrowid)


def _set_busy_timeout_until(
    connection: sqlite3.Connection,
    deadline: float,
) -> None:
    remaining_ms = int((deadline - time.monotonic()) * 1000)
    if remaining_ms <= 0:
        raise sqlite3.OperationalError("Persistence deadline expired.")
    connection.execute(f"PRAGMA busy_timeout = {remaining_ms}")


def _rollback_after_failure(connection: sqlite3.Connection) -> bool:
    try:
        connection.rollback()
        return True
    except sqlite3.Error:
        return _close_after_failed_rollback(connection)


def _close_after_failed_rollback(connection: sqlite3.Connection) -> bool:
    try:
        connection.close()
        return True
    except sqlite3.Error:
        return False
