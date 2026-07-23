"""Validation and row decoding for vault index metadata."""

from __future__ import annotations

import re
import sqlite3

from ._vault_index_schema import INTENT_COLUMNS, MAX_BATCH_LIMIT, RECORD_COLUMNS
from .errors import VaultError
from .models import VaultRecord, VaultWriteIntent


_RECORD_ID = re.compile(r"^[0-9a-f]{32}$")
_RECORD_PATH = re.compile(r"^records/[0-9a-f]{2}/[0-9a-f]{32}\.mvlt$")
_RECORD_STATES = {"active", "delete_pending"}


def validate_record(record: VaultRecord, *, require_mac: bool = True) -> None:
    if not isinstance(record, VaultRecord):
        raise VaultError("invalid_record_metadata")
    validate_record_id(record.record_id)
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
    _validate_metadata_mac(record.metadata_mac, require_mac=require_mac)


def validate_intent(
    intent: VaultWriteIntent, *, require_mac: bool = True,
) -> None:
    if not isinstance(intent, VaultWriteIntent):
        raise VaultError("invalid_record_metadata")
    validate_record(VaultRecord(
        intent.record_id, intent.encrypted_relpath, intent.dedup_hmac,
        intent.created_at_utc, intent.expires_at_utc,
        intent.ciphertext_size, intent.format_version,
        intent.key_version, "active", intent.metadata_mac,
    ), require_mac=require_mac)


def _validate_metadata_mac(value: bytes, *, require_mac: bool) -> None:
    expected_lengths = {32} if require_mac else {0, 32}
    if type(value) is not bytes or len(value) not in expected_lengths:
        raise VaultError("invalid_record_metadata")


def validate_digest(digest: bytes) -> None:
    if type(digest) is not bytes or len(digest) != 32:
        raise VaultError("invalid_record_metadata")


def validate_record_id(record_id: str) -> None:
    if not isinstance(record_id, str) or _RECORD_ID.fullmatch(record_id) is None:
        raise VaultError("invalid_record_id")


def validate_limit(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH_LIMIT:
        raise VaultError("invalid_limit")


def row_to_record(row: sqlite3.Row) -> VaultRecord:
    try:
        record = VaultRecord(
            **{column: row[column] for column in RECORD_COLUMNS}
        )
    except (IndexError, KeyError, TypeError):
        raise VaultError("invalid_record_metadata") from None
    validate_record(record)
    return record


def row_to_intent(row: sqlite3.Row) -> VaultWriteIntent:
    try:
        intent = VaultWriteIntent(
            **{column: row[column] for column in INTENT_COLUMNS}
        )
    except (IndexError, KeyError, TypeError):
        raise VaultError("invalid_record_metadata") from None
    validate_intent(intent)
    return intent
