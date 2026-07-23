"""Canonical message, pair, quotation, and attachment row operations."""

from __future__ import annotations

import sqlite3

from ._sales_corpus_auth import authenticated_values, require_authenticated_row
from ._sales_corpus_common import SalesCorpusIndexError


def find_canonical(
    connection: sqlite3.Connection, identifier: bytes, content: bytes,
    auth_key: bytes | bytearray,
) -> str | None:
    identifiers = connection.execute(
        "SELECT identifier_hmac,canonical_id,auth_mac FROM message_identifiers "
        "WHERE identifier_hmac=?", (identifier,),
    ).fetchall()
    messages = connection.execute(
        "SELECT canonical_id,kind,trusted_timestamp,vault_record_id,content_hmac,"
        "supported_attachment_count,unsupported_attachment_count,auth_mac "
        "FROM canonical_messages WHERE content_hmac=?", (content,),
    ).fetchall()
    rows = {
        require_authenticated_row(auth_key, "message_identifiers", row)[1]
        for row in identifiers
    }
    rows.update(
        require_authenticated_row(auth_key, "canonical_messages", row)[0]
        for row in messages
    )
    if len(rows) > 1:
        raise SalesCorpusIndexError("sales_corpus_message_conflict")
    return None if not rows else next(iter(rows))


def require_same_message(
    connection: sqlite3.Connection, canonical: str, kind: str,
    timestamp: int, record_id: str, content: bytes,
    supported: int, unsupported: int,
    auth_key: bytes | bytearray,
) -> None:
    row = connection.execute(
        "SELECT canonical_id,kind,trusted_timestamp,vault_record_id,content_hmac,"
        "supported_attachment_count,unsupported_attachment_count,auth_mac "
        "FROM canonical_messages "
        "WHERE canonical_id=?", (canonical,),
    ).fetchone()
    if row is None:
        raise SalesCorpusIndexError("sales_corpus_message_conflict")
    values = require_authenticated_row(auth_key, "canonical_messages", row)
    if values[1:] != (
        kind, values[2], record_id, content, supported, unsupported,
    ):
        raise SalesCorpusIndexError("sales_corpus_message_conflict")
    if timestamp < values[2]:
        updated = authenticated_values(
            auth_key, "canonical_messages", canonical, kind, timestamp,
            record_id, content, supported, unsupported,
        )
        connection.execute(
            "UPDATE canonical_messages SET trusted_timestamp=?,auth_mac=? "
            "WHERE canonical_id=?", (timestamp, updated[-1], canonical),
        )


def bind_identifier(
    connection: sqlite3.Connection, canonical: str, token: bytes,
    auth_key: bytes | bytearray,
) -> None:
    row = connection.execute(
        "SELECT identifier_hmac,canonical_id,auth_mac FROM message_identifiers "
        "WHERE identifier_hmac=?", (token,),
    ).fetchone()
    if row is not None:
        values = require_authenticated_row(auth_key, "message_identifiers", row)
        if values[1] != canonical:
            raise SalesCorpusIndexError("sales_corpus_message_conflict")
    connection.execute(
        "INSERT OR IGNORE INTO message_identifiers VALUES(?,?,?)",
        authenticated_values(auth_key, "message_identifiers", token, canonical),
    )


def bind_source(
    connection: sqlite3.Connection, canonical: str, record_id: str, source: bytes,
    auth_key: bytes | bytearray,
) -> None:
    row = connection.execute(
        "SELECT source_hmac,canonical_id,vault_record_id,auth_mac "
        "FROM source_aliases WHERE source_hmac=?",
        (source,),
    ).fetchone()
    if row is not None:
        values = require_authenticated_row(auth_key, "source_aliases", row)
        if values[1:] != (canonical, record_id):
            raise SalesCorpusIndexError("sales_corpus_source_conflict")
    connection.execute(
        "INSERT OR IGNORE INTO source_aliases VALUES(?,?,?,?)",
        authenticated_values(
            auth_key, "source_aliases", source, canonical, record_id,
        ),
    )


def find_message_record(
    connection: sqlite3.Connection, identifier: bytes, content: bytes, source: bytes,
    auth_key: bytes | bytearray,
) -> tuple[str, bool] | None:
    canonical = find_canonical(connection, identifier, content, auth_key)
    alias = connection.execute(
        "SELECT source_hmac,canonical_id,vault_record_id,auth_mac "
        "FROM source_aliases WHERE source_hmac=?",
        (source,),
    ).fetchone()
    if canonical is None:
        if alias is not None:
            require_authenticated_row(auth_key, "source_aliases", alias)
            raise SalesCorpusIndexError("sales_corpus_source_conflict")
        return None
    record = connection.execute(
        "SELECT canonical_id,kind,trusted_timestamp,vault_record_id,content_hmac,"
        "supported_attachment_count,unsupported_attachment_count,auth_mac "
        "FROM canonical_messages WHERE canonical_id=?",
        (canonical,),
    ).fetchone()
    if record is None:
        raise SalesCorpusIndexError("sales_corpus_source_conflict")
    record_values = require_authenticated_row(
        auth_key, "canonical_messages", record,
    )
    if alias is not None:
        alias_values = require_authenticated_row(
            auth_key, "source_aliases", alias,
        )
        if alias_values[1:] != (canonical, record_values[3]):
            raise SalesCorpusIndexError("sales_corpus_source_conflict")
    return record_values[3], alias is not None


def bind_details(
    connection: sqlite3.Connection, canonical: str, kind: str,
    references: tuple[bytes, ...], quotations: tuple[bytes, ...], *, created: bool,
    auth_key: bytes | bytearray,
) -> None:
    if kind == "request" and references:
        raise SalesCorpusIndexError("sales_corpus_message_invalid")
    existing_refs = _tokens(
        connection, "reply_references", canonical, auth_key,
    )
    existing_quotes = _tokens(connection, "quotations", canonical, auth_key)
    if not created:
        if existing_refs != set(references) or existing_quotes != set(quotations):
            raise SalesCorpusIndexError("sales_corpus_message_conflict")
        return
    connection.executemany(
        "INSERT INTO reply_references VALUES(?,?,?)",
        (
            authenticated_values(
                auth_key, "reply_references", canonical, token,
            )
            for token in references
        ),
    )
    connection.executemany(
        "INSERT INTO quotations VALUES(?,?,?)",
        (
            authenticated_values(auth_key, "quotations", canonical, token)
            for token in quotations
        ),
    )


def _tokens(
    connection: sqlite3.Connection, table: str, canonical: str,
    auth_key: bytes | bytearray,
) -> set[bytes]:
    if table == "reply_references":
        query = (
            "SELECT reply_id,reference_hmac,auth_mac "
            "FROM reply_references WHERE reply_id=?"
        )
    elif table == "quotations":
        query = (
            "SELECT canonical_id,quotation_hmac,auth_mac "
            "FROM quotations WHERE canonical_id=?"
        )
    else:
        raise SalesCorpusIndexError()
    return {
        require_authenticated_row(auth_key, table, row)[1]
        for row in connection.execute(query, (canonical,))
    }


def reconcile_pairs(
    connection: sqlite3.Connection, canonical: str,
    auth_key: bytes | bytearray,
) -> None:
    connection.execute(
        "DELETE FROM pairs WHERE request_id=? OR reply_id=?",
        (canonical, canonical),
    )
    rows = connection.execute(
        "SELECT request.canonical_id,request.kind,request.trusted_timestamp,"
        "request.vault_record_id,request.content_hmac,"
        "request.supported_attachment_count,request.unsupported_attachment_count,"
        "request.auth_mac,"
        "reply.canonical_id,reply.kind,reply.trusted_timestamp,reply.vault_record_id,"
        "reply.content_hmac,reply.supported_attachment_count,"
        "reply.unsupported_attachment_count,reply.auth_mac,"
        "refs.reply_id,refs.reference_hmac,refs.auth_mac,quote.canonical_id,"
        "quote.quotation_hmac,quote.auth_mac,ids.identifier_hmac,"
        "ids.canonical_id,ids.auth_mac "
        "FROM reply_references refs JOIN canonical_messages reply ON reply.canonical_id=refs.reply_id "
        "JOIN quotations quote ON quote.canonical_id=reply.canonical_id "
        "JOIN message_identifiers ids ON ids.identifier_hmac=refs.reference_hmac "
        "JOIN canonical_messages request ON request.canonical_id=ids.canonical_id "
        "WHERE request.kind='request' AND reply.kind='reply' "
        "AND reply.trusted_timestamp>request.trusted_timestamp "
        "AND (request.canonical_id=? OR reply.canonical_id=?)",
        (canonical, canonical),
    ).fetchall()
    for row in rows:
        request = require_authenticated_row(
            auth_key, "canonical_messages", row[0:8],
        )
        reply = require_authenticated_row(
            auth_key, "canonical_messages", row[8:16],
        )
        require_authenticated_row(auth_key, "reply_references", row[16:19])
        quotation = require_authenticated_row(
            auth_key, "quotations", row[19:22],
        )
        require_authenticated_row(
            auth_key, "message_identifiers", row[22:25],
        )
        connection.execute(
            "INSERT OR IGNORE INTO pairs VALUES(?,?,?,?)",
            authenticated_values(
                auth_key, "pairs", request[0], reply[0], quotation[1],
            ),
        )


def is_paired(
    connection: sqlite3.Connection, canonical: str,
    auth_key: bytes | bytearray,
) -> bool:
    rows = connection.execute(
        "SELECT request_id,reply_id,quotation_hmac,auth_mac FROM pairs "
        "WHERE request_id=? OR reply_id=?",
        (canonical, canonical),
    ).fetchall()
    for row in rows:
        require_authenticated_row(auth_key, "pairs", row)
    return bool(rows)


__all__ = [
    "bind_details",
    "bind_identifier",
    "bind_source",
    "find_canonical",
    "find_message_record",
    "is_paired",
    "reconcile_pairs",
    "require_same_message",
]
