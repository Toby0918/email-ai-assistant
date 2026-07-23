"""Tamper-resistance tests for the metadata-only sales corpus index."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.mailbox_ingest.sales_corpus_index import (
    SalesCorpusIndex,
    SalesCorpusIndexError,
)


def _insert_row(
    connection: sqlite3.Connection,
    table: str,
    values: dict[str, object],
) -> None:
    columns = tuple(
        row[1] for row in connection.execute(f"PRAGMA table_info({table})")
    )
    selected = {
        column: values.get(
            column,
            0 if column.endswith("_count") else (
                b"X" * 32 if column.endswith("_mac") else None
            ),
        )
        for column in columns
    }
    placeholders = ",".join("?" for _column in columns)
    connection.execute(
        f"INSERT INTO {table}({','.join(columns)}) VALUES({placeholders})",
        tuple(selected[column] for column in columns),
    )


class SalesCorpusAuthenticationTests(unittest.TestCase):
    def test_policy_metadata_tampering_is_authenticated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "corpus-index.sqlite3"
            index = SalesCorpusIndex(path, key=b"K" * 32)
            index.initialize()
            index.bind_policy("a" * 64)
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "UPDATE corpus_metadata SET policy_hmac=? WHERE singleton=1",
                    (b"X" * 32,),
                )
                connection.commit()

            try:
                with self.assertRaises(SalesCorpusIndexError):
                    index.validate(require_policy=True)
            finally:
                index.close()

    def test_nonempty_corpus_with_null_policy_cannot_be_rebound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "corpus-index.sqlite3"
            index = SalesCorpusIndex(path, key=b"K" * 32)
            index.initialize()
            index.bind_policy("a" * 64)
            index.upsert_message(
                kind="request", message_id_token="1" * 64,
                reference_tokens=(), trusted_timestamp=1,
                vault_record_id="a" * 32, source_token="2" * 64,
                content_token="3" * 64, quotation_tokens=(),
            )
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "UPDATE corpus_metadata SET policy_hmac=NULL WHERE singleton=1"
                )
                connection.commit()

            try:
                with self.assertRaises(SalesCorpusIndexError):
                    index.bind_policy("b" * 64)
            finally:
                index.close()

    def test_forged_pair_rows_cannot_authorize_plaintext_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "corpus-index.sqlite3"
            index = SalesCorpusIndex(path, key=b"K" * 32)
            index.initialize()
            index.bind_policy("a" * 64)
            with closing(sqlite3.connect(path)) as connection:
                _insert_row(connection, "canonical_messages", {
                    "canonical_id": "1" * 32,
                    "kind": "request",
                    "trusted_timestamp": 1,
                    "vault_record_id": "a" * 32,
                    "content_hmac": b"A" * 32,
                })
                _insert_row(connection, "canonical_messages", {
                    "canonical_id": "2" * 32,
                    "kind": "reply",
                    "trusted_timestamp": 2,
                    "vault_record_id": "b" * 32,
                    "content_hmac": b"B" * 32,
                })
                _insert_row(connection, "pairs", {
                    "request_id": "1" * 32,
                    "reply_id": "2" * 32,
                    "quotation_hmac": b"Q" * 32,
                })
                connection.commit()

            try:
                with self.assertRaises(SalesCorpusIndexError):
                    index.belongs_to_pair("a" * 32)
                with self.assertRaises(SalesCorpusIndexError):
                    index.validate(require_policy=True)
            finally:
                index.close()


if __name__ == "__main__":
    unittest.main()
