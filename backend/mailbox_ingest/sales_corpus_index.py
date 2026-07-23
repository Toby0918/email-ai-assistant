"""Public metadata-only index for the governed sales corpus."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

from ._sales_corpus_common import (
    ATTACHMENT_CANDIDATE_PURPOSE,
    ATTACHMENT_CONTENT_PURPOSE,
    AttachmentBindResult,
    AttachmentSummary,
    CONTENT_PURPOSE,
    CorpusSummary,
    KEY_CHECK_PURPOSE,
    MESSAGE_PURPOSE,
    MessageLookupResult,
    MessageUpsertResult,
    POLICY_PURPOSE,
    QUOTATION_PURPOSE,
    SOURCE_PURPOSE,
    SalesCorpusIndexError,
    is_hex,
    keyed_token,
    keyed_tokens,
)
from ._sales_corpus_auth import derive_auth_key
from ._sales_corpus_store import SalesCorpusStore


class SalesCorpusIndex:
    """Closed facade that hashes all caller tokens before SQLite persistence."""

    def __init__(self, path: Path, *, key: bytes) -> None:
        if type(key) is not bytes or len(key) < 32:
            raise SalesCorpusIndexError("sales_corpus_key_invalid")
        try:
            selected_path = Path(path)
        except (TypeError, ValueError, OSError):
            raise SalesCorpusIndexError("sales_corpus_path_invalid") from None
        self._key = bytearray(key)
        self._auth_key = derive_auth_key(self._key)
        key_check = keyed_token(
            self._key, KEY_CHECK_PURPOSE, "governed-sales-corpus",
            code="sales_corpus_key_invalid",
        )
        self._store = SalesCorpusStore(selected_path, key_check, self._auth_key)
        self._closed = False

    def __repr__(self) -> str:
        return "SalesCorpusIndex(<metadata-only>)"

    def __enter__(self) -> SalesCorpusIndex:
        self._require_open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        for index in range(len(self._key)):
            self._key[index] = 0
        for index in range(len(self._auth_key)):
            self._auth_key[index] = 0
        self._closed = True

    def initialize(self) -> None:
        self._run(self._store.initialize)

    def validate(self, *, require_policy: bool = False) -> None:
        if type(require_policy) is not bool:
            raise SalesCorpusIndexError("sales_corpus_policy_invalid")
        self._run(self._store.validate, require_policy)

    def bind_policy(self, policy_fingerprint: str) -> None:
        self._require_open()
        if not is_hex(policy_fingerprint, 64):
            raise SalesCorpusIndexError("sales_corpus_policy_invalid")
        policy = keyed_token(
            self._key, POLICY_PURPOSE, policy_fingerprint,
            code="sales_corpus_policy_invalid",
        )
        self._run(self._store.bind_policy, policy)

    def summary(self) -> CorpusSummary:
        return CorpusSummary(*self._run(self._store.summary))

    def find_message_record(
        self, *, message_id_token: str, content_token: str, source_token: str,
    ) -> MessageLookupResult | None:
        self._require_open()
        identifier = keyed_token(
            self._key, MESSAGE_PURPOSE, message_id_token,
            code="sales_corpus_message_invalid",
        )
        content = keyed_token(
            self._key, CONTENT_PURPOSE, content_token,
            code="sales_corpus_message_invalid",
        )
        source = self._source_value(source_token)
        found = self._run(
            self._store.find_message_record, identifier, content, source,
        )
        return None if found is None else MessageLookupResult(*found)

    def upsert_message(
        self,
        *,
        kind: str,
        message_id_token: str,
        reference_tokens: tuple[str, ...],
        trusted_timestamp: int,
        vault_record_id: str,
        source_token: str,
        content_token: str,
        quotation_tokens: tuple[str, ...],
        supported_attachment_count: int = 0,
        unsupported_attachment_count: int = 0,
    ) -> MessageUpsertResult:
        values = self._message_values(
            kind, message_id_token, reference_tokens, trusted_timestamp,
            vault_record_id, source_token, content_token, quotation_tokens,
            supported_attachment_count, unsupported_attachment_count,
        )
        status, paired = self._run(
            self._store.upsert_message,
            kind, values[0], values[1], trusted_timestamp,
            vault_record_id, values[2], values[3], values[4],
            supported_attachment_count, unsupported_attachment_count,
        )
        return MessageUpsertResult(status, paired)

    def belongs_to_pair(self, source_record_id: str) -> bool:
        self._require_open()
        if not is_hex(source_record_id, 32):
            raise SalesCorpusIndexError("sales_corpus_source_invalid")
        return self._run(self._store.belongs_to_pair, source_record_id)

    def bind_attachment(
        self,
        *,
        source_record_id: str,
        candidate_token: str,
        blob_record_id: str,
        content_token: str,
        parse_status: str = "parsed",
        semantic_status: str = "unreviewed",
    ) -> AttachmentBindResult:
        candidate, content = self._attachment_values(
            source_record_id, candidate_token, blob_record_id, content_token,
            parse_status, semantic_status,
        )
        status, selected = self._run(
            self._store.bind_attachment, source_record_id, candidate,
            blob_record_id, content, parse_status, semantic_status,
        )
        return AttachmentBindResult(status, selected)

    def find_attachment_blob(self, content_token: str) -> str | None:
        self._require_open()
        content = keyed_token(
            self._key, ATTACHMENT_CONTENT_PURPOSE, content_token,
            code="attachment_binding_invalid",
        )
        return self._run(self._store.find_attachment_blob, content)

    def attachment_summary(self) -> AttachmentSummary:
        return AttachmentSummary(*self._run(self._store.attachment_summary))

    def vault_record_ids(self) -> tuple[str, ...]:
        return self._run(self._store.vault_record_ids)

    def purge_records(self, record_ids: tuple[str, ...]) -> None:
        self._require_open()
        if (
            not isinstance(record_ids, tuple)
            or len(record_ids) > 1_000
            or any(not is_hex(record_id, 32) for record_id in record_ids)
            or len(set(record_ids)) != len(record_ids)
        ):
            raise SalesCorpusIndexError("sales_corpus_record_ids_invalid")
        self._run(self._store.purge_records, record_ids)

    def _message_values(
        self, kind: str, message_id: str, references: tuple[str, ...],
        timestamp: int, record_id: str, source: str, content: str,
        quotations: tuple[str, ...],
        supported: int, unsupported: int,
    ) -> tuple[bytes, tuple[bytes, ...], bytes, bytes, tuple[bytes, ...]]:
        self._require_open()
        if (
            kind not in {"request", "reply"}
            or not is_hex(record_id, 32)
            or type(timestamp) is not int
            or not 0 <= timestamp <= 253_402_300_799
            or not isinstance(references, tuple)
            or (kind == "request" and bool(references))
            or (kind == "reply" and len(references) > 1)
            or not isinstance(quotations, tuple)
            or (kind == "reply" and len(quotations) != 1)
            or (kind == "request" and bool(quotations))
            or type(supported) is not int or supported < 0
            or type(unsupported) is not int or unsupported < 0
        ):
            raise SalesCorpusIndexError("sales_corpus_message_invalid")
        identifier = keyed_token(
            self._key, MESSAGE_PURPOSE, message_id,
            code="sales_corpus_message_invalid",
        )
        refs = keyed_tokens(
            self._key, MESSAGE_PURPOSE, references,
            code="sales_corpus_message_invalid",
        )
        source_value = self._source_value(source)
        content_value = keyed_token(
            self._key, CONTENT_PURPOSE, content,
            code="sales_corpus_message_invalid",
        )
        quotes = keyed_tokens(
            self._key, QUOTATION_PURPOSE, quotations,
            code="sales_corpus_message_invalid",
        )
        return identifier, refs, source_value, content_value, quotes

    def _source_value(self, source: str) -> bytes:
        self._require_open()
        if not is_hex(source, 64):
            raise SalesCorpusIndexError("sales_corpus_source_invalid")
        return keyed_token(
            self._key, SOURCE_PURPOSE, source, code="sales_corpus_source_invalid",
        )

    def _attachment_values(
        self, source: str, candidate: str, blob: str, content: str,
        parse_status: str, semantic_status: str,
    ) -> tuple[bytes, bytes]:
        self._require_open()
        if (
            not is_hex(source, 32) or not is_hex(blob, 32)
            or parse_status not in {"parsed", "failed", "unparsed"}
            or semantic_status not in {"unreviewed", "approved", "rejected"}
        ):
            raise SalesCorpusIndexError("attachment_binding_invalid")
        candidate_value = keyed_token(
            self._key, ATTACHMENT_CANDIDATE_PURPOSE, candidate,
            code="attachment_binding_invalid",
        )
        content_value = keyed_token(
            self._key, ATTACHMENT_CONTENT_PURPOSE, content,
            code="attachment_binding_invalid",
        )
        return candidate_value, content_value

    def _run(self, operation: Callable[..., object], *args: object):
        self._require_open()
        try:
            return operation(*args)
        except SalesCorpusIndexError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError):
            raise SalesCorpusIndexError("sales_corpus_index_failed") from None

    def _require_open(self) -> None:
        if self._closed:
            raise SalesCorpusIndexError("sales_corpus_index_closed")


__all__ = [
    "AttachmentBindResult",
    "AttachmentSummary",
    "CorpusSummary",
    "MessageUpsertResult",
    "MessageLookupResult",
    "SalesCorpusIndex",
    "SalesCorpusIndexError",
]
