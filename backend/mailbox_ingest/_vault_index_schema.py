"""Exact fresh-only SQLite schema for the encrypted mailbox vault."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Callable

from .errors import VaultError


APPLICATION_ID = 0x4D42564C
SCHEMA_VERSION = 3
MAX_BATCH_LIMIT = 1_000
RECORD_COLUMNS = (
    "record_id", "encrypted_relpath", "dedup_hmac", "created_at_utc",
    "expires_at_utc", "ciphertext_size", "format_version", "key_version",
    "lifecycle_state", "metadata_mac",
)
STATE_COLUMNS = ("singleton", "vault_id", "lifecycle_state")
INTENT_COLUMNS = RECORD_COLUMNS[:-2] + ("metadata_mac",)
VAULT_STATES = {"active", "revoking", "revoke_incomplete", "revoked"}
Connect = Callable[[], sqlite3.Connection]


def initialize_index(path: Path, vault_id: str, connect: Connect) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(connect()) as connection:
            existing = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
            if not existing:
                _create_fresh_schema(connection, vault_id)
        validate_index_schema(vault_id, connect)
    except VaultError:
        raise
    except (OSError, sqlite3.Error):
        raise VaultError("index_initialize_failed") from None


def validate_index_schema(vault_id: str, connect: Connect) -> None:
    try:
        snapshot = _read_schema(connect)
    except sqlite3.Error:
        raise VaultError("index_schema_invalid") from None
    (
        tables, records, intents, state_columns, state_rows,
        identifiers, objects,
    ) = snapshot
    if tables != {"records", "write_intents", "vault_state"}:
        raise VaultError("index_schema_invalid")
    if (
        records != RECORD_COLUMNS
        or intents != INTENT_COLUMNS
        or state_columns != STATE_COLUMNS
        or identifiers != (APPLICATION_ID, SCHEMA_VERSION)
        or objects != _expected_schema_objects()
    ):
        raise VaultError("index_schema_invalid")
    if len(state_rows) != 1:
        raise VaultError("index_schema_invalid")
    state_row = state_rows[0]
    if state_row[0] != 1 or state_row[1] != vault_id:
        raise VaultError("index_schema_invalid")
    if state_row[2] not in VAULT_STATES:
        raise VaultError("index_schema_invalid")


def _create_fresh_schema(
    connection: sqlite3.Connection, vault_id: str,
) -> None:
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(_CREATE_RECORDS)
    connection.execute(_CREATE_INTENTS)
    connection.execute(_CREATE_STATE)
    connection.execute(
        "INSERT INTO vault_state VALUES (1, ?, 'active')", (vault_id,),
    )
    connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
    connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    connection.commit()


def _read_schema(connect: Connect) -> tuple[object, ...]:
    with closing(connect()) as connection:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        columns = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(records)")
        )
        intents = tuple(
            row[1] for row in connection.execute(
                "PRAGMA table_info(write_intents)"
            )
        )
        state = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(vault_state)")
        )
        state_rows = list(connection.execute(
            "SELECT singleton,vault_id,lifecycle_state FROM vault_state"
        ))
        identifiers = (
            connection.execute("PRAGMA application_id").fetchone()[0],
            connection.execute("PRAGMA user_version").fetchone()[0],
        )
        objects = tuple(
            (
                row[0], row[1], row[2],
                None if row[3] is None else _canonical_sql(row[3]),
            )
            for row in connection.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master "
                "ORDER BY type,name"
            )
        )
    return tables, columns, intents, state, state_rows, identifiers, objects


def _expected_schema_objects() -> tuple[tuple[object, ...], ...]:
    return (
        ("index", "sqlite_autoindex_records_1", "records", None),
        ("index", "sqlite_autoindex_records_2", "records", None),
        ("index", "sqlite_autoindex_write_intents_1", "write_intents", None),
        ("index", "sqlite_autoindex_write_intents_2", "write_intents", None),
        ("index", "sqlite_autoindex_write_intents_3", "write_intents", None),
        ("table", "records", "records", _canonical_sql(_CREATE_RECORDS)),
        ("table", "vault_state", "vault_state", _canonical_sql(_CREATE_STATE)),
        (
            "table", "write_intents", "write_intents",
            _canonical_sql(_CREATE_INTENTS),
        ),
    )


def _canonical_sql(value: str) -> str:
    return " ".join(value.split())


_CREATE_RECORDS = """
CREATE TABLE records (
    record_id TEXT PRIMARY KEY,
    encrypted_relpath TEXT NOT NULL UNIQUE,
    dedup_hmac BLOB NOT NULL,
    created_at_utc INTEGER NOT NULL,
    expires_at_utc INTEGER NOT NULL,
    ciphertext_size INTEGER NOT NULL,
    format_version INTEGER NOT NULL,
    key_version INTEGER NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('active','delete_pending')),
    metadata_mac BLOB NOT NULL
)
"""

_CREATE_INTENTS = """
CREATE TABLE write_intents (
    record_id TEXT PRIMARY KEY,
    encrypted_relpath TEXT NOT NULL UNIQUE,
    dedup_hmac BLOB NOT NULL UNIQUE,
    created_at_utc INTEGER NOT NULL,
    expires_at_utc INTEGER NOT NULL,
    ciphertext_size INTEGER NOT NULL,
    format_version INTEGER NOT NULL,
    key_version INTEGER NOT NULL,
    metadata_mac BLOB NOT NULL
)
"""

_CREATE_STATE = """
CREATE TABLE vault_state (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    vault_id TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(
        lifecycle_state IN ('active','revoking','revoke_incomplete','revoked')
    )
)
"""
