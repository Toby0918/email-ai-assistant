"""Synthetic collaborators for governed-corpus scan tests."""

from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.mailbox_ingest.control_store import ControlStoreError
from backend.mailbox_ingest.models import PutRecordResult
from backend.mailbox_ingest.sales_corpus_index import SalesCorpusIndex


class _Session:
    def __init__(
        self,
        duplicate_request: bool = False,
        duplicate_quotation_attachments: bool = False,
        html_forward: bool = False,
    ) -> None:
        self.folders = self._base_folders(duplicate_request)
        self.attachment_names: dict[int, str] = {}
        self.html_uids: set[int] = set()
        if html_forward:
            self._configure_html_forward()
        if duplicate_request:
            self.attachment_names.update({11: "copy.pdf", 31: "copy.pdf"})
        if duplicate_quotation_attachments:
            self._add_duplicate_quotation_messages()
        self.current = b"INBOX"
        self.calls: list[tuple[object, ...]] = []

    @staticmethod
    def _base_folders(duplicate_request: bool):
        request_header = (
            b"From: buyer@customer.test\r\n"
            b"To: sales@company.test\r\n"
            b"Message-ID: <request-1@customer.test>\r\n"
            b"Subject: synthetic request\r\n\r\n"
        )
        reply_header = (
            b"From: sales@company.test\r\n"
            b"To: buyer@customer.test\r\n"
            b"Message-ID: <reply-1@company.test>\r\n"
            b"In-Reply-To: <request-1@customer.test>\r\n"
            b"Subject: synthetic reply\r\n\r\n"
        )
        request = (
            datetime(2025, 1, 31, tzinfo=timezone.utc),
            request_header,
            b"Please quote ten synthetic widgets.",
        )
        reply = (
            datetime(2025, 2, 2, tzinfo=timezone.utc),
            reply_header,
            b"The synthetic quotation is attached.\r\n--\r\nSales signature",
        )
        request_copy = (
            datetime(2025, 2, 1, tzinfo=timezone.utc),
            request_header,
            request[2],
        )
        return {
            b"INBOX": {11: request},
            b"Sent": {21: reply},
            b"Archive": ({31: request_copy} if duplicate_request else {}),
        }

    def _configure_html_forward(self) -> None:
        request = self.folders[b"INBOX"][11]
        self.folders[b"INBOX"][11] = (
            request[0],
            request[1],
            b"<div>----- Forwarded message -----</div><div>Private history</div>",
        )
        self.folders[b"Sent"] = {}
        self.html_uids.add(11)

    def _add_duplicate_quotation_messages(self) -> None:
        request = self.folders[b"INBOX"][11]
        reply = self.folders[b"Sent"][21]
        second_request = (
            datetime(2025, 2, 3, tzinfo=timezone.utc),
            request[1].replace(b"request-1", b"request-2").replace(
                b"buyer@customer.test", b"buyer@second-customer.test"
            ),
            b"Please quote twenty synthetic widgets.",
        )
        second_reply = (
            datetime(2025, 2, 4, tzinfo=timezone.utc),
            reply[1].replace(b"reply-1", b"reply-2").replace(
                b"request-1", b"request-2"
            ).replace(
                b"buyer@customer.test", b"buyer@second-customer.test"
            ),
            reply[2],
        )
        self.folders[b"INBOX"][12] = second_request
        self.folders[b"Sent"][22] = second_reply
        self.attachment_names = {21: "first.pdf", 22: "second.pdf"}

    def examine(self, mailbox: bytes) -> int:
        self.current = mailbox
        self.calls.append(("examine", mailbox))
        return {b"INBOX": 101, b"Sent": 202, b"Archive": 303}[mailbox]

    def uid_search(self, _since):
        return tuple(self.folders[self.current])

    def uid_fetch_size(self, uid: int):
        when, header, body = self.folders[self.current][uid]
        return type(
            "Size",
            (),
            {"uid": uid, "size": len(header) + len(body), "internal_date": when},
        )()

    def uid_fetch_bodystructure(self, uid: int) -> str:
        body = self.folders[self.current][uid][2]
        if uid in self.html_uids:
            return (
                '("TEXT" "HTML" ("CHARSET" "UTF-8") NIL NIL "8BIT" '
                f"{len(body)} 1)"
            )
        if uid in self.attachment_names:
            name = self.attachment_names[uid]
            return (
                '(("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "8BIT" '
                f'{len(body)} 1) ("APPLICATION" "PDF" ("NAME" "{name}") '
                f'NIL NIL "BASE64" 100 NIL ("ATTACHMENT" ("FILENAME" "{name}"))) '
                '"MIXED")'
            )
        return (
            '("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "8BIT" '
            f"{len(body)} 1)"
        )

    def uid_fetch_peek(
        self,
        uid: int,
        section: str,
        *,
        offset: int | None = None,
        count: int | None = None,
    ) -> bytes:
        self.calls.append(("peek", self.current, uid, section))
        payload = self.folders[self.current][uid][1 if section == "HEADER" else 2]
        if offset is None or count is None:
            return payload
        return payload[offset:offset + count]


class _Control:
    def __init__(self, *, fail_on_write: int | None = None) -> None:
        self.payload = None
        self.fail_on_write = fail_on_write
        self.write_count = 0

    def read(self, _name: str):
        if self.payload is None:
            raise ControlStoreError("control_store_missing")
        return copy.deepcopy(self.payload)

    def write(self, _name: str, payload: dict[str, object]) -> None:
        self.write_count += 1
        if self.write_count == self.fail_on_write:
            raise RuntimeError("synthetic control write failure")
        self.payload = copy.deepcopy(payload)


class _Vault:
    def __init__(self) -> None:
        self.records: dict[bytes, str] = {}
        self.expiries: dict[str, int] = {}
        self.coordinated_depth = 0

    @contextmanager
    def coordinated_mutation(self):
        self.coordinated_depth += 1
        try:
            yield
        finally:
            self.coordinated_depth -= 1

    def put_record_if_absent(self, value: bytes, *, expires_at_utc: int):
        if self.coordinated_depth != 1:
            raise AssertionError("vault write must share the corpus mutation lock")
        existing = self.records.get(value)
        if existing is not None:
            return PutRecordResult(existing, False)
        record_id = f"{len(self.records) + 1:032x}"
        self.records[value] = record_id
        self.expiries[record_id] = expires_at_utc
        return PutRecordResult(record_id, True)

    def constrain_record_expiry(
        self, record_id: str, expires_at_utc: int,
    ) -> None:
        if self.coordinated_depth != 1:
            raise AssertionError("expiry update must share the corpus mutation lock")
        self.expiries[record_id] = min(
            self.expiries[record_id], expires_at_utc,
        )


class _FailOnceIndex:
    def __init__(self, inner: SalesCorpusIndex) -> None:
        self.inner = inner
        self.failed = False

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def upsert_message(self, **values: object):
        if not self.failed:
            self.failed = True
            raise RuntimeError("synthetic index failure")
        return self.inner.upsert_message(**values)
