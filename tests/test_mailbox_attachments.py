"""Reviewed representative-attachment pass tests using synthetic data only."""

from __future__ import annotations

import base64
import io
import json
import tempfile
import unittest
from collections import deque
from pathlib import Path

from backend.mailbox_ingest.attachment_scan import (
    AttachmentScanError,
    fetch_prepared_attachments,
    parse_reviewed_manifest,
    prepare_attachments,
)
from backend.mailbox_ingest.models import PutRecordResult, SecretBuffer
from backend.mailbox_ingest.attachment_security import validate_attachment_content
from pypdf import PdfWriter


SCOPE = "a" * 64
FINGERPRINT = "b" * 64
SOURCE_ID = "1" * 32
CANDIDATE_ID = "2" * 32


def manifest_payload(*, mime_type: str = "image/png", size: int = 12):
    return {
        "schema_version": 1,
        "scope": SCOPE,
        "fingerprint": FINGERPRINT,
        "issued_at_utc": 1_700_000_000,
        "expires_at_utc": 1_700_003_600,
        "approval_id": "c" * 32,
        "selections": [
            {
                "source_record_id": SOURCE_ID,
                "candidate_id": CANDIDATE_ID,
                "expected_size": size,
                "mime_type": mime_type,
                "business_approved": True,
                "privacy_approved": True,
            }
        ],
    }


def source_payload(*, mime_type: str = "image/png", size: int = 12):
    return json.dumps(
        {
            "schema_version": 1,
            "scope": SCOPE,
            "fingerprint": FINGERPRINT,
            "opaque_folder_id": "d" * 64,
            "mailbox": "SYNTHETIC-INBOX",
            "uidvalidity": 77,
            "uid": 9,
            "expires_at_utc": 1_800_000_000,
            "attachments": [
                {
                    "candidate_id": CANDIDATE_ID,
                    "section": "2",
                    "mime_type": mime_type,
                    "size": size,
                    "filename": "SYNTHETIC-NAME.png",
                }
            ],
        },
        sort_keys=True,
    ).encode("utf-8")


class FakeAttachmentSession:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.calls: list[tuple[object, ...]] = []
        self.uidvalidity = 77

    def examine(self, mailbox: str) -> int:
        self.calls.append(("examine", mailbox))
        return self.uidvalidity

    def uid_fetch_peek(
        self, uid: int, section: str, *, offset: int, count: int
    ) -> bytes:
        self.calls.append(("peek", uid, section, offset, count))
        return self.content[offset:offset + count]


class FakeAttachmentVault:
    def __init__(self) -> None:
        self.records: list[tuple[bytes, int]] = []

    def put_record_if_absent(self, value: bytes, *, expires_at_utc: int):
        self.records.append((value, expires_at_utc))
        return PutRecordResult("3" * 32, True)


class AttachmentManifestTests(unittest.TestCase):
    def test_manifest_is_strict_opaque_dual_approved_and_capped_at_fifty(self) -> None:
        manifest = parse_reviewed_manifest(
            manifest_payload(),
            expected_scope=SCOPE,
            expected_fingerprint=FINGERPRINT,
            now_utc=1_700_000_100,
        )
        self.assertEqual(len(manifest.selections), 1)
        self.assertNotIn(SOURCE_ID, repr(manifest))

        invalid = manifest_payload()
        invalid["mailbox"] = "forbidden"
        with self.assertRaises(AttachmentScanError):
            parse_reviewed_manifest(
                invalid,
                expected_scope=SCOPE,
                expected_fingerprint=FINGERPRINT,
                now_utc=1_700_000_100,
            )

        too_many = manifest_payload()
        too_many["selections"] = [
            {
                **too_many["selections"][0],
                "source_record_id": f"{index + 1:032x}",
                "candidate_id": f"{index + 100:032x}",
            }
            for index in range(51)
        ]
        with self.assertRaisesRegex(AttachmentScanError, "attachment_selection_limit"):
            parse_reviewed_manifest(
                too_many,
                expected_scope=SCOPE,
                expected_fingerprint=FINGERPRINT,
                now_utc=1_700_000_100,
            )

    def test_manifest_rejects_expiry_missing_approval_duplicates_and_caps(self) -> None:
        cases = {}
        expired = manifest_payload()
        expired["expires_at_utc"] = 1_700_000_000
        cases["expired"] = expired
        approval = manifest_payload()
        approval["selections"][0]["privacy_approved"] = False
        cases["approval"] = approval
        oversized = manifest_payload(size=10 * 1024 * 1024 + 1)
        cases["oversized"] = oversized
        duplicate = manifest_payload()
        duplicate["selections"] *= 2
        cases["duplicate"] = duplicate

        for label, payload in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(AttachmentScanError):
                    parse_reviewed_manifest(
                        payload,
                        expected_scope=SCOPE,
                        expected_fingerprint=FINGERPRINT,
                        now_utc=1_700_000_100,
                    )

    def test_manifest_rejects_unsupported_type_before_source_or_network_access(self) -> None:
        with self.assertRaisesRegex(
            AttachmentScanError, "attachment_type_unsupported"
        ):
            parse_reviewed_manifest(
                manifest_payload(mime_type="image/svg+xml"),
                expected_scope=SCOPE,
                expected_fingerprint=FINGERPRINT,
                now_utc=1_700_000_100,
            )

    def test_prepare_reads_one_source_at_a_time_and_revalidates_mapping(self) -> None:
        manifest = parse_reviewed_manifest(
            manifest_payload(),
            expected_scope=SCOPE,
            expected_fingerprint=FINGERPRINT,
            now_utc=1_700_000_100,
        )
        secret = SecretBuffer(source_payload())
        reads: list[str] = []

        prepared = prepare_attachments(
            manifest,
            read_source_record=lambda record_id: reads.append(record_id) or secret,
        )

        self.assertEqual(reads, [SOURCE_ID])
        self.assertEqual(bytes(secret), bytes(len(secret)))
        self.assertEqual(len(prepared.items), 1)
        self.assertNotIn("SYNTHETIC-INBOX", repr(prepared))
        self.assertNotIn("SYNTHETIC-NAME", repr(prepared))


class PdfSecurityTests(unittest.TestCase):
    def _pdf(self, *, encrypted: bool = False) -> bytes:
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        if encrypted:
            writer.encrypt("synthetic-password")
        writer.write(output)
        return output.getvalue()

    def test_parsed_safe_pdf_is_accepted(self) -> None:
        validate_attachment_content(self._pdf(), "application/pdf")

    def test_pdf_name_escapes_actions_embeds_and_object_streams_are_rejected(self) -> None:
        names = (
            b"/Java#53cript", b"/J#53", b"/Launch", b"/EmbeddedFile",
            b"/Filespec", b"/OpenAction", b"/AA", b"/ObjStm",
        )
        for name in names:
            with self.subTest(name=name), self.assertRaises(AttachmentScanError):
                validate_attachment_content(
                    b"%PDF-1.7\n1 0 obj << " + name + b" true >> endobj\n%%EOF",
                    "application/pdf",
                )

    def test_encrypted_or_malformed_pdf_is_rejected(self) -> None:
        for content in (self._pdf(encrypted=True), b"%PDF-1.7\n%%EOF"):
            with self.subTest(size=len(content)), self.assertRaises(AttachmentScanError):
                validate_attachment_content(content, "application/pdf")


class AttachmentFetchTests(unittest.TestCase):
    def _prepared(self, *, mime_type="image/png", content=b"\x89PNG\r\n\x1a\nDATA"):
        payload = manifest_payload(mime_type=mime_type, size=len(content))
        manifest = parse_reviewed_manifest(
            payload,
            expected_scope=SCOPE,
            expected_fingerprint=FINGERPRINT,
            now_utc=1_700_000_100,
        )
        return prepare_attachments(
            manifest,
            read_source_record=lambda _record_id: SecretBuffer(
                source_payload(mime_type=mime_type, size=len(content))
            ),
        )

    def test_success_rechecks_uidvalidity_chunks_with_peek_and_encrypts(self) -> None:
        content = b"\x89PNG\r\n\x1a\nDATA"
        prepared = self._prepared(content=content)
        session = FakeAttachmentSession(content)
        vault = FakeAttachmentVault()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            report = fetch_prepared_attachments(
                prepared,
                session=session,
                vault=vault,
                vault_root=root,
                parser=lambda path, _mime: path.read_bytes()[-4:],
                chunk_size=4,
                clock=lambda: 1_700_000_100,
            )

            self.assertEqual((report.accepted_count, report.skipped_count), (1, 0))
            self.assertTrue(all(call[-1] <= 4 for call in session.calls if call[0] == "peek"))
            transferred = sum(
                len(content[call[3]:call[3] + call[4]])
                for call in session.calls
                if call[0] == "peek"
            )
            self.assertEqual(transferred, len(content))
            self.assertEqual(len(vault.records), 1)
            self.assertIn(base64.b64encode(content).decode("ascii").encode("ascii"), vault.records[0][0])
            temp_root = root / "restricted-temp"
            self.assertTrue(not temp_root.exists() or not any(temp_root.iterdir()))

    def test_uidvalidity_size_magic_and_active_content_fail_before_persist(self) -> None:
        cases = {
            "uidvalidity": (b"\x89PNG\r\n\x1a\nDATA", "image/png", 78),
            "magic mismatch": (b"NOT-A-PNG!!", "image/png", 77),
            "active PDF": (b"%PDF-1.7\n/JavaScript /JS", "application/pdf", 77),
        }
        for label, (content, mime_type, uidvalidity) in cases.items():
            with self.subTest(label=label):
                prepared = self._prepared(mime_type=mime_type, content=content)
                session = FakeAttachmentSession(content)
                session.uidvalidity = uidvalidity
                vault = FakeAttachmentVault()
                with tempfile.TemporaryDirectory() as directory:
                    with self.assertRaises(AttachmentScanError):
                        fetch_prepared_attachments(
                            prepared,
                            session=session,
                            vault=vault,
                            vault_root=Path(directory),
                            parser=lambda _path, _mime: b"parsed",
                            chunk_size=4,
                            clock=lambda: 1_700_000_100,
                        )
                self.assertEqual(vault.records, [])

    def test_parser_failure_or_short_transfer_removes_plaintext_temp(self) -> None:
        content = b"\x89PNG\r\n\x1a\nDATA"
        prepared = self._prepared(content=content)
        for label, session in {
            "parser": FakeAttachmentSession(content),
            "short": FakeAttachmentSession(content[:-1]),
        }.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                parser = (
                    (lambda _path, _mime: (_ for _ in ()).throw(RuntimeError("canary")))
                    if label == "parser"
                    else (lambda _path, _mime: b"parsed")
                )
                with self.assertRaises(AttachmentScanError):
                    fetch_prepared_attachments(
                        prepared,
                        session=session,
                        vault=FakeAttachmentVault(),
                        vault_root=root,
                        parser=parser,
                        chunk_size=4,
                        clock=lambda: 1_700_000_100,
                    )
                temp_root = root / "restricted-temp"
                self.assertTrue(not temp_root.exists() or not any(temp_root.iterdir()))

    def test_manifest_expiry_is_rechecked_immediately_before_persistence(self) -> None:
        content = b"\x89PNG\r\n\x1a\nDATA"
        prepared = self._prepared(content=content)
        ticks = deque((1_700_003_599, 1_700_003_600))
        vault = FakeAttachmentVault()

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                AttachmentScanError, "attachment_manifest_expired"
            ):
                fetch_prepared_attachments(
                    prepared,
                    session=FakeAttachmentSession(content),
                    vault=vault,
                    vault_root=Path(directory),
                    parser=lambda _path, _mime: b"parsed",
                    chunk_size=4,
                    clock=ticks.popleft,
                )

        self.assertEqual(vault.records, [])


if __name__ == "__main__":
    unittest.main()
