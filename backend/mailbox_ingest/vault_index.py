"""Authenticated SQLite index and exclusive vault mutation lock."""

from __future__ import annotations

import hmac
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Callable, TypeVar

from ._vault_index_auth import (
    decode_intent,
    decode_record,
)
from ._vault_index_mutations import (
    activate_reserved as _activate_reserved,
    add_record as _add_record,
    constrain_intent_expiry as _constrain_intent_expiry,
    mark_delete_pending as _mark_delete_pending,
    reserve_write as _reserve_write,
    update_record_expiry as _update_record_expiry,
)
from ._vault_index_records import (
    validate_digest as _validate_digest,
    validate_limit as _validate_limit,
    validate_record_id as _validate_record_id,
)
from ._vault_index_schema import (
    APPLICATION_ID,
    MAX_BATCH_LIMIT,
    SCHEMA_VERSION,
    VAULT_STATES as _VAULT_STATES,
    initialize_index,
    validate_index_schema,
)
from .errors import VaultError
from .models import VaultRecord, VaultWriteIntent
from .vault_crypto import VaultCrypto
from .vault_lock import VaultMutationLock


Result = TypeVar("Result")
Mutation = Callable[..., Result]


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
        self._crypto: VaultCrypto | None = None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA temp_store=MEMORY")
        except sqlite3.Error:
            try:
                connection.close()
            except sqlite3.Error:
                pass
            raise
        return connection

    def initialize(self) -> None:
        initialize_index(self._path, self._vault_id, self._connect)

    def bind_metadata_authenticator(self, crypto: VaultCrypto) -> None:
        if not isinstance(crypto, VaultCrypto):
            raise VaultError("record_authentication_failed")
        if self._crypto is not None and self._crypto is not crypto:
            raise VaultError("record_authentication_failed")
        validate_index_schema(self._vault_id, self._connect)
        self._crypto = crypto
        self.list_records()
        self.list_write_intents()

    def add_record(self, record: VaultRecord) -> None:
        self._mutate(_add_record, record)

    def reserve_write(self, intent: VaultWriteIntent) -> VaultWriteIntent:
        return self._mutate(_reserve_write, intent)

    def find_write_intent(self, dedup_hmac: bytes) -> VaultWriteIntent | None:
        _validate_digest(dedup_hmac)
        matches = [
            row for row in self.list_write_intents()
            if hmac.compare_digest(row.dedup_hmac, dedup_hmac)
        ]
        if len(matches) > 1:
            raise VaultError("index_schema_invalid")
        return None if not matches else matches[0]

    def list_write_intents(self) -> list[VaultWriteIntent]:
        crypto = self._require_crypto()
        return [
            decode_intent(row, crypto)
            for row in self._read(
                "SELECT * FROM write_intents ORDER BY record_id", ()
            )
        ]

    def constrain_write_intent_expiry(
        self, record_id: str, expires_at_utc: int,
    ) -> VaultWriteIntent:
        return self._mutate(
            _constrain_intent_expiry, record_id, expires_at_utc,
        )

    def activate_reserved(self, record_id: str) -> VaultRecord:
        return self._mutate(_activate_reserved, record_id)

    def delete_write_intent(self, record_id: str) -> None:
        _validate_record_id(record_id)
        self._write("DELETE FROM write_intents WHERE record_id=?", (record_id,))

    def get_record(self, record_id: str) -> VaultRecord | None:
        _validate_record_id(record_id)
        return next(
            (row for row in self.list_records() if row.record_id == record_id),
            None,
        )

    def find_by_dedup_hmac(self, dedup_hmac: bytes) -> VaultRecord | None:
        _validate_digest(dedup_hmac)
        matches = [
            row for row in self.list_records()
            if row.lifecycle_state == "active"
            and hmac.compare_digest(row.dedup_hmac, dedup_hmac)
        ]
        if len(matches) > 1:
            raise VaultError("index_schema_invalid")
        return None if not matches else matches[0]

    def validate(self) -> None:
        validate_index_schema(self._vault_id, self._connect)
        if self._crypto is not None:
            self.list_records()
            self.list_write_intents()

    def list_records(self) -> list[VaultRecord]:
        crypto = self._require_crypto()
        return [
            decode_record(row, crypto)
            for row in self._read("SELECT * FROM records ORDER BY record_id", ())
        ]

    def mark_delete_pending(self, record_id: str) -> None:
        self._mutate(_mark_delete_pending, record_id)

    def extend_expiry(self, record_id: str, expires_at_utc: int) -> None:
        self._mutate(
            _update_record_expiry, record_id, expires_at_utc, extend=True,
        )

    def constrain_expiry(self, record_id: str, expires_at_utc: int) -> None:
        self._mutate(
            _update_record_expiry, record_id, expires_at_utc, extend=False,
        )

    def delete_record(self, record_id: str) -> None:
        _validate_record_id(record_id)
        self._write("DELETE FROM records WHERE record_id=?", (record_id,))

    def list_expired(self, *, now_utc: int, limit: int) -> list[VaultRecord]:
        _validate_time_and_limit(now_utc, limit)
        records = [
            row for row in self.list_records()
            if row.lifecycle_state == "active" and row.expires_at_utc <= now_utc
        ]
        return sorted(
            records, key=lambda row: (row.expires_at_utc, row.record_id),
        )[:limit]

    def count_expired(self, *, now_utc: int) -> int:
        _validate_time(now_utc)
        return sum(
            row.lifecycle_state == "active" and row.expires_at_utc <= now_utc
            for row in self.list_records()
        )

    def list_expired_write_intents(
        self, *, now_utc: int, limit: int,
    ) -> list[VaultWriteIntent]:
        _validate_time_and_limit(now_utc, limit)
        intents = [
            row for row in self.list_write_intents()
            if row.expires_at_utc <= now_utc
        ]
        return sorted(
            intents, key=lambda row: (row.expires_at_utc, row.record_id),
        )[:limit]

    def count_expired_write_intents(self, *, now_utc: int) -> int:
        _validate_time(now_utc)
        return sum(
            row.expires_at_utc <= now_utc for row in self.list_write_intents()
        )

    def list_delete_pending(self, *, limit: int) -> list[VaultRecord]:
        _validate_limit(limit)
        return [
            row for row in self.list_records()
            if row.lifecycle_state == "delete_pending"
        ][:limit]

    def count_delete_pending(self) -> int:
        return sum(
            row.lifecycle_state == "delete_pending" for row in self.list_records()
        )

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

    def _require_crypto(self) -> VaultCrypto:
        if self._crypto is None:
            raise VaultError("record_authentication_failed")
        return self._crypto

    def _mutate(
        self, operation: Mutation[Result], *args: object, **kwargs: object,
    ) -> Result:
        try:
            with closing(self._connect()) as connection:
                return operation(
                    connection, self._require_crypto(), *args, **kwargs,
                )
        except VaultError:
            raise
        except sqlite3.Error:
            raise VaultError("index_write_failed") from None

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


def _validate_time(now_utc: int) -> None:
    if type(now_utc) is not int:
        raise VaultError("invalid_expiry")


def _validate_time_and_limit(now_utc: int, limit: int) -> None:
    _validate_time(now_utc)
    _validate_limit(limit)
