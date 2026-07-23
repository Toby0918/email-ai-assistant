"""Message and pair tests for the governed sales-corpus index."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.mailbox_ingest.sales_corpus_index import SalesCorpusIndex


KEY = b"K" * 32
POLICY = "a" * 64
ONE_REQUEST_SUMMARY = {
    "canonical_message_count": 1,
    "request_count": 1,
    "reply_count": 0,
    "source_record_count": 2,
    "duplicate_message_count": 1,
    "pair_count": 0,
    "paired_message_count": 0,
    "quotation_count": 0,
    "duplicate_quotation_count": 0,
    "supported_attachment_count": 0,
    "unsupported_attachment_count": 0,
}


def _pair_messages():
    request = {
        "kind": "request",
        "message_id_token": "<request-pair@synthetic.external>",
        "reference_tokens": (),
        "trusted_timestamp": 100,
        "vault_record_id": "3" * 32,
        "content_token": "pair request content",
        "quotation_tokens": (),
    }
    reply = {
        "kind": "reply",
        "message_id_token": "<reply-pair@synthetic.internal>",
        "reference_tokens": (request["message_id_token"],),
        "trusted_timestamp": 101,
        "vault_record_id": "4" * 32,
        "content_token": "pair reply content",
        "quotation_tokens": ("pair reply evidence",),
    }
    return request, reply


class SalesCorpusIndexTests(unittest.TestCase):
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

    def test_cross_folder_message_dedupe_is_canonical_and_idempotent(self) -> None:
        index = self._index()
        index.initialize()
        index.bind_policy(POLICY)
        arguments = {
            "kind": "request",
            "message_id_token": "<request-001@synthetic.external>",
            "reference_tokens": (),
            "trusted_timestamp": 1_700_000_000,
            "content_token": "canonical request content token",
            "quotation_tokens": (),
        }

        first = self._upsert(index, vault_record_id="1" * 32, **arguments)
        lookup = index.find_message_record(
            message_id_token=arguments["message_id_token"],
            content_token=arguments["content_token"], source_token="e" * 64,
        )
        duplicate = self._upsert(
            index, vault_record_id=lookup.vault_record_id,
            source_token="e" * 64, **arguments,
        )
        replay = self._upsert(
            index, vault_record_id=lookup.vault_record_id,
            source_token="e" * 64, **arguments,
        )
        seen = index.find_message_record(
            message_id_token=arguments["message_id_token"],
            content_token=arguments["content_token"], source_token="e" * 64,
        )

        self.assertEqual((first.status, duplicate.status, replay.status), (
            "created", "duplicate", "duplicate",
        ))
        self.assertFalse(lookup.source_seen)
        self.assertTrue(seen.source_seen)
        self.assertEqual(lookup.vault_record_id, "1" * 32)
        self.assertEqual(index.summary().to_dict(), ONE_REQUEST_SUMMARY)

    def test_pair_reconciles_in_either_insert_order_and_is_exactly_deduped(self) -> None:
        request, reply = _pair_messages()
        for label, ordered in (
            ("request-first", (request, reply)),
            ("reply-first", (reply, request)),
        ):
            with self.subTest(order=label):
                path = self.root / f"{label}.sqlite3"
                index = SalesCorpusIndex(path, key=KEY)
                index.initialize()
                index.bind_policy(POLICY)
                self._upsert(index, **ordered[0])
                result = self._upsert(index, **ordered[1])
                self._upsert(index, **reply)

                self.assertTrue(result.belongs_to_pair)
                self.assertTrue(index.belongs_to_pair(request["vault_record_id"]))
                self.assertTrue(index.belongs_to_pair(reply["vault_record_id"]))
                summary = index.summary()
                self.assertEqual(
                    (summary.pair_count, summary.paired_message_count), (1, 2)
                )

    def test_exact_reply_quotation_can_support_only_one_pair(self) -> None:
        index = self._index()
        index.initialize()
        index.bind_policy(POLICY)
        evidence = ("same counterparty and cleaned quotation",)

        for offset in (0, 1):
            request_id = f"<quotation-request-{offset}@synthetic.external>"
            self._upsert(index,
                kind="request", message_id_token=request_id,
                reference_tokens=(), trusted_timestamp=200 + (offset * 10),
                vault_record_id=f"{8 + offset * 2:x}" * 32,
                content_token=f"quotation request content {offset}",
                quotation_tokens=(),
            )
            self._upsert(index,
                kind="reply",
                message_id_token=f"<quotation-reply-{offset}@synthetic.internal>",
                reference_tokens=(request_id,),
                trusted_timestamp=201 + (offset * 10),
                vault_record_id=f"{9 + offset * 2:x}" * 32,
                content_token=f"quotation reply content {offset}",
                quotation_tokens=evidence,
            )

        summary = index.summary()
        self.assertEqual((summary.pair_count, summary.paired_message_count), (1, 2))
        self.assertEqual(summary.quotation_count, 1)
        self.assertEqual(summary.duplicate_quotation_count, 1)

    def test_pre_put_lookup_and_earlier_duplicate_timestamp_reconcile_pair(self) -> None:
        index = self._index()
        index.initialize()
        index.bind_policy(POLICY)
        request_id = "<timestamp-request@synthetic.external>"
        request_content = "timestamp request content"
        request_record = "c" * 32
        self._upsert(index,
            kind="request", message_id_token=request_id, reference_tokens=(),
            trusted_timestamp=200, vault_record_id=request_record,
            content_token=request_content, quotation_tokens=(),
        )
        self._upsert(index,
            kind="reply", message_id_token="<timestamp-reply@synthetic.internal>",
            reference_tokens=(request_id,), trusted_timestamp=150,
            vault_record_id="d" * 32, content_token="timestamp reply content",
            quotation_tokens=("timestamp reply evidence",),
        )
        self.assertFalse(index.belongs_to_pair(request_record))

        existing = index.find_message_record(
            message_id_token=request_id, content_token=request_content,
            source_token="e" * 64,
        )
        result = self._upsert(index,
            kind="request", message_id_token=request_id, reference_tokens=(),
            trusted_timestamp=100, vault_record_id=existing.vault_record_id,
            source_token="e" * 64,
            content_token=request_content, quotation_tokens=(),
        )

        self.assertEqual(existing.vault_record_id, request_record)
        self.assertFalse(existing.source_seen)
        self.assertEqual(result.status, "duplicate")
        self.assertTrue(result.belongs_to_pair)
        self.assertEqual(index.summary().source_record_count, 3)


if __name__ == "__main__":
    unittest.main()
