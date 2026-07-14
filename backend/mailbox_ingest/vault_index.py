"""Metadata-only SQLite index and exclusive vault mutation lock."""

from __future__ import annotations

import os
import re
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from .errors import VaultError
from .models import VaultRecord


APPLICATION_ID = 0x4D42564C
SCHEMA_VERSION = 1
MAX_BATCH_LIMIT = 1_000
_RECORD_ID = re.compile(r"^[0-9a-f]{32}$")
_RECORD_PATH = re.compile(r"^records/[0-9a-f]{2}/[0-9a-f]{32}\.mvlt$")
_RECORD_STATES = {"active", "delete_pending"}
_VAULT_STATES = {"active", "revoking", "revoke_incomplete", "revoked"}
_RECORD_COLUMNS = (
    "record_id", "encrypted_relpath", "dedup_hmac", "created_at_utc",
    "expires_at_utc", "ciphertext_size", "format_version", "key_version",
    "lifecycle_state",
)
_STATE_COLUMNS = ("singleton", "vault_id", "lifecycle_state")


class VaultMutationLock:
    """Fail closed when another mutation is in progress or left a stale lock."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._descriptor: int | None = None

    def __enter__(self) -> "VaultMutationLock":
        if self._descriptor is not None:
            raise VaultError("vault_busy")
        try:
            self._descriptor = os.open(
                self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            os.fsync(self._descriptor)
        except FileExistsError:
            raise VaultError("vault_busy") from None
        except OSError:
            raise VaultError("vault_busy") from None
        return self

    def __exit__(self, *_args: object) -> None:
        descriptor, self._descriptor = self._descriptor, None
        if descriptor is not None:
            try:
                os.close(descriptor)
            finally:
                try:
                    self._path.unlink(missing_ok=True)
                except OSError:
                    pass

    def __repr__(self) -> str:
        return "VaultMutationLock(<redacted>)"


class VaultIndex:
    def __init__(self, path: Path, *, vault_id: str) -> None:
        self._path = Path(path)
        try:
            parsed = uuid.UUID(vault_id)
        except (ValueError, AttributeError):
            raise VaultError("invalid_vault_id") from None
        if str(parsed) != vault_id:
            raise VaultError("invalid_vault_id")
        self._vault_id = vault_id

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA temp_store=MEMORY")
        return connection

    def initialize(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(_CREATE_RECORDS)
                connection.execute(_CREATE_STATE)
                connection.execute(
                    "INSERT OR IGNORE INTO vault_state VALUES (1, ?, 'active')",
                    (self._vault_id,),
                )
                connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                connection.commit()
            self._validate_schema()
        except VaultError:
            raise
        except (OSError, sqlite3.Error):
            raise VaultError("index_initialize_failed") from None

    def _validate_schema(self) -> None:
        try:
            with closing(self._connect()) as connection:
                tables = {
                    row[0] for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                records = tuple(
                    row[1] for row in connection.execute("PRAGMA table_info(records)")
                )
                state_columns = tuple(
                    row[1] for row in connection.execute("PRAGMA table_info(vault_state)")
                )
                state_rows = list(
                    connection.execute(
                        "SELECT singleton,vault_id,lifecycle_state FROM vault_state"
                    )
                )
                identifiers = (
                    connection.execute("PRAGMA application_id").fetchone()[0],
                    connection.execute("PRAGMA user_version").fetchone()[0],
                )
        except sqlite3.Error:
            raise VaultError("index_schema_invalid") from None
        if tables != {"records", "vault_state"}:
            raise VaultError("index_schema_invalid")
        if records != _RECORD_COLUMNS or state_columns != _STATE_COLUMNS:
            raise VaultError("index_schema_invalid")
        if identifiers != (APPLICATION_ID, SCHEMA_VERSION):
            raise VaultError("index_schema_invalid")
        if len(state_rows) != 1:
            raise VaultError("index_schema_invalid")
        state_row = state_rows[0]
        if state_row[0] != 1 or state_row[1] != self._vault_id:
            raise VaultError("index_schema_invalid")
        if state_row[2] not in _VAULT_STATES:
            raise VaultError("index_schema_invalid")

    def add_record(self, record: VaultRecord) -> None:
        _validate_record(record)
        values = tuple(getattr(record, column) for column in _RECORD_COLUMNS)
        placeholders = ",".join("?" for _ in _RECORD_COLUMNS)
        sql = f"INSERT INTO records VALUES ({placeholders})"
        self._write(sql, values)

    def get_record(self, record_id: str) -> VaultRecord | None:
        _validate_record_id(record_id)
        rows = self._read(
            "SELECT * FROM records WHERE record_id = ?", (record_id,)
        )
        return None if not rows else _row_to_record(rows[0])

    def list_records(self) -> list[VaultRecord]:
        return [
            _row_to_record(row)
            for row in self._read("SELECT * FROM records ORDER BY record_id", ())
        ]

    def mark_delete_pending(self, record_id: str) -> None:
        _validate_record_id(record_id)
        self._write(
            "UPDATE records SET lifecycle_state='delete_pending' WHERE record_id=?",
            (record_id,),
        )

    def delete_record(self, record_id: str) -> None:
        _validate_record_id(record_id)
        self._write("DELETE FROM records WHERE record_id=?", (record_id,))

    def list_expired(self, *, now_utc: int, limit: int) -> list[VaultRecord]:
        _validate_limit(limit)
        if type(now_utc) is not int:
            raise VaultError("invalid_expiry")
        rows = self._read(
            "SELECT * FROM records WHERE lifecycle_state='active' "
            "AND expires_at_utc<=? ORDER BY expires_at_utc,record_id LIMIT ?",
            (now_utc, limit),
        )
        return [_row_to_record(row) for row in rows]

    def count_expired(self, *, now_utc: int) -> int:
        rows = self._read(
            "SELECT COUNT(*) AS count FROM records WHERE lifecycle_state='active' "
            "AND expires_at_utc<=?", (now_utc,),
        )
        return int(rows[0]["count"])

    def list_delete_pending(self, *, limit: int) -> list[VaultRecord]:
        _validate_limit(limit)
        rows = self._read(
            "SELECT * FROM records WHERE lifecycle_state='delete_pending' "
            "ORDER BY record_id LIMIT ?", (limit,),
        )
        return [_row_to_record(row) for row in rows]

    def count_delete_pending(self) -> int:
        rows = self._read(
            "SELECT COUNT(*) AS count FROM records "
            "WHERE lifecycle_state='delete_pending'", ()
        )
        return int(rows[0]["count"])

    def get_vault_state(self) -> str:
        rows = self._read(
            "SELECT lifecycle_state FROM vault_state WHERE singleton=1", ()
        )
        if len(rows) != 1:
            raise VaultError("index_schema_invalid")
        return str(rows[0]["lifecycle_state"])

    def set_vault_state(self, state: str) -> None:
        if state not in _VAULT_STATES:
            raise VaultError("invalid_lifecycle_state")
        self._write(
            "UPDATE vault_state SET lifecycle_state=? WHERE singleton=1", (state,)
        )

    def _write(self, sql: str, parameters: tuple[object, ...]) -> None:
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(sql, parameters)
                connection.commit()
        except sqlite3.Error:
            raise VaultError("index_write_failed") from None

    def _read(
        self, sql: str, parameters: tuple[object, ...]
    ) -> list[sqlite3.Row]:
        try:
            with closing(self._connect()) as connection:
                return list(connection.execute(sql, parameters).fetchall())
        except sqlite3.Error:
            raise VaultError("index_read_failed") from None


def _validate_record(record: VaultRecord) -> None:
    if not isinstance(record, VaultRecord):
        raise VaultError("invalid_record_metadata")
    _validate_record_id(record.record_id)
    if _RECORD_PATH.fullmatch(record.encrypted_relpath) is None:
        raise VaultError("invalid_record_metadata")
    if type(record.dedup_hmac) is not bytes or len(record.dedup_hmac) != 32:
        raise VaultError("invalid_record_metadata")
    integer_values = (
        record.created_at_utc, record.expires_at_utc, record.ciphertext_size,
        record.format_version, record.key_version,
    )
    if any(type(value) is not int or value < 0 for value in integer_values):
        raise VaultError("invalid_record_metadata")
    if record.format_version != 1 or record.key_version != 1:
        raise VaultError("invalid_record_metadata")
    if record.lifecycle_state not in _RECORD_STATES:
        raise VaultError("invalid_record_metadata")


def _validate_record_id(record_id: str) -> None:
    if not isinstance(record_id, str) or _RECORD_ID.fullmatch(record_id) is None:
        raise VaultError("invalid_record_id")


def _validate_limit(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH_LIMIT:
        raise VaultError("invalid_limit")


def _row_to_record(row: sqlite3.Row) -> VaultRecord:
    return VaultRecord(**{column: row[column] for column in _RECORD_COLUMNS})


_CREATE_RECORDS = """
CREATE TABLE IF NOT EXISTS records (
    record_id TEXT PRIMARY KEY,
    encrypted_relpath TEXT NOT NULL UNIQUE,
    dedup_hmac BLOB NOT NULL,
    created_at_utc INTEGER NOT NULL,
    expires_at_utc INTEGER NOT NULL,
    ciphertext_size INTEGER NOT NULL,
    format_version INTEGER NOT NULL,
    key_version INTEGER NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('active','delete_pending'))
)
"""

_CREATE_STATE = """
CREATE TABLE IF NOT EXISTS vault_state (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    vault_id TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(
        lifecycle_state IN ('active','revoking','revoke_incomplete','revoked')
    )
)
"""
