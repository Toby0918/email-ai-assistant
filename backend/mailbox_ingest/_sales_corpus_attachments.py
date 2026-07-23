"""Authenticated attachment and source lookups for the sales corpus index."""

from __future__ import annotations

import sqlite3

from ._sales_corpus_auth import authenticated_values, require_authenticated_row
from ._sales_corpus_common import SalesCorpusIndexError


def source_canonical(
    connection: sqlite3.Connection, source: str, auth_key: bytes | bytearray,
) -> str | None:
    row = connection.execute(
        "SELECT canonical_id,kind,trusted_timestamp,vault_record_id,content_hmac,"
        "supported_attachment_count,unsupported_attachment_count,auth_mac "
        "FROM canonical_messages WHERE vault_record_id=?", (source,),
    ).fetchone()
    if row is None:
        return None
    return require_authenticated_row(auth_key, "canonical_messages", row)[0]


def find_attachment_blob(
    connection: sqlite3.Connection, content: bytes,
    auth_key: bytes | bytearray,
) -> str | None:
    row = connection.execute(
        "SELECT blob_record_id,content_hmac,parse_status,semantic_status,auth_mac "
        "FROM attachment_blobs WHERE content_hmac=?", (content,),
    ).fetchone()
    if row is None:
        return None
    return require_authenticated_row(auth_key, "attachment_blobs", row)[0]


def select_blob(
    connection: sqlite3.Connection, proposed: str, content: bytes,
    parse_status: str, semantic_status: str, auth_key: bytes | bytearray,
) -> tuple[str, str]:
    row = connection.execute(
        "SELECT blob_record_id,content_hmac,parse_status,semantic_status,auth_mac "
        "FROM attachment_blobs WHERE content_hmac=?", (content,),
    ).fetchone()
    if row is not None:
        values = require_authenticated_row(auth_key, "attachment_blobs", row)
        if values[2:] != (parse_status, semantic_status):
            raise SalesCorpusIndexError("attachment_blob_conflict")
        return values[0], "duplicate"
    conflict = connection.execute(
        "SELECT blob_record_id,content_hmac,parse_status,semantic_status,auth_mac "
        "FROM attachment_blobs WHERE blob_record_id=?", (proposed,),
    ).fetchone()
    if conflict is not None:
        require_authenticated_row(auth_key, "attachment_blobs", conflict)
        raise SalesCorpusIndexError("attachment_blob_conflict")
    connection.execute(
        "INSERT INTO attachment_blobs VALUES(?,?,?,?,?)",
        authenticated_values(
            auth_key, "attachment_blobs", proposed, content,
            parse_status, semantic_status,
        ),
    )
    return proposed, "new"


def bind_attachment(
    connection: sqlite3.Connection, source: str, candidate: bytes, blob: str,
    auth_key: bytes | bytearray,
) -> None:
    row = connection.execute(
        "SELECT source_record_id,candidate_hmac,blob_record_id,auth_mac "
        "FROM attachment_bindings "
        "WHERE source_record_id=? AND candidate_hmac=?", (source, candidate),
    ).fetchone()
    if row is not None:
        values = require_authenticated_row(auth_key, "attachment_bindings", row)
        if values[2] != blob:
            raise SalesCorpusIndexError("attachment_binding_conflict")
        return
    connection.execute(
        "INSERT INTO attachment_bindings VALUES(?,?,?,?)",
        authenticated_values(
            auth_key, "attachment_bindings", source, candidate, blob,
        ),
    )


__all__ = [
    "bind_attachment", "find_attachment_blob", "select_blob", "source_canonical",
]
