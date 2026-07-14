"""Synthetic first-pass scan, checkpoint, and deduplication tests."""

from __future__ import annotations

import base64
import unittest
import json
from datetime import datetime, timezone

from backend.mailbox_ingest.authorization import AuthorizationScope, freeze_window
from backend.mailbox_ingest.folder_policy import RawFolder, select_mail_folders
from backend.mailbox_ingest.inventory import build_inventory
from backend.mailbox_ingest.imap_readonly import ImapReadOnlyError
from backend.mailbox_ingest.models import PutRecordResult
from backend.mailbox_ingest.bodystructure import TextBodySection
from backend.mailbox_ingest.scan import ScanError, classify_message, scan_mailbox
from backend.mailbox_ingest.text_body_decoder import (
    MAX_ENCODED_TEXT_BYTES,
    TextBodyDecodeError,
    decode_text_body,
)


BODYSTRUCTURE = (
    '(("TEXT" "PLAIN" NIL NIL NIL "7BIT" 13 1) '
    '("APPLICATION" "PDF" ("NAME" "synthetic.pdf") NIL NIL "BASE64" 100 '
    'NIL ("ATTACHMENT" ("FILENAME" "synthetic.pdf"))) "MIXED")'
)


class FakeScanSession:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.uidvalidity = 77
        self.bodystructure = BODYSTRUCTURE
        self.body_content = None
        self.messages = {
            2: (100, datetime(2023, 6, 1, 8, 0, tzinfo=timezone.utc)),
            3: (200, datetime(2023, 7, 1, 8, 0, tzinfo=timezone.utc)),
        }

    def examine(self, mailbox: str) -> int:
        self.calls.append(("examine", mailbox))
        return self.uidvalidity

    def uid_search(self, _since):
        self.calls.append(("search",))
        return tuple(self.messages)

    def uid_fetch_size(self, uid: int):
        size, date = self.messages[uid]
        return type("Size", (), {"uid": uid, "size": size, "internal_date": date})()

    def uid_fetch_bodystructure(self, uid: int) -> str:
        self.calls.append(("bodystructure", uid))
        return self.bodystructure

    def uid_fetch_peek(
        self,
        uid: int,
        section: str,
        *,
        offset: int | None = None,
        count: int | None = None,
    ) -> bytes:
        self.calls.append(("peek", uid, section, offset, count))
        if section == "HEADER":
            payload = f"Subject: SYNTHETIC-{uid}\r\n\r\n".encode("ascii")
        elif section == "1":
            payload = (
                f"BODY-CANARY-{uid}".encode("ascii")
                if self.body_content is None
                else self.body_content
            )
        else:
            raise AssertionError("attachment body fetched during first pass")
        if offset is None or count is None:
            return payload
        return payload[offset:offset + count]


class FakeControl:
    def __init__(self) -> None:
        self.payload = None
        self.writes: list[dict[str, object]] = []

    def read(self, _name: str):
        if self.payload is None:
            from backend.mailbox_ingest.control_store import ControlStoreError
            raise ControlStoreError("control_store_missing")
        return self.payload

    def write(self, _name: str, payload: dict[str, object]) -> None:
        self.payload = payload.copy()
        self.writes.append(payload.copy())


class FakeVault:
    def __init__(self) -> None:
        self.records: list[tuple[bytes, int]] = []
        self.duplicate_after = 999
        self.fail_after = 999

    def put_record_if_absent(self, plaintext: bytes, *, expires_at_utc: int):
        if len(self.records) >= self.fail_after:
            raise RuntimeError("synthetic interruption")
        self.records.append((plaintext, expires_at_utc))
        created = len(self.records) <= self.duplicate_after
        return PutRecordResult(f"{len(self.records):032x}", created)


class MailboxScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = AuthorizationScope.create(
            "AUTH-SCAN-1", "one@example.test", hmac_key=b"S" * 32
        )
        self.folders = select_mail_folders(
            (RawFolder(("\\Inbox",), "INBOX-CANARY"),), hmac_key=b"F" * 32
        )
        self.window = freeze_window(
            datetime(2024, 2, 29, 12, 30, tzinfo=timezone.utc)
        )
        self.session = FakeScanSession()
        self.bundle = build_inventory(
            self.session,
            scope=self.scope,
            folders=self.folders,
            window=self.window,
            fingerprint_key=b"I" * 32,
        )
        self.session.calls.clear()

    def _run(self, **overrides):
        arguments = {
            "session": self.session,
            "inventory_bundle": self.bundle,
            "confirmed_fingerprint": self.bundle.inventory.fingerprint,
            "vault": FakeVault(),
            "control_store": FakeControl(),
            "rebuild_inventory": lambda: self.bundle,
            "classifier": lambda _header, _bodies: "eligible",
        }
        arguments.update(overrides)
        return scan_mailbox(**arguments), arguments

    def test_fingerprint_is_checked_before_recompute_or_content_fetch(self) -> None:
        calls: list[str] = []
        with self.assertRaisesRegex(ScanError, "inventory_fingerprint_mismatch"):
            self._run(
                confirmed_fingerprint="0" * 64,
                rebuild_inventory=lambda: calls.append("rebuild"),
            )
        self.assertEqual(calls, [])
        self.assertEqual(self.session.calls, [])

    def test_recomputed_inventory_must_match_before_header_or_body_fetch(self) -> None:
        changed = type("Bundle", (), {
            "inventory": type("Inventory", (), {"fingerprint": "1" * 64})()
        })()
        with self.assertRaisesRegex(ScanError, "inventory_changed"):
            self._run(rebuild_inventory=lambda: changed)
        self.assertFalse(any(call[0] in {"bodystructure", "peek"} for call in self.session.calls))

    def test_first_pass_fetches_only_header_and_selected_text_then_encrypts(self) -> None:
        vault = FakeVault()
        control = FakeControl()

        report, _arguments = self._run(vault=vault, control_store=control)

        self.assertEqual((report.processed_count, report.created_count), (2, 2))
        self.assertEqual(report.duplicate_count, 0)
        self.assertEqual(
            [(call[1], call[2]) for call in self.session.calls if call[0] == "peek"],
            [(2, "HEADER"), (2, "1"), (3, "HEADER"), (3, "1")],
        )
        expected_expiry = int(datetime(2025, 6, 1, 8, 0, tzinfo=timezone.utc).timestamp())
        self.assertEqual(vault.records[0][1], expected_expiry)
        stored = json.loads(vault.records[0][0])
        self.assertEqual(stored["scope"], self.scope.opaque_scope_id)
        self.assertEqual(stored["fingerprint"], self.bundle.inventory.fingerprint)
        self.assertEqual(stored["opaque_folder_id"], self.folders[0].opaque_folder_id)
        self.assertEqual(stored["uidvalidity"], 77)
        self.assertEqual(stored["expires_at_utc"], expected_expiry)
        self.assertNotIn("BODY-CANARY", repr(report))
        self.assertNotIn("BODY-CANARY", repr(control.payload))

    def test_first_pass_uses_only_bounded_partial_peek_requests(self) -> None:
        report, _arguments = self._run()

        peek_calls = [call for call in self.session.calls if call[0] == "peek"]
        self.assertEqual(report.processed_count, 2)
        self.assertTrue(peek_calls)
        self.assertTrue(all(call[3] == 0 for call in peek_calls))
        self.assertTrue(all(type(call[4]) is int and 0 < call[4] <= 65_536 for call in peek_calls))

    def test_oversized_declared_text_causes_zero_content_fetches(self) -> None:
        self.session.bodystructure = (
            '("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "8BIT" '
            f'{MAX_ENCODED_TEXT_BYTES + 1} 1)'
        )

        report, _arguments = self._run()

        self.assertEqual(report.ambiguous_count, 2)
        self.assertFalse(any(call[0] == "peek" for call in self.session.calls))

    def test_transport_failures_do_not_advance_cursor_and_resume_same_uid(self) -> None:
        for stage in ("bodystructure", "header", "text"):
            session = FakeScanSession()
            bundle = build_inventory(
                session,
                scope=self.scope,
                folders=self.folders,
                window=self.window,
                fingerprint_key=b"I" * 32,
            )
            session.calls.clear()
            control = FakeControl()
            original_bodystructure = session.uid_fetch_bodystructure
            original_peek = session.uid_fetch_peek

            def bodystructure(uid: int, *, _stage=stage):
                if _stage == "bodystructure" and uid == 2:
                    raise ImapReadOnlyError("imap_fetch_failed")
                return original_bodystructure(uid)

            def peek(
                uid: int,
                section: str,
                *,
                offset: int | None = None,
                count: int | None = None,
                _stage=stage,
            ) -> bytes:
                if uid == 2 and (
                    _stage == "header" and section == "HEADER"
                    or _stage == "text" and section == "1"
                ):
                    raise ImapReadOnlyError("imap_fetch_failed")
                return original_peek(uid, section, offset=offset, count=count)

            session.uid_fetch_bodystructure = bodystructure  # type: ignore[method-assign]
            session.uid_fetch_peek = peek  # type: ignore[method-assign]

            with self.subTest(stage=stage), self.assertRaisesRegex(
                ScanError, "scan_transport_failed"
            ):
                scan_mailbox(
                    session=session,
                    inventory_bundle=bundle,
                    confirmed_fingerprint=bundle.inventory.fingerprint,
                    vault=FakeVault(),
                    control_store=control,
                    rebuild_inventory=lambda: bundle,
                    classifier=lambda _header, _bodies: "eligible",
                )

            folder_state = control.payload["folders"][self.folders[0].opaque_folder_id]
            self.assertEqual(folder_state["cursor"], 0)
            session.uid_fetch_bodystructure = original_bodystructure  # type: ignore[method-assign]
            session.uid_fetch_peek = original_peek  # type: ignore[method-assign]
            report = scan_mailbox(
                session=session,
                inventory_bundle=bundle,
                confirmed_fingerprint=bundle.inventory.fingerprint,
                vault=FakeVault(),
                control_store=control,
                rebuild_inventory=lambda: bundle,
                classifier=lambda _header, _bodies: "eligible",
            )
            self.assertEqual(report.processed_count, 2)

    def test_scan_reselects_folder_with_preserved_wire_mailbox(self) -> None:
        folders = select_mail_folders(
            (RawFolder((), "\u5ba2\u6237", b"&W6JiNw-"),),
            hmac_key=b"F" * 32,
        )
        bundle = build_inventory(
            self.session,
            scope=self.scope,
            folders=folders,
            window=self.window,
            fingerprint_key=b"I" * 32,
        )
        self.session.calls.clear()

        scan_mailbox(
            session=self.session,
            inventory_bundle=bundle,
            confirmed_fingerprint=bundle.inventory.fingerprint,
            vault=FakeVault(),
            control_store=FakeControl(),
            rebuild_inventory=lambda: bundle,
            classifier=lambda _header, _bodies: "eligible",
        )

        selects = [call[1] for call in self.session.calls if call[0] == "examine"]
        self.assertEqual(selects, [b"&W6JiNw-"] * 3)

    def test_resume_advances_only_after_atomic_put_and_skips_completed_uids(self) -> None:
        control = FakeControl()
        first_vault = FakeVault()
        first_vault.fail_after = 1

        with self.assertRaisesRegex(ScanError, "scan_persist_failed"):
            self._run(vault=first_vault, control_store=control)

        self.assertEqual(control.payload["folders"][self.folders[0].opaque_folder_id]["cursor"], 2)
        self.session.calls.clear()
        second_vault = FakeVault()
        report, _arguments = self._run(vault=second_vault, control_store=control)
        self.assertEqual(report.processed_count, 1)
        self.assertFalse(any(call == ("bodystructure", 2) for call in self.session.calls))

    def test_uidvalidity_change_stops_without_resetting_cursor(self) -> None:
        control = FakeControl()
        control.payload = {
            "schema_version": 1,
            "scope": self.scope.opaque_scope_id,
            "fingerprint": self.bundle.inventory.fingerprint,
            "window_start": self.bundle.inventory.window_start.isoformat(),
            "window_end": self.bundle.inventory.window_end.isoformat(),
            "folders": {
                self.folders[0].opaque_folder_id: {
                    "uidvalidity": 77,
                    "cursor": 2,
                    "processed_count": 1,
                }
            },
        }
        self.session.uidvalidity = 78

        with self.assertRaisesRegex(ScanError, "uidvalidity_changed"):
            self._run(control_store=control)

        self.assertEqual(control.payload["folders"][self.folders[0].opaque_folder_id]["cursor"], 2)
        self.assertFalse(any(call[0] == "peek" for call in self.session.calls))

    def test_sensitive_ambiguous_and_duplicate_results_are_counted_without_content(self) -> None:
        outcomes = iter(("sensitive", "ambiguous"))
        report, _arguments = self._run(
            classifier=lambda _header, _body: next(outcomes)
        )
        self.assertEqual((report.sensitive_count, report.ambiguous_count), (1, 1))
        self.assertEqual(report.created_count, 0)

        self.session.calls.clear()
        vault = FakeVault()
        vault.duplicate_after = 0
        report, _arguments = self._run(vault=vault)
        self.assertEqual(report.duplicate_count, 2)
        self.assertEqual(report.created_count, 0)

    def test_transfer_decoding_exposes_sensitive_text_to_classifier(self) -> None:
        encoded = base64.b64encode(b"password credential")
        self.session.bodystructure = (
            '("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL '
            f'"BASE64" {len(encoded)} 1)'
        )
        self.session.body_content = encoded
        vault = FakeVault()

        report, _arguments = self._run(
            vault=vault,
            classifier=classify_message,
        )

        self.assertEqual(report.sensitive_count, 2)
        self.assertEqual(vault.records, [])

    def test_transfer_decode_failure_is_ambiguous_and_not_persisted(self) -> None:
        self.session.bodystructure = (
            '("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "BASE64" 3 1)'
        )
        self.session.body_content = b"%%%"
        vault = FakeVault()

        report, _arguments = self._run(
            vault=vault,
            classifier=classify_message,
        )

        self.assertEqual(report.ambiguous_count, 2)
        self.assertEqual(vault.records, [])


class TextBodyDecoderTests(unittest.TestCase):
    def test_supported_transfer_encodings_decode_strictly_to_utf8(self) -> None:
        cases = (
            ("BASE64", "utf-8", base64.b64encode("\u654f\u611f".encode()), "\u654f\u611f"),
            ("QUOTED-PRINTABLE", "utf-8", b"safe=20text", "safe text"),
            ("7BIT", "us-ascii", b"safe text", "safe text"),
            ("8BIT", "utf-8", "\u654f\u611f".encode(), "\u654f\u611f"),
        )
        for encoding, charset, payload, expected in cases:
            part = TextBodySection("1", encoding, charset, len(payload))
            with self.subTest(encoding=encoding):
                self.assertEqual(decode_text_body(part, payload), expected.encode())

    def test_unsupported_or_malformed_transfer_data_fails_closed(self) -> None:
        cases = (
            (TextBodySection("1", "BINARY", "utf-8", 3), b"abc"),
            (TextBodySection("1", "BASE64", "utf-8", 3), b"%%%"),
            (TextBodySection("1", "QUOTED-PRINTABLE", "utf-8", 4), b"a=ZZ"),
            (TextBodySection("1", "8BIT", "x-unknown", 3), b"abc"),
        )
        for part, payload in cases:
            with self.subTest(part=part), self.assertRaises(TextBodyDecodeError):
                decode_text_body(part, payload)


if __name__ == "__main__":
    unittest.main()
