"""Strict SQLite storage for metadata-only sales corpus tokens."""

from __future__ import annotations

import secrets
import sqlite3
from pathlib import Path

from ._sales_corpus_auth import (
    AUTH_COLUMNS,
    authenticated_values,
    require_authenticated_row,
    verify_all_rows,
)
from ._sales_corpus_attachments import (
    bind_attachment,
    find_attachment_blob,
    select_blob,
    source_canonical,
)
from ._sales_corpus_common import SalesCorpusIndexError
from ._sales_corpus_database import (
    connection as _connection,
    count as _count,
    require_schema as _require_schema,
    schema_rows as _schema_rows,
)
from ._sales_corpus_lifecycle import (
    purge_records,
    vault_record_ids,
)
from ._sales_corpus_records import (
    bind_details,
    bind_identifier,
    bind_source,
    find_canonical,
    find_message_record,
    is_paired,
    reconcile_pairs,
    require_same_message,
)


_SCHEMA = (
    "CREATE TABLE corpus_metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL CHECK(schema_version=1), key_check_hmac BLOB NOT NULL CHECK(length(key_check_hmac)=32), policy_hmac BLOB CHECK(policy_hmac IS NULL OR length(policy_hmac)=32), auth_mac BLOB NOT NULL CHECK(length(auth_mac)=32))",
    "CREATE TABLE canonical_messages (canonical_id TEXT PRIMARY KEY CHECK(length(canonical_id)=32), kind TEXT NOT NULL CHECK(kind IN ('request','reply')), trusted_timestamp INTEGER NOT NULL CHECK(trusted_timestamp>=0), vault_record_id TEXT NOT NULL UNIQUE CHECK(length(vault_record_id)=32), content_hmac BLOB NOT NULL UNIQUE CHECK(length(content_hmac)=32), supported_attachment_count INTEGER NOT NULL CHECK(supported_attachment_count>=0), unsupported_attachment_count INTEGER NOT NULL CHECK(unsupported_attachment_count>=0), auth_mac BLOB NOT NULL CHECK(length(auth_mac)=32), UNIQUE(canonical_id,vault_record_id))",
    "CREATE TABLE message_identifiers (identifier_hmac BLOB PRIMARY KEY CHECK(length(identifier_hmac)=32), canonical_id TEXT NOT NULL REFERENCES canonical_messages(canonical_id), auth_mac BLOB NOT NULL CHECK(length(auth_mac)=32))",
    "CREATE TABLE source_aliases (source_hmac BLOB PRIMARY KEY CHECK(length(source_hmac)=32), canonical_id TEXT NOT NULL, vault_record_id TEXT NOT NULL, auth_mac BLOB NOT NULL CHECK(length(auth_mac)=32), FOREIGN KEY(canonical_id,vault_record_id) REFERENCES canonical_messages(canonical_id,vault_record_id))",
    "CREATE TABLE reply_references (reply_id TEXT NOT NULL REFERENCES canonical_messages(canonical_id), reference_hmac BLOB NOT NULL CHECK(length(reference_hmac)=32), auth_mac BLOB NOT NULL CHECK(length(auth_mac)=32), PRIMARY KEY(reply_id,reference_hmac))",
    "CREATE TABLE quotations (canonical_id TEXT NOT NULL REFERENCES canonical_messages(canonical_id), quotation_hmac BLOB NOT NULL CHECK(length(quotation_hmac)=32), auth_mac BLOB NOT NULL CHECK(length(auth_mac)=32), PRIMARY KEY(canonical_id,quotation_hmac))",
    "CREATE TABLE pairs (request_id TEXT NOT NULL REFERENCES canonical_messages(canonical_id), reply_id TEXT NOT NULL REFERENCES canonical_messages(canonical_id), quotation_hmac BLOB NOT NULL UNIQUE CHECK(length(quotation_hmac)=32), auth_mac BLOB NOT NULL CHECK(length(auth_mac)=32), PRIMARY KEY(request_id,reply_id), CHECK(request_id<>reply_id))",
    "CREATE TABLE attachment_blobs (blob_record_id TEXT PRIMARY KEY CHECK(length(blob_record_id)=32), content_hmac BLOB NOT NULL UNIQUE CHECK(length(content_hmac)=32), parse_status TEXT NOT NULL CHECK(parse_status IN ('parsed','failed','unparsed')), semantic_status TEXT NOT NULL CHECK(semantic_status IN ('unreviewed','approved','rejected')), auth_mac BLOB NOT NULL CHECK(length(auth_mac)=32))",
    "CREATE TABLE attachment_bindings (source_record_id TEXT NOT NULL REFERENCES canonical_messages(vault_record_id), candidate_hmac BLOB NOT NULL CHECK(length(candidate_hmac)=32), blob_record_id TEXT NOT NULL REFERENCES attachment_blobs(blob_record_id), auth_mac BLOB NOT NULL CHECK(length(auth_mac)=32), PRIMARY KEY(source_record_id,candidate_hmac))",
    "CREATE INDEX source_aliases_canonical_idx ON source_aliases(canonical_id)",
    "CREATE INDEX message_identifiers_canonical_idx ON message_identifiers(canonical_id)",
    "CREATE INDEX reply_references_token_idx ON reply_references(reference_hmac)",
    "CREATE INDEX quotations_token_idx ON quotations(quotation_hmac)",
    "CREATE INDEX pairs_reply_idx ON pairs(reply_id)",
    "CREATE INDEX attachment_bindings_blob_idx ON attachment_bindings(blob_record_id)",
)


class SalesCorpusStore:
    def __init__(
        self, path: Path, key_check: bytes, auth_key: bytes | bytearray,
    ) -> None:
        self.path = Path(path)
        self.key_check = key_check
        self.auth_key = auth_key

    def initialize(self) -> None:
        with _connection(self.path, create=True) as connection:
            existing = _schema_rows(connection)
            if existing:
                _require_schema(connection, _SCHEMA)
            else:
                for statement in _SCHEMA:
                    connection.execute(statement)
                connection.execute("PRAGMA user_version=1")
                _require_schema(connection, _SCHEMA)
            row = connection.execute(
                "SELECT 1 FROM corpus_metadata WHERE singleton=1"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO corpus_metadata VALUES(?,?,?,?,?)",
                    authenticated_values(
                        self.auth_key, "corpus_metadata",
                        1, 1, self.key_check, None,
                    ),
                )
            else:
                self._metadata(connection)

    def validate(self, require_policy: bool) -> None:
        try:
            connection = sqlite3.connect(
                f"{self.path.resolve().as_uri()}?mode=ro", uri=True,
            )
        except (OSError, sqlite3.Error, ValueError):
            raise SalesCorpusIndexError("sales_corpus_schema_invalid") from None
        try:
            policy = self._metadata(connection)[1]
            if require_policy and policy is None:
                raise SalesCorpusIndexError("sales_corpus_policy_unbound")
            verify_all_rows(connection, self.auth_key)
        finally:
            connection.close()

    def bind_policy(self, policy: bytes) -> None:
        with _connection(self.path) as connection:
            row = self._metadata(connection)
            verify_all_rows(connection, self.auth_key)
            if row[1] is None:
                if self._has_content(connection):
                    raise SalesCorpusIndexError("sales_corpus_policy_unbound")
                values = authenticated_values(
                    self.auth_key, "corpus_metadata",
                    1, 1, self.key_check, policy,
                )
                connection.execute(
                    "UPDATE corpus_metadata SET policy_hmac=?,auth_mac=? "
                    "WHERE singleton=1",
                    (values[-2], values[-1]),
                )
            elif row[1] != policy:
                raise SalesCorpusIndexError("sales_corpus_policy_mismatch")

    def summary(self) -> tuple[int, ...]:
        with _connection(self.path) as connection:
            self._metadata(connection)
            verify_all_rows(connection, self.auth_key)
            messages = connection.execute(
                "SELECT COUNT(*),SUM(kind='request'),SUM(kind='reply'),"
                "COALESCE(SUM(supported_attachment_count),0),"
                "COALESCE(SUM(unsupported_attachment_count),0) "
                "FROM canonical_messages"
            ).fetchone()
            sources = _count(connection, "source_aliases")
            pairs = _count(connection, "pairs")
            paired = connection.execute(
                "SELECT COUNT(*) FROM (SELECT request_id id FROM pairs UNION SELECT reply_id id FROM pairs)"
            ).fetchone()[0]
            quotes = connection.execute(
                "SELECT COUNT(DISTINCT quotation_hmac) FROM quotations"
            ).fetchone()[0]
            potential = connection.execute(
                "SELECT COUNT(*) FROM reply_references refs "
                "JOIN canonical_messages reply ON reply.canonical_id=refs.reply_id "
                "JOIN quotations quote ON quote.canonical_id=reply.canonical_id "
                "JOIN message_identifiers ids ON ids.identifier_hmac=refs.reference_hmac "
                "JOIN canonical_messages request ON request.canonical_id=ids.canonical_id "
                "WHERE request.kind='request' AND reply.kind='reply' "
                "AND reply.trusted_timestamp>request.trusted_timestamp"
            ).fetchone()[0]
        total, requests, replies, supported, unsupported = messages
        return (
            total, requests or 0, replies or 0, sources, sources-total,
            pairs, paired, quotes, potential-pairs, supported, unsupported,
        )

    def upsert_message(
        self, kind: str, identifier: bytes, references: tuple[bytes, ...],
        timestamp: int, record_id: str, source: bytes, content: bytes,
        quotations: tuple[bytes, ...], supported: int, unsupported: int,
    ) -> tuple[str, bool]:
        with _connection(self.path) as connection:
            self._require_policy(connection)
            canonical = find_canonical(
                connection, identifier, content, self.auth_key,
            )
            status = "duplicate"
            if canonical is None:
                canonical, status = secrets.token_hex(16), "created"
                connection.execute(
                    "INSERT INTO canonical_messages VALUES(?,?,?,?,?,?,?,?)",
                    authenticated_values(
                        self.auth_key, "canonical_messages", canonical, kind,
                        timestamp, record_id, content, supported, unsupported,
                    ),
                )
            else:
                require_same_message(
                    connection, canonical, kind, timestamp, record_id, content,
                    supported, unsupported, self.auth_key,
                )
            bind_identifier(connection, canonical, identifier, self.auth_key)
            bind_source(
                connection, canonical, record_id, source, self.auth_key,
            )
            bind_details(
                connection, canonical, kind, references, quotations,
                created=status == "created", auth_key=self.auth_key,
            )
            reconcile_pairs(connection, canonical, self.auth_key)
            return status, is_paired(connection, canonical, self.auth_key)

    def find_message_record(
        self, identifier: bytes, content: bytes, source: bytes,
    ) -> tuple[str, bool] | None:
        with _connection(self.path) as connection:
            self._require_policy(connection)
            return find_message_record(
                connection, identifier, content, source, self.auth_key,
            )

    def belongs_to_pair(self, record_id: str) -> bool:
        with _connection(self.path) as connection:
            self._require_policy(connection)
            canonical = source_canonical(connection, record_id, self.auth_key)
            return canonical is not None and is_paired(
                connection, canonical, self.auth_key,
            )

    def bind_attachment(
        self, source: str, candidate: bytes, proposed_blob: str, content: bytes,
        parse_status: str, semantic_status: str,
    ) -> tuple[str, str]:
        with _connection(self.path) as connection:
            self._require_policy(connection)
            canonical = source_canonical(connection, source, self.auth_key)
            if canonical is None or not is_paired(
                connection, canonical, self.auth_key,
            ):
                raise SalesCorpusIndexError("attachment_source_not_paired")
            blob, status = select_blob(
                connection, proposed_blob, content, parse_status, semantic_status,
                self.auth_key,
            )
            bind_attachment(
                connection, source, candidate, blob, self.auth_key,
            )
            return status, blob

    def find_attachment_blob(self, content: bytes) -> str | None:
        with _connection(self.path) as connection:
            self._require_policy(connection)
            return find_attachment_blob(connection, content, self.auth_key)

    def attachment_summary(self) -> tuple[int, ...]:
        with _connection(self.path) as connection:
            self._require_policy(connection)
            verify_all_rows(connection, self.auth_key)
            blobs = _count(connection, "attachment_blobs")
            bindings = _count(connection, "attachment_bindings")
            parsed = connection.execute(
                "SELECT COUNT(*) FROM attachment_blobs WHERE parse_status='parsed'"
            ).fetchone()[0]
            unreviewed = connection.execute(
                "SELECT COUNT(*) FROM attachment_blobs WHERE semantic_status='unreviewed'"
            ).fetchone()[0]
            return blobs, bindings-blobs, blobs, bindings, parsed, unreviewed

    def vault_record_ids(self) -> tuple[str, ...]:
        with _connection(self.path) as connection:
            policy = self._metadata(connection)[1]
            record_ids = vault_record_ids(connection, self.auth_key)
            if record_ids and policy is None:
                raise SalesCorpusIndexError("sales_corpus_policy_unbound")
            return record_ids

    def purge_records(self, record_ids: tuple[str, ...]) -> None:
        with _connection(self.path) as connection:
            policy = self._metadata(connection)[1]
            existing_ids = vault_record_ids(connection, self.auth_key)
            if existing_ids and policy is None:
                raise SalesCorpusIndexError("sales_corpus_policy_unbound")
            purge_records(connection, record_ids, self.auth_key)

    def _metadata(self, connection: sqlite3.Connection) -> tuple[bytes, bytes | None]:
        _require_schema(connection, _SCHEMA)
        row = connection.execute(
            "SELECT singleton,schema_version,key_check_hmac,policy_hmac,auth_mac "
            "FROM corpus_metadata WHERE singleton=1"
        ).fetchone()
        if row is None or len(row) != 5 or row[2] != self.key_check:
            raise SalesCorpusIndexError("sales_corpus_key_mismatch")
        values = require_authenticated_row(
            self.auth_key, "corpus_metadata", row,
        )
        if values[:3] != (1, 1, self.key_check):
            raise SalesCorpusIndexError("sales_corpus_key_mismatch")
        return values[2], values[3]

    @staticmethod
    def _has_content(connection: sqlite3.Connection) -> bool:
        return any(
            connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
            is not None
            for table in AUTH_COLUMNS
            if table != "corpus_metadata"
        )

    def _require_policy(self, connection: sqlite3.Connection) -> None:
        if self._metadata(connection)[1] is None:
            raise SalesCorpusIndexError("sales_corpus_policy_unbound")

__all__ = ["SalesCorpusStore"]
