"""Fail-closed governed scan tests for transport and corpus conflicts."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.mailbox_ingest.sales_corpus_index import SalesCorpusIndex
from backend.mailbox_ingest.scan import ScanError
from tests.mailbox_governed_fixtures import _Control, _Session, _Vault
from tests.test_mailbox_governed_scan import (
    _inventory_bundle,
    _sales_policy,
    _scan,
)


class _ChangingUidvaliditySession(_Session):
    inbox_uidvalidity = 101

    def examine(self, mailbox: bytes) -> int:
        self.current = mailbox
        self.calls.append(("examine", mailbox))
        if mailbox == b"INBOX":
            return self.inbox_uidvalidity
        return {b"Sent": 202, b"Archive": 303}[mailbox]


class GovernedScanGuardTests(unittest.TestCase):
    def _index(self) -> tuple[SalesCorpusIndex, tempfile.TemporaryDirectory]:
        temporary = tempfile.TemporaryDirectory()
        index = SalesCorpusIndex(
            Path(temporary.name) / "corpus-index.sqlite3", key=b"C" * 32
        )
        index.initialize()
        self.addCleanup(temporary.cleanup)
        self.addCleanup(index.close)
        return index, temporary

    def test_uidvalidity_change_after_bodystructure_stops_before_body_fetch(self) -> None:
        class ChangingSession(_ChangingUidvaliditySession):
            def uid_fetch_bodystructure(self, uid: int) -> str:
                value = super().uid_fetch_bodystructure(uid)
                if self.current == b"INBOX":
                    self.inbox_uidvalidity = 999
                return value

        session = ChangingSession()
        index, _temporary = self._index()

        with self.assertRaisesRegex(ScanError, "uidvalidity_changed"):
            _scan(
                session, _inventory_bundle(session), _sales_policy(),
                _Vault(), _Control(), index,
            )

        self.assertFalse(
            any(
                call[0] == "peek" and call[1] == b"INBOX"
                for call in session.calls
            )
        )
        self.assertEqual(index.summary().request_count, 0)

    def test_uidvalidity_change_during_body_fetch_stops_before_persist(self) -> None:
        class ChangingSession(_ChangingUidvaliditySession):
            def uid_fetch_peek(self, uid: int, section: str, **kwargs: int) -> bytes:
                value = super().uid_fetch_peek(uid, section, **kwargs)
                if self.current == b"INBOX" and section != "HEADER":
                    self.inbox_uidvalidity = 999
                return value

        session = ChangingSession()
        index, _temporary = self._index()

        with self.assertRaisesRegex(ScanError, "uidvalidity_changed"):
            _scan(
                session, _inventory_bundle(session), _sales_policy(),
                _Vault(), _Control(), index,
            )

        self.assertEqual(index.summary().request_count, 0)

    def test_uidvalidity_change_during_ambiguous_body_fetch_still_fails_closed(
        self,
    ) -> None:
        class ChangingSession(_ChangingUidvaliditySession):
            def uid_fetch_peek(
                self, uid: int, section: str, **kwargs: int,
            ) -> bytes:
                value = super().uid_fetch_peek(uid, section, **kwargs)
                if self.current == b"INBOX" and section != "HEADER":
                    self.inbox_uidvalidity = 999
                return value

        session = ChangingSession()
        when, header, _body = session.folders[b"INBOX"][11]
        session.folders[b"INBOX"][11] = (when, header, b"\xff")
        index, _temporary = self._index()

        with self.assertRaisesRegex(ScanError, "uidvalidity_changed"):
            _scan(
                session, _inventory_bundle(session), _sales_policy(),
                _Vault(), _Control(), index,
            )

        self.assertEqual(index.summary().request_count, 0)

    def test_conflicting_message_id_does_not_shorten_existing_record_expiry(self) -> None:
        vault, control = _Vault(), _Control()
        index, _temporary = self._index()
        initial = _Session()
        _scan(
            initial, _inventory_bundle(initial), _sales_policy(),
            vault, control, index,
        )
        before = dict(vault.expiries)
        conflicting = _Session(duplicate_request=True)
        _when, header, _body = conflicting.folders[b"Archive"][31]
        conflicting.folders[b"Archive"][31] = (
            datetime(2024, 3, 1, tzinfo=timezone.utc),
            header,
            b"Conflicting synthetic request content.",
        )

        with self.assertRaisesRegex(ScanError, "sales_corpus_index_failed"):
            _scan(
                conflicting, _inventory_bundle(conflicting), _sales_policy(),
                vault, _Control(), index,
            )

        self.assertEqual(vault.expiries, before)

    def test_unfetched_attachment_prevents_exact_aggregate_dedup(
        self,
    ) -> None:
        session = _Session(duplicate_request=True)
        for mailbox, uid in ((b"INBOX", 11), (b"Archive", 31)):
            when, header, body = session.folders[mailbox][uid]
            session.folders[mailbox][uid] = (
                when,
                header.replace(
                    b"\r\n\r\n",
                    b"\r\nAuto-Submitted: auto-generated\r\n\r\n",
                ),
                body,
            )
        index, _temporary = self._index()

        report = _scan(
            session, _inventory_bundle(session), _sales_policy(),
            _Vault(), _Control(), index,
        )

        self.assertEqual(report.processed_count, 3)
        self.assertEqual(report.excluded_automated_count, 2)
        self.assertEqual(report.supported_attachment_count, 2)

    def test_same_excluded_text_with_different_attachment_is_not_deduplicated(
        self,
    ) -> None:
        session = _Session(duplicate_request=True)
        session.attachment_names[31] = "different.pdf"
        for mailbox, uid in ((b"INBOX", 11), (b"Archive", 31)):
            when, header, body = session.folders[mailbox][uid]
            session.folders[mailbox][uid] = (
                when,
                header.replace(
                    b"\r\n\r\n",
                    b"\r\nAuto-Submitted: auto-generated\r\n\r\n",
                ),
                body,
            )
        index, _temporary = self._index()

        report = _scan(
            session, _inventory_bundle(session), _sales_policy(),
            _Vault(), _Control(), index,
        )

        self.assertEqual(report.processed_count, 3)
        self.assertEqual(report.excluded_automated_count, 2)
        self.assertEqual(report.supported_attachment_count, 2)

    def test_exact_html_ambiguous_copy_uses_raw_bytes_for_aggregate_dedup(
        self,
    ) -> None:
        session = _Session(duplicate_request=True)
        session.html_uids.update({11, 31})
        index, _temporary = self._index()

        report = _scan(
            session, _inventory_bundle(session), _sales_policy(),
            _Vault(), _Control(), index,
        )

        self.assertEqual(report.processed_count, 2)
        self.assertEqual(report.ambiguous_count, 1)

    def test_transfer_metadata_distinguishes_same_raw_body_and_attachment(
        self,
    ) -> None:
        class MetadataSession(_Session):
            def uid_fetch_bodystructure(self, uid: int) -> str:
                if uid not in {11, 31}:
                    return super().uid_fetch_bodystructure(uid)
                encoding = "8BIT" if uid == 11 else "BASE64"
                return (
                    '("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL '
                    f'"{encoding}" 4 1)'
                )

        session = MetadataSession(duplicate_request=True)
        for mailbox, uid in ((b"INBOX", 11), (b"Archive", 31)):
            when, header, _body = session.folders[mailbox][uid]
            session.folders[mailbox][uid] = (
                when,
                header.replace(
                    b"\r\n\r\n",
                    b"\r\nAuto-Submitted: auto-generated\r\n\r\n",
                ),
                b"QUJD",
            )
        index, _temporary = self._index()

        report = _scan(
            session, _inventory_bundle(session), _sales_policy(),
            _Vault(), _Control(), index,
        )

        self.assertEqual(report.processed_count, 3)
        self.assertEqual(report.excluded_automated_count, 2)
        self.assertEqual(report.supported_attachment_count, 0)

    def test_unselected_alternative_part_distinguishes_exact_outcome(
        self,
    ) -> None:
        class AlternativeSession(_Session):
            def uid_fetch_bodystructure(self, uid: int) -> str:
                if uid not in {11, 31}:
                    return super().uid_fetch_bodystructure(uid)
                html_size = 4 if uid == 11 else 5
                return (
                    '(("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL '
                    '"8BIT" 4 1) '
                    '("TEXT" "HTML" ("CHARSET" "UTF-8") NIL NIL '
                    f'"8BIT" {html_size} 1) "ALTERNATIVE")'
                )

        session = AlternativeSession(duplicate_request=True)
        for mailbox, uid in ((b"INBOX", 11), (b"Archive", 31)):
            when, header, _body = session.folders[mailbox][uid]
            session.folders[mailbox][uid] = (
                when,
                header.replace(
                    b"\r\n\r\n",
                    b"\r\nAuto-Submitted: auto-generated\r\n\r\n",
                ),
                b"QUJD",
            )
        index, _temporary = self._index()

        report = _scan(
            session, _inventory_bundle(session), _sales_policy(),
            _Vault(), _Control(), index,
        )

        self.assertEqual(report.processed_count, 3)
        self.assertEqual(report.excluded_automated_count, 2)


if __name__ == "__main__":
    unittest.main()
