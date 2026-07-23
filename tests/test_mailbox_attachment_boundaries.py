"""Authorization and source-envelope boundaries for governed attachments."""

from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.mailbox_ingest.attachment_manifest import (
    AttachmentScanError,
    PreparedAttachment,
    parse_reviewed_manifest,
    prepare_attachments,
)
from backend.mailbox_ingest.attachment_scan import _persist_blob
from backend.mailbox_ingest.bodystructure import AttachmentMetadata
from backend.mailbox_ingest.models import PutRecordResult, SecretBuffer
from backend.mailbox_ingest.scan_record import encode_scan_record


_SCOPE = "a" * 64
_FINGERPRINT = "b" * 64
_SOURCE_ID = "1" * 32
_CANDIDATE_ID = "2" * 32
_BLOB_ID = "3" * 32


def _manifest():
    return parse_reviewed_manifest(
        {
            "schema_version": 1,
            "scope": _SCOPE,
            "fingerprint": _FINGERPRINT,
            "issued_at_utc": 1_700_000_000,
            "expires_at_utc": 1_700_003_600,
            "approval_id": "c" * 32,
            "selections": [{
                "source_record_id": _SOURCE_ID,
                "candidate_id": _CANDIDATE_ID,
                "expected_size": 12,
                "mime_type": "image/png",
                "business_approved": True,
                "privacy_approved": True,
            }],
        },
        expected_scope=_SCOPE,
        expected_fingerprint=_FINGERPRINT,
        now_utc=1_700_000_100,
    )


def _v2_source_record() -> bytes:
    attachment = AttachmentMetadata(
        "2", "image/png", 12, "synthetic-name.png"
    )
    return encode_scan_record(
        scope=_SCOPE,
        fingerprint=_FINGERPRINT,
        opaque_folder_id="d" * 64,
        mailbox="SYNTHETIC-INBOX",
        uidvalidity=77,
        uid=9,
        internal_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        expires_at_utc=1_800_000_000,
        header=b"synthetic header",
        bodies=(b"synthetic body",),
        learning_projection="Synthetic governed learning projection.",
        attachments=(attachment,),
        candidate_id_factory=lambda: _CANDIDATE_ID,
    )


class AttachmentSourceEnvelopeTests(unittest.TestCase):
    def test_governed_v2_source_record_can_prepare_reviewed_attachment(
        self,
    ) -> None:
        prepared = prepare_attachments(
            _manifest(),
            read_source_record=lambda _record_id: SecretBuffer(
                _v2_source_record()
            ),
            source_is_paired=lambda _record_id: True,
        )

        self.assertEqual(len(prepared.items), 1)
        self.assertEqual(prepared.items[0].mime_type, "image/png")

    def test_governed_v2_source_record_rejects_unknown_fields(self) -> None:
        payload = json.loads(_v2_source_record())
        payload["unexpected"] = "forbidden"

        with self.assertRaisesRegex(
            AttachmentScanError, "attachment_source_invalid"
        ):
            prepare_attachments(
                _manifest(),
                read_source_record=lambda _record_id: SecretBuffer(
                    json.dumps(payload).encode("utf-8")
                ),
                source_is_paired=lambda _record_id: True,
            )


class _DuplicateVault:
    def __init__(self) -> None:
        self.extend_flags: list[bool] = []

    @contextmanager
    def coordinated_mutation(self):
        yield

    def put_record_if_absent(
        self,
        _value: bytes,
        *,
        expires_at_utc: int,
        extend_expiry_on_duplicate: bool = False,
    ) -> PutRecordResult:
        self.extend_flags.append(extend_expiry_on_duplicate)
        return PutRecordResult(_BLOB_ID, False)


class AttachmentRetentionTests(unittest.TestCase):
    def test_failed_binding_does_not_extend_duplicate_blob_retention(
        self,
    ) -> None:
        vault = _DuplicateVault()
        item = PreparedAttachment(
            _SOURCE_ID,
            _CANDIDATE_ID,
            "SYNTHETIC-INBOX",
            9,
            77,
            "2",
            "image/png",
            12,
            1_800_000_000,
        )

        with self.assertRaisesRegex(
            AttachmentScanError, "attachment_persist_failed"
        ):
            _persist_blob(
                item,
                b"synthetic attachment",
                vault,
                lambda _content: "e" * 64,
                lambda _token: _BLOB_ID,
                lambda _item, _blob_id, _token: (
                    (_ for _ in ()).throw(
                        RuntimeError("synthetic pair expired")
                    )
                ),
            )

        self.assertEqual(vault.extend_flags, [False])

    def test_recovered_intent_extends_only_after_successful_binding(self) -> None:
        class RecoveredIntentVault(_DuplicateVault):
            def put_record_if_absent(
                self,
                _value: bytes,
                *,
                expires_at_utc: int,
                extend_expiry_on_duplicate: bool = False,
            ) -> PutRecordResult:
                self.extend_flags.append(extend_expiry_on_duplicate)
                return PutRecordResult(
                    _BLOB_ID,
                    len(self.extend_flags) == 1,
                )

        vault = RecoveredIntentVault()
        item = PreparedAttachment(
            _SOURCE_ID,
            _CANDIDATE_ID,
            "SYNTHETIC-INBOX",
            9,
            77,
            "2",
            "image/png",
            12,
            1_800_000_000,
        )

        status = _persist_blob(
            item,
            b"synthetic attachment",
            vault,
            lambda _content: "e" * 64,
            lambda _token: None,
            lambda _item, _blob_id, _token: type(
                "Binding", (), {"status": "new"}
            )(),
        )

        self.assertEqual(status, "new")
        self.assertEqual(vault.extend_flags, [False, True])


if __name__ == "__main__":
    unittest.main()
