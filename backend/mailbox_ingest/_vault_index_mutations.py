"""Authenticated, transactional mutations for vault index rows."""

from __future__ import annotations

import hmac
import sqlite3
from dataclasses import replace

from ._vault_index_auth import (
    load_intents,
    load_records,
    sign_intent,
    sign_record,
)
from ._vault_index_records import validate_record_id
from ._vault_index_schema import INTENT_COLUMNS, RECORD_COLUMNS
from .errors import VaultError
from .models import VaultRecord, VaultWriteIntent
from .vault_crypto import VaultCrypto


def add_record(
    connection: sqlite3.Connection, crypto: VaultCrypto, record: VaultRecord,
) -> None:
    signed = sign_record(record, crypto)
    connection.execute("BEGIN IMMEDIATE")
    load_records(connection, crypto)
    _insert(connection, "records", RECORD_COLUMNS, signed)
    connection.commit()


def reserve_write(
    connection: sqlite3.Connection,
    crypto: VaultCrypto,
    intent: VaultWriteIntent,
) -> VaultWriteIntent:
    signed = sign_intent(intent, crypto)
    connection.execute("BEGIN IMMEDIATE")
    intents = load_intents(connection, crypto)
    records = load_records(connection, crypto)
    existing = _intent_by_digest(intents, signed.dedup_hmac)
    if existing is not None:
        connection.commit()
        return existing
    if any(
        row.record_id == signed.record_id
        or row.encrypted_relpath == signed.encrypted_relpath
        for row in records
    ):
        raise VaultError("invalid_record_metadata")
    _insert(connection, "write_intents", INTENT_COLUMNS, signed)
    connection.commit()
    return signed


def activate_reserved(
    connection: sqlite3.Connection, crypto: VaultCrypto, record_id: str,
) -> VaultRecord:
    validate_record_id(record_id)
    connection.execute("BEGIN IMMEDIATE")
    intents = load_intents(connection, crypto)
    load_records(connection, crypto)
    intent = next((row for row in intents if row.record_id == record_id), None)
    if intent is None:
        raise VaultError("record_not_found")
    record = sign_record(_active_record(intent), crypto)
    _insert(connection, "records", RECORD_COLUMNS, record)
    connection.execute(
        "DELETE FROM write_intents WHERE record_id=?", (record_id,),
    )
    connection.commit()
    return record


def update_record_expiry(
    connection: sqlite3.Connection,
    crypto: VaultCrypto,
    record_id: str,
    expires_at_utc: int,
    *,
    extend: bool,
) -> None:
    _validate_expiry_input(record_id, expires_at_utc)
    connection.execute("BEGIN IMMEDIATE")
    records = load_records(connection, crypto)
    record = _active_by_id(records, record_id)
    changes = (
        expires_at_utc > record.expires_at_utc
        if extend else expires_at_utc < record.expires_at_utc
    )
    if changes:
        updated = sign_record(
            replace(record, expires_at_utc=expires_at_utc), crypto,
        )
        connection.execute(
            "UPDATE records SET expires_at_utc=?,metadata_mac=? "
            "WHERE record_id=? AND lifecycle_state='active'",
            (updated.expires_at_utc, updated.metadata_mac, record_id),
        )
    connection.commit()


def constrain_intent_expiry(
    connection: sqlite3.Connection,
    crypto: VaultCrypto,
    record_id: str,
    expires_at_utc: int,
) -> VaultWriteIntent:
    _validate_expiry_input(record_id, expires_at_utc)
    connection.execute("BEGIN IMMEDIATE")
    intents = load_intents(connection, crypto)
    intent = next((row for row in intents if row.record_id == record_id), None)
    if intent is None:
        raise VaultError("record_not_found")
    if expires_at_utc < intent.expires_at_utc:
        intent = sign_intent(
            replace(intent, expires_at_utc=expires_at_utc), crypto,
        )
        connection.execute(
            "UPDATE write_intents SET expires_at_utc=?,metadata_mac=? "
            "WHERE record_id=?",
            (intent.expires_at_utc, intent.metadata_mac, record_id),
        )
    connection.commit()
    return intent


def mark_delete_pending(
    connection: sqlite3.Connection, crypto: VaultCrypto, record_id: str,
) -> None:
    validate_record_id(record_id)
    connection.execute("BEGIN IMMEDIATE")
    record = _active_by_id(load_records(connection, crypto), record_id)
    updated = sign_record(replace(record, lifecycle_state="delete_pending"), crypto)
    connection.execute(
        "UPDATE records SET lifecycle_state=?,metadata_mac=? WHERE record_id=?",
        (updated.lifecycle_state, updated.metadata_mac, record_id),
    )
    connection.commit()


def _active_record(intent: VaultWriteIntent) -> VaultRecord:
    return VaultRecord(
        record_id=intent.record_id,
        encrypted_relpath=intent.encrypted_relpath,
        dedup_hmac=intent.dedup_hmac,
        created_at_utc=intent.created_at_utc,
        expires_at_utc=intent.expires_at_utc,
        ciphertext_size=intent.ciphertext_size,
        format_version=intent.format_version,
        key_version=intent.key_version,
        lifecycle_state="active",
    )


def _insert(
    connection: sqlite3.Connection,
    table: str,
    columns: tuple[str, ...],
    item: object,
) -> None:
    placeholders = ",".join("?" for _ in columns)
    values = tuple(getattr(item, column) for column in columns)
    connection.execute(f"INSERT INTO {table} VALUES ({placeholders})", values)


def _intent_by_digest(
    intents: list[VaultWriteIntent], digest: bytes,
) -> VaultWriteIntent | None:
    matches = [
        row for row in intents if hmac.compare_digest(row.dedup_hmac, digest)
    ]
    if len(matches) > 1:
        raise VaultError("index_schema_invalid")
    return None if not matches else matches[0]


def _active_by_id(records: list[VaultRecord], record_id: str) -> VaultRecord:
    record = next((row for row in records if row.record_id == record_id), None)
    if record is None or record.lifecycle_state != "active":
        raise VaultError("record_not_found")
    return record


def _validate_expiry_input(record_id: str, expires_at_utc: int) -> None:
    validate_record_id(record_id)
    if type(expires_at_utc) is not int or expires_at_utc < 0:
        raise VaultError("invalid_expiry")
