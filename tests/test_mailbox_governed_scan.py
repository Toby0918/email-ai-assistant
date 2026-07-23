"""Synthetic governed-corpus scan integration tests."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.mailbox_ingest.authorization import AuthorizationScope, freeze_window
from backend.mailbox_ingest.folder_policy import RawFolder, select_mail_folders
from backend.mailbox_ingest.governed_scan import scan_governed_mailbox
from backend.mailbox_ingest.inventory import build_inventory
from backend.mailbox_ingest.sales_corpus_index import SalesCorpusIndex
from backend.mailbox_ingest.sales_message_policy import parse_sales_corpus_policy
from backend.mailbox_ingest.scan import ScanError
from tests.mailbox_governed_fixtures import (
    _Control,
    _FailOnceIndex,
    _Session,
    _Vault,
)


def _inventory_bundle(session: _Session):
    scope = AuthorizationScope.create(
        "AUTH-CORPUS-1", "sales@company.test", hmac_key=b"S" * 32
    )
    folders = select_mail_folders(
        (
            RawFolder(("\\Inbox",), b"INBOX"),
            RawFolder(("\\Sent",), b"Sent"),
            RawFolder(("\\Archive",), b"Archive"),
        ),
        hmac_key=b"F" * 32,
    )
    window = freeze_window(datetime(2026, 1, 1, tzinfo=timezone.utc))
    return build_inventory(
        session,
        scope=scope,
        folders=folders,
        window=window,
        fingerprint_key=b"I" * 32,
    )


def _sales_policy():
    return parse_sales_corpus_policy(
        {
            "schema_version": 1,
            "company_domain": "company.test",
            "salesperson_allowlist": ["sales@company.test"],
        }
    )


def _scan(session, bundle, policy, vault, control, selected_index):
    return scan_governed_mailbox(
        session=session,
        inventory_bundle=bundle,
        confirmed_fingerprint=bundle.inventory.fingerprint,
        vault=vault,
        control_store=control,
        rebuild_inventory=lambda: bundle,
        sales_policy=policy,
        corpus_index=selected_index,
        identity_key=b"K" * 32,
    )


class GovernedScanTests(unittest.TestCase):
    def _run(
        self, *, duplicate_request: bool = False,
        duplicate_quotation_attachments: bool = False,
        html_forward: bool = False,
        fail_index_once: bool = False, fail_control_write: int | None = None,
    ):
        session = _Session(
            duplicate_request, duplicate_quotation_attachments, html_forward
        )
        bundle = _inventory_bundle(session)
        policy = _sales_policy()
        vault = _Vault()
        control = _Control(fail_on_write=fail_control_write)
        temporary = tempfile.TemporaryDirectory()
        index = SalesCorpusIndex(
            Path(temporary.name) / "corpus-index.sqlite3", key=b"C" * 32
        )
        index.initialize()
        selected_index = _FailOnceIndex(index) if fail_index_once else index
        scan = lambda: _scan(
            session, bundle, policy, vault, control, selected_index
        )
        if fail_index_once or fail_control_write is not None:
            with self.assertRaises(ScanError):
                scan()
            control.fail_on_write = None
        report = scan()
        return report, vault, control, index, temporary

    def test_request_and_later_allowlisted_reply_pair_across_folder_order(self) -> None:
        report, vault, control, index, temporary = self._run()
        self.addCleanup(temporary.cleanup)
        self.addCleanup(index.close)

        self.assertEqual(report.processed_count, 2)
        self.assertEqual(report.unique_message_count, 2)
        self.assertEqual(report.customer_request_count, 1)
        self.assertEqual(report.sales_reply_count, 1)
        self.assertEqual(report.pair_count, 1)
        self.assertEqual(len(vault.records), 2)
        rendered = repr((report, control.payload))
        self.assertNotIn("synthetic widgets", rendered)
        self.assertNotIn("buyer@customer.test", rendered)

    def test_cross_folder_copy_is_processed_but_not_written_twice(self) -> None:
        report, vault, _control, index, temporary = self._run(
            duplicate_request=True
        )
        self.addCleanup(temporary.cleanup)
        self.addCleanup(index.close)

        self.assertEqual(report.processed_count, 3)
        self.assertEqual(report.unique_message_count, 2)
        self.assertEqual(report.duplicate_message_count, 1)
        self.assertEqual(report.pair_count, 1)
        self.assertEqual(report.supported_attachment_count, 1)
        self.assertEqual(len(vault.records), 2)
        self.assertIn(
            int(datetime(2027, 1, 31, tzinfo=timezone.utc).timestamp()),
            vault.expiries.values(),
        )
        database = (Path(temporary.name) / "corpus-index.sqlite3").read_bytes()
        for forbidden in (
            b"buyer@customer.test",
            b"request-1@customer.test",
            b"synthetic widgets",
        ):
            self.assertNotIn(forbidden, database)

    def test_retry_after_vault_commit_before_index_commit_reuses_raw_record(self) -> None:
        report, vault, _control, index, temporary = self._run(
            fail_index_once=True
        )
        self.addCleanup(temporary.cleanup)
        self.addCleanup(index.close)

        self.assertEqual(report.pair_count, 1)
        self.assertEqual(report.duplicate_message_count, 0)
        self.assertEqual(len(vault.records), 2)

    def test_retry_after_index_commit_before_checkpoint_is_idempotent(self) -> None:
        report, vault, control, index, temporary = self._run(
            fail_control_write=2
        )
        self.addCleanup(temporary.cleanup)
        self.addCleanup(index.close)

        self.assertEqual(report.processed_count, 2)
        self.assertEqual(report.pair_count, 1)
        self.assertEqual(report.duplicate_message_count, 0)
        self.assertEqual(len(vault.records), 2)
        self.assertGreaterEqual(control.write_count, 4)

    def test_duplicate_alias_checkpoint_retry_counts_attachments_once(self) -> None:
        report, vault, control, index, temporary = self._run(
            duplicate_request=True, fail_control_write=4
        )
        self.addCleanup(temporary.cleanup)
        self.addCleanup(index.close)

        self.assertEqual(report.processed_count, 3)
        self.assertEqual(report.duplicate_message_count, 1)
        self.assertEqual(report.supported_attachment_count, 1)
        self.assertEqual(len(vault.records), 2)
        self.assertGreaterEqual(control.write_count, 5)

    def test_duplicate_cleaned_quotation_is_not_split_by_attachment_metadata(self) -> None:
        report, vault, _control, index, temporary = self._run(
            duplicate_quotation_attachments=True
        )
        self.addCleanup(temporary.cleanup)
        self.addCleanup(index.close)

        self.assertEqual(report.unique_message_count, 4)
        self.assertEqual(report.pair_count, 1)
        self.assertEqual(report.duplicate_quotation_count, 1)
        self.assertEqual(len(vault.records), 4)

    def test_html_only_forward_fails_closed_before_learning_evidence(self) -> None:
        report, vault, _control, index, temporary = self._run(html_forward=True)
        self.addCleanup(temporary.cleanup)
        self.addCleanup(index.close)

        self.assertEqual(report.processed_count, 1)
        self.assertEqual(report.ambiguous_count, 1)
        self.assertEqual(report.customer_request_count, 0)
        self.assertEqual(report.pair_count, 0)
        self.assertEqual(len(vault.records), 0)

if __name__ == "__main__":
    unittest.main()
