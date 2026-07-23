"""Attachment and lifecycle tests for the governed sales-corpus index."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.mailbox_ingest.sales_corpus_index import (
    SalesCorpusIndex,
    SalesCorpusIndexError,
)


KEY = b"K" * 32
POLICY = "a" * 64
EMPTY_SUMMARY = {
    "canonical_message_count": 0,
    "request_count": 0,
    "reply_count": 0,
    "source_record_count": 0,
    "duplicate_message_count": 0,
    "pair_count": 0,
    "paired_message_count": 0,
    "quotation_count": 0,
    "duplicate_quotation_count": 0,
    "supported_attachment_count": 0,
    "unsupported_attachment_count": 0,
}
ATTACHMENT_SUMMARY = {
    "new_count": 1,
    "duplicate_count": 1,
    "blob_count": 1,
    "binding_count": 2,
    "parsed_count": 1,
    "unreviewed_count": 1,
}


class SalesCorpusIndexLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / "sales-corpus.sqlite3"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _index(self) -> SalesCorpusIndex:
        return SalesCorpusIndex(self.path, key=KEY)

    def _upsert(self, index: SalesCorpusIndex, **message):
        message.setdefault("source_token", message["vault_record_id"] * 2)
        return index.upsert_message(**message)

    def _paired_index(self) -> SalesCorpusIndex:
        index = self._index()
        index.initialize()
        index.bind_policy(POLICY)
        self._upsert(index,
            kind="request", message_id_token="<attachment-root@synthetic.external>",
            reference_tokens=(), trusted_timestamp=100,
            vault_record_id="5" * 32, content_token="attachment root content",
            quotation_tokens=(),
        )
        self._upsert(index,
            kind="reply", message_id_token="<attachment-reply@synthetic.internal>",
            reference_tokens=("<attachment-root@synthetic.external>",),
            trusted_timestamp=101, vault_record_id="6" * 32,
            content_token="attachment reply content",
            quotation_tokens=("attachment reply evidence",),
        )
        return index

    def test_initialize_exposes_only_an_empty_aggregate_summary(self) -> None:
        index = self._index()

        index.initialize()

        self.assertEqual(index.summary().to_dict(), EMPTY_SUMMARY)
        rendered = repr(index)
        self.assertEqual(rendered, "SalesCorpusIndex(<metadata-only>)")
        self.assertNotIn(str(self.path), rendered)
        self.assertNotIn(POLICY, rendered)

    def test_validate_is_read_only_and_can_require_policy_binding(self) -> None:
        index = self._index()
        with self.assertRaises(SalesCorpusIndexError) as caught:
            index.validate()
        self.assertEqual(caught.exception.code, "sales_corpus_schema_invalid")
        self.assertFalse(self.path.exists())

        index.initialize()
        index.validate()
        with self.assertRaises(SalesCorpusIndexError) as caught:
            index.validate(require_policy=True)
        self.assertEqual(caught.exception.code, "sales_corpus_policy_unbound")
        index.bind_policy(POLICY)
        index.validate(require_policy=True)

    def test_attachment_content_reuses_one_blob_and_bindings_are_idempotent(self) -> None:
        index = self._paired_index()

        first = index.bind_attachment(
            source_record_id="5" * 32,
            candidate_token="candidate-one",
            blob_record_id="7" * 32,
            content_token="exact attachment content",
        )
        existing_blob = index.find_attachment_blob(
            content_token="exact attachment content"
        )
        duplicate = index.bind_attachment(
            source_record_id="6" * 32,
            candidate_token="candidate-two",
            blob_record_id=existing_blob,
            content_token="exact attachment content",
        )
        replay = index.bind_attachment(
            source_record_id="6" * 32,
            candidate_token="candidate-two",
            blob_record_id="8" * 32,
            content_token="exact attachment content",
        )

        self.assertEqual((first.status, duplicate.status, replay.status), (
            "new", "duplicate", "duplicate",
        ))
        self.assertEqual(existing_blob, "7" * 32)
        self.assertEqual(first.blob_record_id, "7" * 32)
        self.assertEqual(duplicate.blob_record_id, "7" * 32)
        self.assertEqual(index.attachment_summary().to_dict(), ATTACHMENT_SUMMARY)

    def test_reopen_binds_policy_and_rejects_unknown_schema_objects(self) -> None:
        index = self._paired_index()
        expected = index.summary().to_dict()

        reopened = self._index()
        reopened.initialize()
        reopened.bind_policy(POLICY)
        self.assertEqual(reopened.summary().to_dict(), expected)

        with self.assertRaises(SalesCorpusIndexError) as caught:
            SalesCorpusIndex(self.path, key=b"Z" * 32).initialize()
        self.assertEqual(caught.exception.code, "sales_corpus_key_mismatch")
        self.assertNotIn(str(self.path), repr(caught.exception))

        mismatched = self._index()
        mismatched.initialize()
        with self.assertRaises(SalesCorpusIndexError) as caught:
            mismatched.bind_policy("b" * 64)
        self.assertEqual(caught.exception.code, "sales_corpus_policy_mismatch")
        self.assertNotIn(str(self.path), repr(caught.exception))

        connection = sqlite3.connect(self.path)
        try:
            connection.execute("CREATE TABLE injected_canary (raw_text TEXT)")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(SalesCorpusIndexError) as caught:
            reopened.initialize()
        self.assertEqual(caught.exception.code, "sales_corpus_schema_invalid")
        self.assertNotIn("injected_canary", repr(caught.exception))


if __name__ == "__main__":
    unittest.main()
