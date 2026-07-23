"""Mode-specific staged-record release tests over the public source seam."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.mailbox_ingest.knowledge_stage_source import (
    open_evaluation_stage_source,
    open_knowledge_stage_source,
)
from backend.mailbox_ingest import stage_record_release
from backend.mailbox_ingest.errors import VaultError
from backend.mailbox_ingest.models import SecretBuffer
from backend.mailbox_ingest.scan_record import encode_scan_record


class _OpenedVault:
    def __init__(
        self, record_id: str, payload: bytes, *, paired: bool | None,
    ) -> None:
        self.identity = type("Identity", (), {"vault_id": "v" * 32})()
        self._record_id = record_id
        self._payload = payload
        self._paired = paired
        self.record_reads = 0
        self.pair_checks = 0
        self.vault = type("Vault", (), {"get_record": self._get_record})()
        self.corpus_index = type(
            "CorpusIndex", (), {"belongs_to_pair": self._belongs_to_pair}
        )()
        self.closed = False

    def require_authorization_scope(
        self, _authorization: str, _account: str,
    ) -> object:
        return type("Scope", (), {"opaque_scope_id": "a" * 64})()

    def _get_record(self, selected: str) -> SecretBuffer | None:
        self.record_reads += 1
        return (
            SecretBuffer(self._payload)
            if selected == self._record_id
            else None
        )

    def _belongs_to_pair(self, _selected: str) -> bool:
        self.pair_checks += 1
        if self._paired is None:
            raise AssertionError("evaluation release required a pair")
        return self._paired

    def close(self) -> None:
        self.closed = True


class MailboxStageRecordReleaseTests(unittest.TestCase):
    def test_evaluation_release_accepts_governed_v2_record_and_uses_raw_text(
        self,
    ) -> None:
        record_id = "1" * 32
        payload = encode_scan_record(
            scope="a" * 64,
            fingerprint="b" * 64,
            opaque_folder_id="c" * 64,
            mailbox="INBOX",
            uidvalidity=1,
            uid=1,
            internal_date=datetime(2025, 7, 15, tzinfo=timezone.utc),
            expires_at_utc=1_800_000_000,
            header=(
                b"From: Synthetic Partner <partner@vendor.example>\r\n"
                b"To: Synthetic User <user@example.test>\r\n"
                b"Message-ID: <synthetic@vendor.example>\r\n\r\n"
            ),
            bodies=(b"Raw synthetic evaluation body.",),
            learning_projection="Clean governed learning projection.",
            attachments=(),
            candidate_id_factory=lambda: "d" * 32,
        )
        opened = _OpenedVault(record_id, payload, paired=None)
        source = open_evaluation_stage_source(
            Path("E:/synthetic-vault"),
            authorization_id="AUTH-EVAL-1",
            account="user@example.test",
            expected_vault_id="v" * 32,
            expected_scope="a" * 64,
            window_start=datetime(2024, 7, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 7, 15, tzinfo=timezone.utc),
            expected_fingerprint="b" * 64,
            project_root=Path("C:/synthetic-project"),
            validate_existing=lambda *_args: object(),
            dpapi_factory=lambda: object(),
            opener=lambda *_args, **_kwargs: opened,
            clock=lambda: 1_752_500_000,
        )

        with source, source.read_one_record(record_id) as record:
            self.assertIn("Raw synthetic evaluation body.", record.text)
            self.assertNotIn("Clean governed learning projection.", record.text)
        self.assertEqual(opened.pair_checks, 0)
        self.assertTrue(opened.closed)

    def test_knowledge_opener_cannot_disable_the_paired_record_gate(self) -> None:
        record_id = "2" * 32
        payload = encode_scan_record(
            scope="a" * 64,
            fingerprint="b" * 64,
            opaque_folder_id="c" * 64,
            mailbox="INBOX",
            uidvalidity=1,
            uid=2,
            internal_date=datetime(2025, 7, 15, tzinfo=timezone.utc),
            expires_at_utc=1_800_000_000,
            header=b"Message-ID: <synthetic-2@vendor.example>\r\n\r\n",
            bodies=(b"Raw unpaired body.",),
            learning_projection="Clean unpaired projection.",
            attachments=(),
            candidate_id_factory=lambda: "d" * 32,
        )
        opened = _OpenedVault(record_id, payload, paired=False)
        source = open_knowledge_stage_source(
            Path("E:/synthetic-vault"),
            authorization_id="AUTH-KNOWLEDGE-1",
            account="user@example.test",
            expected_vault_id="v" * 32,
            expected_scope="a" * 64,
            window_start=datetime(2024, 7, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 7, 15, tzinfo=timezone.utc),
            project_root=Path("C:/synthetic-project"),
            validate_existing=lambda *_args: object(),
            dpapi_factory=lambda: object(),
            opener=lambda *_args, **_kwargs: opened,
            clock=lambda: 1_752_500_000,
            retain_evidence=False,
        )

        with source, self.assertRaises(VaultError):
            with source.read_one_record(record_id):
                self.fail("unpaired knowledge record released plaintext")
        self.assertEqual(opened.pair_checks, 1)
        self.assertEqual(opened.record_reads, 0)

    def test_evaluation_opener_rejects_missing_fingerprint_before_open(
        self,
    ) -> None:
        opened = False

        def opener(*_args: object, **_kwargs: object) -> object:
            nonlocal opened
            opened = True
            raise AssertionError("missing fingerprint opened the vault")

        with self.assertRaises(VaultError):
            open_evaluation_stage_source(
                Path("E:/synthetic-vault"),
                authorization_id="AUTH-EVAL-1",
                account="user@example.test",
                expected_vault_id="v" * 32,
                expected_scope="a" * 64,
                expected_fingerprint=None,  # type: ignore[arg-type]
                window_start=datetime(2024, 7, 15, tzinfo=timezone.utc),
                window_end=datetime(2026, 7, 15, tzinfo=timezone.utc),
                project_root=Path("C:/synthetic-project"),
                validate_existing=lambda *_args: object(),
                dpapi_factory=lambda: object(),
                opener=opener,
                clock=lambda: 1_752_500_000,
            )
        self.assertFalse(opened)

    def test_evaluation_rejects_malformed_governed_v2_projection(self) -> None:
        record_id = "3" * 32
        valid = encode_scan_record(
            scope="a" * 64,
            fingerprint="b" * 64,
            opaque_folder_id="c" * 64,
            mailbox="INBOX",
            uidvalidity=1,
            uid=3,
            internal_date=datetime(2025, 7, 15, tzinfo=timezone.utc),
            expires_at_utc=1_800_000_000,
            header=b"Message-ID: <synthetic-3@vendor.example>\r\n\r\n",
            bodies=(b"Raw evaluation body.",),
            learning_projection="Valid projection.",
            attachments=(),
            candidate_id_factory=lambda: "d" * 32,
        )
        value = json.loads(valid)
        value["learning_projection"] = ""
        payload = json.dumps(value, separators=(",", ":")).encode("ascii")
        opened = _OpenedVault(record_id, payload, paired=None)
        source = open_evaluation_stage_source(
            Path("E:/synthetic-vault"),
            authorization_id="AUTH-EVAL-1",
            account="user@example.test",
            expected_vault_id="v" * 32,
            expected_scope="a" * 64,
            expected_fingerprint="b" * 64,
            window_start=datetime(2024, 7, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 7, 15, tzinfo=timezone.utc),
            project_root=Path("C:/synthetic-project"),
            validate_existing=lambda *_args: object(),
            dpapi_factory=lambda: object(),
            opener=lambda *_args, **_kwargs: opened,
            clock=lambda: 1_752_500_000,
        )

        with source, self.assertRaises(VaultError):
            with source.read_one_record(record_id):
                self.fail("malformed v2 record released plaintext")

    def test_release_policy_singletons_are_not_mutable(self) -> None:
        release = stage_record_release._KNOWLEDGE_RELEASE

        with self.assertRaises(AttributeError):
            release.requires_pair = False

    def test_evaluation_rejects_tampered_common_envelope_fields(self) -> None:
        valid = json.loads(encode_scan_record(
            scope="a" * 64,
            fingerprint="b" * 64,
            opaque_folder_id="c" * 64,
            mailbox="INBOX",
            uidvalidity=1,
            uid=4,
            internal_date=datetime(2025, 7, 15, tzinfo=timezone.utc),
            expires_at_utc=1_800_000_000,
            header=b"Message-ID: <synthetic-4@vendor.example>\r\n\r\n",
            bodies=(b"Raw evaluation body.",),
            learning_projection="Valid projection.",
            attachments=(),
            candidate_id_factory=lambda: "d" * 32,
        ))
        mutations = {
            "boolean uid": lambda value: value.update(uid=True),
            "string expiry": lambda value: value.update(
                expires_at_utc="not-an-int"
            ),
            "unvalidated attachment": lambda value: value.update(
                attachments=[{"unexpected": "forbidden"}]
            ),
        }
        for offset, (label, mutate) in enumerate(mutations.items(), start=4):
            with self.subTest(label=label):
                value = json.loads(json.dumps(valid))
                mutate(value)
                payload = json.dumps(value, separators=(",", ":")).encode(
                    "ascii"
                )
                record_id = f"{offset:032x}"
                opened = _OpenedVault(record_id, payload, paired=None)
                source = open_evaluation_stage_source(
                    Path("E:/synthetic-vault"),
                    authorization_id="AUTH-EVAL-1",
                    account="user@example.test",
                    expected_vault_id="v" * 32,
                    expected_scope="a" * 64,
                    expected_fingerprint="b" * 64,
                    window_start=datetime(
                        2024, 7, 15, tzinfo=timezone.utc
                    ),
                    window_end=datetime(
                        2026, 7, 15, tzinfo=timezone.utc
                    ),
                    project_root=Path("C:/synthetic-project"),
                    validate_existing=lambda *_args: object(),
                    dpapi_factory=lambda: object(),
                    opener=lambda *_args, **_kwargs: opened,
                    clock=lambda: 1_752_500_000,
                )

                with source, self.assertRaises(VaultError) as caught:
                    with source.read_one_record(record_id):
                        self.fail("tampered v2 record released plaintext")
                self.assertEqual(caught.exception.code, "internal_error")


if __name__ == "__main__":
    unittest.main()
