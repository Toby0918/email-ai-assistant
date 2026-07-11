"""SQLite persistence boundary for analysis results."""

from __future__ import annotations

import json
import sqlite3
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


def connect(path: str | None = None) -> sqlite3.Connection:
    if path == ":memory:":
        return sqlite3.connect(":memory:", check_same_thread=False)
    database_path = Path(path or load_config().sqlite_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(database_path, check_same_thread=False)


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.execute(SCHEMA)
    connection.commit()


def save_analysis(
    connection: sqlite3.Connection,
    subject: str,
    sender: str,
    analysis: dict[str, Any],
) -> int:
    # Persist only the documented structured result and projected attachment insights.
    stored_analysis = project_analysis_for_storage(analysis)
    cursor = connection.execute(
        "INSERT INTO email_analysis (subject, sender, analysis_json) VALUES (?, ?, ?)",
        (subject, sender, json.dumps(stored_analysis, ensure_ascii=False)),
    )
    connection.commit()
    return int(cursor.lastrowid)
