"""Fail-closed retention lifecycle tests for the governed sales corpus."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from backend.mailbox_ingest.models import PurgeReport, VerifyReport
from backend.mailbox_ingest.sales_corpus_index import (
    SalesCorpusIndex,
    SalesCorpusIndexError,
)
from backend.mailbox_ingest.service_operations import PurgeOperation, VerifyOperation


KEY = b"R" * 32
POLICY = "a" * 64
REQUEST_ID = "1" * 32
REPLY_ID = "2" * 32
BLOB_ID = "3" * 32


class _Opened:
    def __init__(self, corpus_index: object, vault: object) -> None:
        self.corpus_index = corpus_index
        self.vault = vault

    def close(self) -> None:
        return None


class SalesCorpusRetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "sales-corpus.sqlite3"
        self.index = SalesCorpusIndex(self.path, key=KEY)
        self.index.initialize()
        self.index.bind_policy(POLICY)
        self.index.upsert_message(
            kind="request", message_id_token="<request@external.test>",
            reference_tokens=(), trusted_timestamp=100,
            vault_record_id=REQUEST_ID, source_token="a" * 64,
            content_token="request content", quotation_tokens=(),
        )
        self.index.upsert_message(
            kind="reply", message_id_token="<reply@internal.test>",
            reference_tokens=("<request@external.test>",),
            trusted_timestamp=101, vault_record_id=REPLY_ID,
            source_token="b" * 64, content_token="reply content",
            quotation_tokens=("exact quotation",),
        )
        self.index.bind_attachment(
            source_record_id=REQUEST_ID, candidate_token="candidate",
            blob_record_id=BLOB_ID, content_token="attachment content",
        )

    def tearDown(self) -> None:
        self.index.close()
        self.temporary.cleanup()

    def test_purge_records_transaction_removes_edges_and_keeps_row_auth_valid(self) -> None:
        self.index.purge_records((REQUEST_ID,))

        self.index.validate(require_policy=True)
        summary = self.index.summary()
        attachments = self.index.attachment_summary()
        self.assertEqual(summary.canonical_message_count, 1)
        self.assertEqual(summary.reply_count, 1)
        self.assertEqual(summary.pair_count, 0)
        self.assertEqual(summary.source_record_count, 1)
        self.assertEqual(attachments.blob_count, 0)
        self.assertEqual(attachments.binding_count, 0)
        self.assertEqual(self.index.vault_record_ids(), (REPLY_ID,))

    def test_verify_rejects_tampered_policy_metadata_before_vault_read(self) -> None:
        connection = sqlite3.connect(self.path)
        try:
            connection.execute(
                "UPDATE corpus_metadata SET policy_hmac=NULL WHERE singleton=1"
            )
            connection.commit()
        finally:
            connection.close()
        vault = _VerifyVault(())

        with self.assertRaises(SalesCorpusIndexError) as caught:
            VerifyOperation(_Opened(self.index, vault)).execute(None)

        self.assertEqual(caught.exception.code, "sales_corpus_auth_invalid")
        self.assertFalse(vault.verified)

    def test_empty_unbound_corpus_allows_a_noop_retention_transaction(self) -> None:
        empty_path = self.path.with_name("empty-sales-corpus.sqlite3")
        empty = SalesCorpusIndex(empty_path, key=KEY)
        try:
            empty.initialize()
            empty.purge_records(())
            self.assertEqual(empty.vault_record_ids(), ())
        finally:
            empty.close()

    def test_normal_query_does_not_create_a_missing_corpus_database(self) -> None:
        missing_path = self.path.with_name("missing-sales-corpus.sqlite3")
        missing = SalesCorpusIndex(missing_path, key=KEY)
        try:
            with self.assertRaises(SalesCorpusIndexError) as caught:
                missing.summary()
            self.assertEqual(caught.exception.code, "sales_corpus_index_failed")
            self.assertFalse(missing_path.exists())
        finally:
            missing.close()

    def test_purge_record_batch_matches_cli_limit_contract(self) -> None:
        record_ids = tuple(f"{index + 100:032x}" for index in range(1_000))

        self.index.purge_records(record_ids)

        self.index.validate(require_policy=True)


class _PurgeCorpus:
    def __init__(self, events: list[object], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail

    def purge_records(self, record_ids: tuple[str, ...]) -> None:
        self.events.append(("corpus", record_ids))
        if self.fail:
            raise SalesCorpusIndexError("sales_corpus_index_failed")


class _PurgeVault:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.ids = (REQUEST_ID, BLOB_ID)
        self.coordinated = False

    @contextmanager
    def coordinated_mutation(self):
        self.events.append("lock_enter")
        self.coordinated = True
        try:
            yield
        finally:
            self.coordinated = False
            self.events.append("lock_exit")

    def plan_expired_purge(self, *, limit: int) -> tuple[str, ...]:
        if not self.coordinated:
            raise AssertionError("purge plan must be coordinated")
        self.events.append(("plan", limit))
        return self.ids

    def purge_planned(self, record_ids: tuple[str, ...]) -> PurgeReport:
        if not self.coordinated:
            raise AssertionError("vault purge must be coordinated")
        self.events.append(("vault", record_ids))
        return PurgeReport(len(record_ids), 0)


class _VerifyCorpus:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def validate(self, *, require_policy: bool = False) -> None:
        self.events.append(("validate", require_policy))

    def vault_record_ids(self) -> tuple[str, ...]:
        self.events.append("ids")
        return (REQUEST_ID, BLOB_ID)


class _VerifyVault:
    def __init__(self, events: list[object] | tuple[()]) -> None:
        self.events = events
        self.verified = False

    def verify(self) -> VerifyReport:
        self.verified = True
        if isinstance(self.events, list):
            self.events.append("verify")
        return VerifyReport(2, 0, 0, 0, 0)

    def count_inactive_or_missing_records(self, record_ids: tuple[str, ...]) -> int:
        if isinstance(self.events, list):
            self.events.append(("cross-check", record_ids))
        return 1


class SalesCorpusServiceLifecycleTests(unittest.TestCase):
    def test_purge_deletes_corpus_before_exact_planned_vault_records(self) -> None:
        events: list[object] = []
        vault = _PurgeVault(events)

        result = PurgeOperation(
            _Opened(_PurgeCorpus(events), vault), limit=7,
        ).execute(None)

        self.assertEqual(result.count, 2)
        self.assertEqual(events, [
            "lock_enter", ("plan", 7), ("corpus", vault.ids),
            ("vault", vault.ids), "lock_exit",
        ])

    def test_purge_stops_before_vault_when_corpus_transaction_fails(self) -> None:
        events: list[object] = []

        with self.assertRaises(SalesCorpusIndexError):
            PurgeOperation(
                _Opened(_PurgeCorpus(events, fail=True), _PurgeVault(events)),
                limit=7,
            ).execute(None)

        self.assertEqual(events, [
            "lock_enter", ("plan", 7),
            ("corpus", (REQUEST_ID, BLOB_ID)), "lock_exit",
        ])

    def test_verify_counts_dangling_corpus_vault_references_as_failures(self) -> None:
        events: list[object] = []

        result = VerifyOperation(
            _Opened(_VerifyCorpus(events), _VerifyVault(events))
        ).execute(None)

        self.assertEqual(result.count, 1)
        self.assertEqual(events, [
            ("validate", False), "ids", "verify",
            ("cross-check", (REQUEST_ID, BLOB_ID)),
        ])


if __name__ == "__main__":
    unittest.main()
