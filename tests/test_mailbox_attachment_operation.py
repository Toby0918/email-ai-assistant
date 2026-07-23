"""Public aggregate-success semantics for governed attachment execution."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from backend.mailbox_ingest.attachment_operation import AttachmentOperation
from backend.mailbox_ingest.attachment_scan import AttachmentReport


class _Opened:
    vault = object()
    vault_root = Path("E:/synthetic-vault")
    corpus_index = type(
        "CorpusIndex",
        (),
        {
            "find_attachment_blob": staticmethod(lambda _token: None),
            "bind_attachment": staticmethod(lambda **_values: object()),
        },
    )()

    @contextmanager
    def sales_identity_key(self):
        yield bytearray(b"K" * 32)

    def close(self) -> None:
        pass


class AttachmentOperationTests(unittest.TestCase):
    def test_duplicate_blob_does_not_increase_top_level_success_count(
        self,
    ) -> None:
        report = AttachmentReport(
            selected_count=2,
            fetched_count=2,
            parsed_count=2,
            new_blob_count=1,
            duplicate_blob_count=1,
            semantic_unreviewed_count=1,
        )
        with mock.patch(
            "backend.mailbox_ingest.attachment_operation."
            "fetch_prepared_attachments",
            return_value=report,
        ):
            result = AttachmentOperation(_Opened(), object()).execute(object())

        self.assertEqual(result.count, 1)
        self.assertEqual(result.aggregate_counts["parsed"], 2)
        self.assertEqual(result.aggregate_counts["duplicate_blobs"], 1)


if __name__ == "__main__":
    unittest.main()
