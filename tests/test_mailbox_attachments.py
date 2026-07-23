"""Reviewed representative-attachment pass tests using synthetic data only."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from collections import deque
from contextlib import contextmanager
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
    def __init__(self, *, created: bool = True) -> None:
        self.records: list[tuple[bytes, int]] = []
        self._payload_records: dict[bytes, str] = {}
        self.extended_expiries: list[int] = []
        self.created = created
        self.coordinated_depth = 0

    @contextmanager
    def coordinated_mutation(self):
        self.coordinated_depth += 1
        try:
            yield
        finally:
            self.coordinated_depth -= 1

    def put_record_if_absent(
        self, value: bytes, *, expires_at_utc: int,
        extend_expiry_on_duplicate: bool = False,
    ):
        if self.coordinated_depth != 1:
            raise AssertionError("blob binding must share the vault mutation lock")
        if value in self._payload_records:
            if extend_expiry_on_duplicate:
                self.extended_expiries.append(expires_at_utc)
            return PutRecordResult(self._payload_records[value], False)
        self.records.append((value, expires_at_utc))
        record_id = "3" * 32
        self._payload_records[value] = record_id
        return PutRecordResult(record_id, self.created)


class FakeAttachmentCorpus:
    def __init__(self, *, existing_blob: str | None = None) -> None:
        self.existing_blob = existing_blob
        self.bindings: list[tuple[str, str]] = []

    def content_token(self, content: bytes) -> str:
        if not content:
            raise AssertionError("synthetic attachment content must not be empty")
        return "e" * 64

    def find_blob(self, token: str) -> str | None:
        if token != "e" * 64:
            raise AssertionError("unexpected synthetic content token")
        return self.existing_blob

    def bind_blob(self, _item: object, blob_id: str, token: str) -> object:
        self.bindings.append((blob_id, token))
        status = "duplicate" if self.existing_blob is not None else "new"
        return type("Binding", (), {"status": status})()

    def callbacks(self) -> dict[str, object]:
        return {
            "content_token_factory": self.content_token,
            "find_existing_blob": self.find_blob,
            "bind_blob": self.bind_blob,
        }


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
            source_is_paired=lambda _record_id: True,
        )

        self.assertEqual(reads, [SOURCE_ID])
        self.assertEqual(bytes(secret), bytes(len(secret)))
        self.assertEqual(len(prepared.items), 1)
        self.assertNotIn("SYNTHETIC-INBOX", repr(prepared))
        self.assertNotIn("SYNTHETIC-NAME", repr(prepared))

    def test_prepare_requires_pair_gate_before_raw_record_read(self) -> None:
        manifest = parse_reviewed_manifest(
            manifest_payload(),
            expected_scope=SCOPE,
            expected_fingerprint=FINGERPRINT,
            now_utc=1_700_000_100,
        )
        reads: list[str] = []

        with self.assertRaises(TypeError):
            prepare_attachments(
                manifest,
                read_source_record=lambda record_id: reads.append(record_id),
            )

        self.assertEqual(reads, [])

    def test_prepare_rejects_an_unpaired_source_before_raw_record_read(self) -> None:
        manifest = parse_reviewed_manifest(
            manifest_payload(),
            expected_scope=SCOPE,
            expected_fingerprint=FINGERPRINT,
            now_utc=1_700_000_100,
        )
        reads: list[str] = []

        with self.assertRaisesRegex(
            AttachmentScanError, "attachment_source_not_paired"
        ):
            prepare_attachments(
                manifest,
                read_source_record=lambda record_id: reads.append(record_id),
                source_is_paired=lambda _record_id: False,
            )

        self.assertEqual(reads, [])


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
            source_is_paired=lambda _record_id: True,
        )

    def test_fetch_requires_all_corpus_callbacks_before_network_access(self) -> None:
        content = b"\x89PNG\r\n\x1a\nDATA"
        prepared = self._prepared(content=content)
        session = FakeAttachmentSession(content)

        with tempfile.TemporaryDirectory() as directory, self.assertRaises(TypeError):
            fetch_prepared_attachments(
                prepared,
                session=session,
                vault=FakeAttachmentVault(),
                vault_root=Path(directory),
                parser=lambda _path, _mime: b"parsed",
                clock=lambda: 1_700_000_100,
            )

        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(
            AttachmentScanError, "attachment_fetch_invalid"
        ):
            fetch_prepared_attachments(
                prepared,
                session=session,
                vault=FakeAttachmentVault(),
                vault_root=Path(directory),
                parser=lambda _path, _mime: b"parsed",
                clock=lambda: 1_700_000_100,
                content_token_factory=None,  # type: ignore[arg-type]
                find_existing_blob=None,  # type: ignore[arg-type]
                bind_blob=None,  # type: ignore[arg-type]
            )

        self.assertEqual(session.calls, [])

    def test_success_rechecks_uidvalidity_chunks_with_peek_and_encrypts(self) -> None:
        content = b"\x89PNG\r\n\x1a\nDATA"
        prepared = self._prepared(content=content)
        session = FakeAttachmentSession(content)
        vault = FakeAttachmentVault()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = FakeAttachmentCorpus()

            report = fetch_prepared_attachments(
                prepared,
                session=session,
                vault=vault,
                vault_root=root,
                parser=lambda path, _mime: path.read_bytes()[-4:],
                chunk_size=4,
                clock=lambda: 1_700_000_100,
                **corpus.callbacks(),
            )

            self.assertEqual(
                (
                    report.selected_count,
                    report.fetched_count,
                    report.parsed_count,
                    report.new_blob_count,
                    report.duplicate_blob_count,
                    report.semantic_unreviewed_count,
                ),
                (1, 1, 1, 1, 0, 1),
            )
            self.assertTrue(all(call[-1] <= 4 for call in session.calls if call[0] == "peek"))
            transferred = sum(
                len(content[call[3]:call[3] + call[4]])
                for call in session.calls
                if call[0] == "peek"
            )
            self.assertEqual(transferred, len(content))
            self.assertEqual(len(vault.records), 1)
            record = vault.records[0][0]
            self.assertEqual(
                record, b"MAILBOX-ATTACHMENT-BLOB-V1\0" + content
            )
            self.assertNotIn(SOURCE_ID.encode("ascii"), record)
            self.assertNotIn(CANDIDATE_ID.encode("ascii"), record)
            temp_root = root / "restricted-temp"
            self.assertTrue(not temp_root.exists() or not any(temp_root.iterdir()))

    def test_existing_content_blob_is_reported_without_inflating_new_evidence(self) -> None:
        content = b"\x89PNG\r\n\x1a\nDATA"
        prepared = self._prepared(content=content)
        vault = FakeAttachmentVault()
        vault._payload_records[
            b"MAILBOX-ATTACHMENT-BLOB-V1\0" + content
        ] = "3" * 32
        corpus = FakeAttachmentCorpus(existing_blob="3" * 32)

        with tempfile.TemporaryDirectory() as directory:
            report = fetch_prepared_attachments(
                prepared,
                session=FakeAttachmentSession(content),
                vault=vault,
                vault_root=Path(directory),
                parser=lambda path, _mime: path.read_bytes()[-4:],
                clock=lambda: 1_700_000_100,
                **corpus.callbacks(),
            )

        self.assertEqual(vault.records, [])
        self.assertEqual(
            vault.extended_expiries, [prepared.items[0].expires_at_utc]
        )
        self.assertEqual(report.new_blob_count, 0)
        self.assertEqual(report.duplicate_blob_count, 1)
        self.assertEqual(report.semantic_unreviewed_count, 0)

    def test_binding_retry_reuses_raw_byte_blob_when_parser_output_changes(self) -> None:
        content = b"\x89PNG\r\n\x1a\nDATA"
        prepared = self._prepared(content=content)
        vault = FakeAttachmentVault()
        parser_outputs = deque((b"PARSE-ONE", b"PARSE-TWO"))
        bind_calls = 0

        def bind(_item: object, _blob_id: str, _token: str) -> object:
            nonlocal bind_calls
            bind_calls += 1
            if bind_calls == 1:
                raise RuntimeError("synthetic bind interruption")
            return type("Binding", (), {"status": "new"})()

        def run(root: Path):
            return fetch_prepared_attachments(
                prepared, session=FakeAttachmentSession(content), vault=vault,
                vault_root=root,
                parser=lambda _path, _mime: parser_outputs.popleft(),
                clock=lambda: 1_700_000_100,
                content_token_factory=lambda _content: "e" * 64,
                find_existing_blob=lambda _token: None,
                bind_blob=bind,
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(
                AttachmentScanError, "attachment_persist_failed"
            ):
                run(root)
            report = run(root)

        self.assertEqual(report.new_blob_count, 1)
        self.assertEqual(len(vault.records), 1)
        self.assertEqual(
            vault.records[0][0], b"MAILBOX-ATTACHMENT-BLOB-V1\0" + content
        )
        self.assertNotIn(b"PARSE-ONE", vault.records[0][0])
        self.assertNotIn(b"PARSE-TWO", vault.records[0][0])

    def test_index_lookup_reuses_blob_and_extends_bounded_expiry(self) -> None:
        content = b"\x89PNG\r\n\x1a\nDATA"
        prepared = self._prepared(content=content)
        vault = FakeAttachmentVault()
        vault._payload_records[
            b"MAILBOX-ATTACHMENT-BLOB-V1\0" + content
        ] = "3" * 32
        bindings: list[tuple[str, str]] = []

        with tempfile.TemporaryDirectory() as directory:
            report = fetch_prepared_attachments(
                prepared,
                session=FakeAttachmentSession(content),
                vault=vault,
                vault_root=Path(directory),
                parser=lambda path, _mime: path.read_bytes()[-4:],
                clock=lambda: 1_700_000_100,
                content_token_factory=lambda value: (
                    self.assertEqual(value, content) or "e" * 64
                ),
                find_existing_blob=lambda token: (
                    self.assertEqual(token, "e" * 64) or "3" * 32
                ),
                bind_blob=lambda _item, blob_id, token: (
                    bindings.append((blob_id, token))
                    or type("Binding", (), {"status": "duplicate"})()
                ),
            )

        self.assertEqual(vault.records, [])
        self.assertEqual(
            vault.extended_expiries, [prepared.items[0].expires_at_utc]
        )
        self.assertEqual(bindings, [("3" * 32, "e" * 64)])
        self.assertEqual(report.duplicate_blob_count, 1)

    def test_index_blob_id_must_match_vault_dedup_record(self) -> None:
        content = b"\x89PNG\r\n\x1a\nDATA"
        prepared = self._prepared(content=content)
        vault = FakeAttachmentVault()
        vault._payload_records[
            b"MAILBOX-ATTACHMENT-BLOB-V1\0" + content
        ] = "4" * 32
        bindings: list[tuple[str, str]] = []

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                AttachmentScanError, "attachment_persist_failed"
            ):
                fetch_prepared_attachments(
                    prepared, session=FakeAttachmentSession(content), vault=vault,
                    vault_root=Path(directory), parser=lambda _path, _mime: b"ok",
                    clock=lambda: 1_700_000_100,
                    content_token_factory=lambda _content: "e" * 64,
                    find_existing_blob=lambda _token: "3" * 32,
                    bind_blob=lambda _item, blob_id, token: (
                        bindings.append((blob_id, token))
                        or type("Binding", (), {"status": "duplicate"})()
                    ),
                )

        self.assertEqual(bindings, [])

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
                            **FakeAttachmentCorpus().callbacks(),
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
                        **FakeAttachmentCorpus().callbacks(),
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
                    **FakeAttachmentCorpus().callbacks(),
                )

        self.assertEqual(vault.records, [])


if __name__ == "__main__":
    unittest.main()
