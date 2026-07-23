"""Signing and verification adapters for vault-index metadata rows."""

from __future__ import annotations

import sqlite3

from ._vault_index_records import (
    row_to_intent,
    row_to_record,
    validate_intent,
    validate_record,
)
from .models import VaultRecord, VaultWriteIntent
from .vault_crypto import VaultCrypto


def decode_record(row: sqlite3.Row, crypto: VaultCrypto) -> VaultRecord:
    record = row_to_record(row)
    crypto.verify_record_metadata(record)
    return record


def decode_intent(row: sqlite3.Row, crypto: VaultCrypto) -> VaultWriteIntent:
    intent = row_to_intent(row)
    crypto.verify_intent_metadata(intent)
    return intent


def sign_record(record: VaultRecord, crypto: VaultCrypto) -> VaultRecord:
    validate_record(record, require_mac=False)
    signed = crypto.sign_record_metadata(record)
    validate_record(signed)
    return signed


def sign_intent(
    intent: VaultWriteIntent, crypto: VaultCrypto,
) -> VaultWriteIntent:
    validate_intent(intent, require_mac=False)
    signed = crypto.sign_intent_metadata(intent)
    validate_intent(signed)
    return signed


def load_records(
    connection: sqlite3.Connection, crypto: VaultCrypto,
) -> list[VaultRecord]:
    rows = connection.execute("SELECT * FROM records ORDER BY record_id")
    return [decode_record(row, crypto) for row in rows]


def load_intents(
    connection: sqlite3.Connection, crypto: VaultCrypto,
) -> list[VaultWriteIntent]:
    rows = connection.execute("SELECT * FROM write_intents ORDER BY record_id")
    return [decode_intent(row, crypto) for row in rows]
