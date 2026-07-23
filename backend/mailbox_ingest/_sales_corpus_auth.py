"""Domain-separated row authentication for the private corpus SQLite index."""

from __future__ import annotations

import hashlib
import hmac
import sqlite3

from ._sales_corpus_common import SalesCorpusIndexError


AUTH_KEY_PURPOSE = b"sales-corpus-index/row-auth-key/v1\0"
AUTH_COLUMNS = {
    "corpus_metadata": (
        "singleton", "schema_version", "key_check_hmac", "policy_hmac",
    ),
    "canonical_messages": (
        "canonical_id", "kind", "trusted_timestamp", "vault_record_id",
        "content_hmac", "supported_attachment_count",
        "unsupported_attachment_count",
    ),
    "message_identifiers": ("identifier_hmac", "canonical_id"),
    "source_aliases": ("source_hmac", "canonical_id", "vault_record_id"),
    "reply_references": ("reply_id", "reference_hmac"),
    "quotations": ("canonical_id", "quotation_hmac"),
    "pairs": ("request_id", "reply_id", "quotation_hmac"),
    "attachment_blobs": (
        "blob_record_id", "content_hmac", "parse_status", "semantic_status",
    ),
    "attachment_bindings": (
        "source_record_id", "candidate_hmac", "blob_record_id",
    ),
}


def derive_auth_key(key: bytes | bytearray) -> bytearray:
    return bytearray(hmac.new(key, AUTH_KEY_PURPOSE, hashlib.sha256).digest())


def authenticate_row(
    key: bytes | bytearray, table: str, *values: object,
) -> bytes:
    if table not in AUTH_COLUMNS or len(values) != len(AUTH_COLUMNS[table]):
        raise SalesCorpusIndexError("sales_corpus_auth_invalid")
    framed = b"".join(_field(value) for value in values)
    return hmac.new(
        key,
        b"sales-corpus-index/row/v1\0" + table.encode("ascii") + b"\0" + framed,
        hashlib.sha256,
    ).digest()


def require_authenticated_row(
    key: bytes | bytearray, table: str, row: object,
) -> tuple[object, ...]:
    if not isinstance(row, tuple) or len(row) != len(AUTH_COLUMNS[table]) + 1:
        raise SalesCorpusIndexError("sales_corpus_auth_invalid")
    values, supplied = row[:-1], row[-1]
    expected = authenticate_row(key, table, *values)
    if type(supplied) is not bytes or not hmac.compare_digest(supplied, expected):
        raise SalesCorpusIndexError("sales_corpus_auth_invalid")
    return values


def verify_all_rows(
    connection: sqlite3.Connection, key: bytes | bytearray,
) -> None:
    for table, columns in AUTH_COLUMNS.items():
        selected = ",".join((*columns, "auth_mac"))
        for row in connection.execute(f"SELECT {selected} FROM {table}"):
            require_authenticated_row(key, table, row)


def authenticated_values(
    key: bytes | bytearray, table: str, *values: object,
) -> tuple[object, ...]:
    return (*values, authenticate_row(key, table, *values))


def _field(value: object) -> bytes:
    if value is None:
        tag, payload = b"n", b""
    elif type(value) is bytes:
        tag, payload = b"b", value
    elif type(value) is str:
        tag, payload = b"s", value.encode("utf-8", errors="strict")
    elif type(value) is int:
        tag, payload = b"i", str(value).encode("ascii")
    else:
        raise SalesCorpusIndexError("sales_corpus_auth_invalid")
    return tag + len(payload).to_bytes(8, "big") + payload


__all__ = [
    "AUTH_COLUMNS",
    "authenticated_values",
    "derive_auth_key",
    "require_authenticated_row",
    "verify_all_rows",
]
