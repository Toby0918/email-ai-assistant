"""Authenticated lifecycle queries for the governed sales corpus index."""

from __future__ import annotations

import sqlite3

from ._sales_corpus_auth import verify_all_rows


def vault_record_ids(
    connection: sqlite3.Connection, auth_key: bytes | bytearray,
) -> tuple[str, ...]:
    verify_all_rows(connection, auth_key)
    rows = connection.execute(
        "SELECT vault_record_id FROM canonical_messages "
        "UNION SELECT vault_record_id FROM source_aliases "
        "UNION SELECT blob_record_id FROM attachment_blobs "
        "ORDER BY 1"
    )
    return tuple(row[0] for row in rows)


def purge_records(
    connection: sqlite3.Connection,
    record_ids: tuple[str, ...],
    auth_key: bytes | bytearray,
) -> None:
    verify_all_rows(connection, auth_key)
    if not record_ids:
        return
    placeholders = ",".join("?" for _ in record_ids)
    canonical_ids = tuple(row[0] for row in connection.execute(
        "SELECT canonical_id FROM canonical_messages "
        f"WHERE vault_record_id IN ({placeholders})",
        record_ids,
    ))
    connection.execute(
        "DELETE FROM attachment_bindings "
        f"WHERE source_record_id IN ({placeholders}) "
        f"OR blob_record_id IN ({placeholders})",
        (*record_ids, *record_ids),
    )
    connection.execute(
        f"DELETE FROM attachment_blobs WHERE blob_record_id IN ({placeholders}) "
        "OR NOT EXISTS (SELECT 1 FROM attachment_bindings bindings "
        "WHERE bindings.blob_record_id=attachment_blobs.blob_record_id)",
        record_ids,
    )
    _purge_messages(connection, canonical_ids, record_ids, placeholders)


def _purge_messages(
    connection: sqlite3.Connection,
    canonical_ids: tuple[str, ...],
    record_ids: tuple[str, ...],
    record_placeholders: str,
) -> None:
    if not canonical_ids:
        connection.execute(
            "DELETE FROM source_aliases "
            f"WHERE vault_record_id IN ({record_placeholders})",
            record_ids,
        )
        return
    canonical_placeholders = ",".join("?" for _ in canonical_ids)
    connection.execute(
        f"DELETE FROM pairs WHERE request_id IN ({canonical_placeholders}) "
        f"OR reply_id IN ({canonical_placeholders})",
        (*canonical_ids, *canonical_ids),
    )
    for table, column in (
        ("reply_references", "reply_id"),
        ("quotations", "canonical_id"),
        ("message_identifiers", "canonical_id"),
    ):
        connection.execute(
            f"DELETE FROM {table} WHERE {column} IN ({canonical_placeholders})",
            canonical_ids,
        )
    connection.execute(
        f"DELETE FROM source_aliases WHERE canonical_id IN ({canonical_placeholders}) "
        f"OR vault_record_id IN ({record_placeholders})",
        (*canonical_ids, *record_ids),
    )
    connection.execute(
        f"DELETE FROM canonical_messages WHERE canonical_id IN ({canonical_placeholders})",
        canonical_ids,
    )


__all__ = ["purge_records", "vault_record_ids"]
