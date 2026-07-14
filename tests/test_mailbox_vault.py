"""End-to-end synthetic tests for encrypted record lifecycle semantics."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from backend.mailbox_ingest.errors import VaultError
from backend.mailbox_ingest.models import SecretBuffer
from backend.mailbox_ingest.vault import (
    AtomicCiphertextStore,
    MailboxVault,
    max_expiry_utc,
)
from backend.mailbox_ingest.vault_crypto import VaultCrypto
from backend.mailbox_ingest.vault_index import VaultIndex


class CounterRng:
    def __init__(self) -> None:
        self.counter = 1

    def __call__(self, size: int) -> bytes:
        value = self.counter.to_bytes(size, "big")
        self.counter += 1
        return value


class FailingStore(AtomicCiphertextStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.fail_write = False
        self.fail_unlink = False

    def write(self, relative_path: str, ciphertext: bytes) -> None:
        if self.fail_write:
            raise VaultError("ciphertext_write_failed")
        super().write(relative_path, ciphertext)

    def unlink(self, relative_path: str) -> None:
        if self.fail_unlink:
            raise VaultError("ciphertext_delete_failed")
        super().unlink(relative_path)


class MailboxVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.vault_id = "11111111-2222-4333-8444-555555555555"
        self.now = int(
            datetime(2024, 2, 29, 12, 0, tzinfo=timezone.utc).timestamp()
        )
        self.master = SecretBuffer(b"M" * 32)
        self.crypto = VaultCrypto(
            self.master,
            vault_id=self.vault_id,
            rng=CounterRng(),
            max_plaintext_size=1_024,
        )
        self.index = VaultIndex(
            self.root / "vault-index.sqlite3", vault_id=self.vault_id
        )
        self.index.initialize()
        self.store = FailingStore(self.root)
        self.identifiers = iter(
            (
                "0123456789abcdef0123456789abcdef",
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "11111111111111111111111111111111",
                "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "22222222222222222222222222222222",
                "cccccccccccccccccccccccccccccccc",
                "33333333333333333333333333333333",
                "dddddddddddddddddddddddddddddddd",
                "44444444444444444444444444444444",
                "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                "55555555555555555555555555555555",
                "ffffffffffffffffffffffffffffffff",
            )
        )
        self.vault = MailboxVault(
            self.root,
            vault_id=self.vault_id,
            crypto=self.crypto,
            index=self.index,
            ciphertext_store=self.store,
            clock=lambda: self.now,
            random_identifier=lambda: next(self.identifiers),
        )

    def tearDown(self) -> None:
        self.crypto.close()
        self.master.wipe()
        self.temporary.cleanup()

    def _put(self, plaintext: bytes = b"SYNTHETIC-CONTENT", *, expiry: int | None = None) -> str:
        return self.vault.put_record(
            plaintext,
            expires_at_utc=(expiry if expiry is not None else self.now + 60),
        )

    def test_put_get_uses_random_independent_path_and_no_plaintext_at_rest(self) -> None:
        record_id = self._put()
        metadata = self.index.get_record(record_id)

        plaintext = self.vault.get_record(record_id)

        self.assertEqual(bytes(plaintext), b"SYNTHETIC-CONTENT")
        self.assertIsInstance(plaintext, SecretBuffer)
        plaintext.wipe()
        self.assertNotIn(record_id, metadata.encrypted_relpath)
        ciphertext_path = self.root / metadata.encrypted_relpath
        self.assertTrue(ciphertext_path.exists())
        self.assertNotIn(b"SYNTHETIC-CONTENT", ciphertext_path.read_bytes())
        self.assertNotIn(
            b"SYNTHETIC-CONTENT", (self.root / "vault-index.sqlite3").read_bytes()
        )
        for artifact in self.root.rglob("*"):
            if artifact.is_file():
                self.assertNotIn(b"SYNTHETIC-CONTENT", artifact.read_bytes())
        self.assertFalse(any(path.suffix == ".stage" for path in ciphertext_path.parent.iterdir()))

    def test_caller_expiry_is_capped_at_twenty_four_calendar_months(self) -> None:
        maximum = max_expiry_utc(self.now, months=24)
        expected = int(
            datetime(2026, 2, 28, 12, 0, tzinfo=timezone.utc).timestamp()
        )
        self.assertEqual(maximum, expected)

        self._put(expiry=maximum)
        with self.assertRaisesRegex(VaultError, "expiry_exceeds_retention"):
            self._put(expiry=maximum + 1)
        for invalid in (None, True, 1.5, "2000"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(VaultError, "invalid_expiry"):
                    self.vault.put_record(b"x", expires_at_utc=invalid)  # type: ignore[arg-type]

    def test_expired_at_now_semantics_and_bounded_idempotent_purge(self) -> None:
        expired_ids = [
            self._put(b"expired-a", expiry=self.now - 1),
            self._put(b"expired-b", expiry=self.now),
        ]
        live_id = self._put(b"live", expiry=self.now + 1)

        for record_id in expired_ids:
            with self.subTest(record_id=record_id, operation="get expired"):
                with self.assertRaisesRegex(VaultError, "record_not_found"):
                    self.vault.get_record(record_id)

        first = self.vault.purge_expired(limit=1)
        second = self.vault.purge_expired(limit=1)
        third = self.vault.purge_expired(limit=1)

        self.assertEqual((first.deleted_count, second.deleted_count), (1, 1))
        self.assertEqual(third.deleted_count, 0)
        self.assertTrue(all(self.index.get_record(item) is None for item in expired_ids))
        self.assertIsNotNone(self.index.get_record(live_id))
        with self.assertRaisesRegex(VaultError, "invalid_limit"):
            self.vault.purge_expired(limit=0)

    def test_purge_limit_bounds_pending_reconcile_plus_expired_delete(self) -> None:
        pending_id = self._put(b"pending", expiry=self.now)
        expired_id = self._put(b"expired", expiry=self.now)
        self.index.mark_delete_pending(pending_id)

        first = self.vault.purge_expired(limit=1)

        self.assertEqual(first.deleted_count, 1)
        self.assertEqual(first.remaining_eligible_count, 1)
        self.assertIsNone(self.index.get_record(pending_id))
        self.assertIsNotNone(self.index.get_record(expired_id))

        second = self.vault.purge_expired(limit=1)
        self.assertEqual(second.deleted_count, 1)
        self.assertEqual(second.remaining_eligible_count, 0)

    def test_disk_failure_does_not_create_index_row(self) -> None:
        self.store.fail_write = True

        with self.assertRaisesRegex(VaultError, "ciphertext_write_failed"):
            self._put()

        self.assertEqual(self.index.list_records(), [])

    def test_ciphertext_filesystem_errors_are_fixed_and_path_safe(self) -> None:
        with mock.patch.object(
            Path, "mkdir", side_effect=OSError(f"denied {self.root}")
        ):
            with self.assertRaises(VaultError) as caught:
                self.store.write(
                    "records/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.mvlt",
                    b"ciphertext",
                )

        self.assertEqual(caught.exception.code, "ciphertext_write_failed")
        self.assertNotIn(str(self.root), repr(caught.exception))

    def test_index_failure_leaves_reportable_encrypted_orphan(self) -> None:
        original_add = self.index.add_record

        def fail_add(_record) -> None:
            raise VaultError("index_write_failed")

        self.index.add_record = fail_add  # type: ignore[method-assign]
        try:
            with self.assertRaisesRegex(VaultError, "index_write_failed"):
                self._put()
        finally:
            self.index.add_record = original_add  # type: ignore[method-assign]

        report = self.vault.verify()
        self.assertEqual(report.orphan_count, 1)
        self.assertEqual(report.missing_count, 0)
        self.assertNotIn("records/", repr(report))

    def test_verify_reports_missing_orphan_pending_and_integrity_without_repair(self) -> None:
        good_id = self._put(b"good")
        missing_id = self._put(b"missing")
        corrupt_id = self._put(b"corrupt")
        missing = self.index.get_record(missing_id)
        corrupt = self.index.get_record(corrupt_id)
        self.store.unlink(missing.encrypted_relpath)
        corrupt_path = self.root / corrupt.encrypted_relpath
        corrupt_bytes = bytearray(corrupt_path.read_bytes())
        corrupt_bytes[-1] ^= 1
        corrupt_path.write_bytes(corrupt_bytes)
        orphan = self.root / "records" / "ff" / "ffffffffffffffffffffffffffffffff.mvlt"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_bytes(b"encrypted-orphan")
        self.index.mark_delete_pending(good_id)

        report = self.vault.verify()

        self.assertEqual(report.total_count, 3)
        self.assertEqual(report.missing_count, 1)
        self.assertEqual(report.orphan_count, 1)
        self.assertEqual(report.integrity_failure_count, 1)
        self.assertEqual(report.delete_pending_count, 1)
        self.assertIsNotNone(self.index.get_record(missing_id))
        self.assertTrue(orphan.exists())

    def test_delete_pending_survives_failure_and_reconciles_idempotently(self) -> None:
        record_id = self._put()
        self.store.fail_unlink = True

        with self.assertRaisesRegex(VaultError, "ciphertext_delete_failed"):
            self.vault.delete_record(record_id)
        self.assertEqual(
            self.index.get_record(record_id).lifecycle_state,
            "delete_pending",
        )

        self.store.fail_unlink = False
        first = self.vault.reconcile_delete_pending(limit=10)
        second = self.vault.reconcile_delete_pending(limit=10)
        self.assertEqual((first, second), (1, 0))
        self.assertIsNone(self.index.get_record(record_id))

    def test_mutations_fail_when_exclusive_lock_is_held(self) -> None:
        with self.vault.mutation_lock:
            with self.assertRaisesRegex(VaultError, "vault_busy"):
                self._put()

    def test_revoke_is_explicit_stateful_partial_safe_and_leaves_offline_media(self) -> None:
        offline_recovery = self.root.parent / "synthetic-offline-recovery.key"
        offline_recovery.write_bytes(b"offline-synthetic")
        try:
            with self.assertRaisesRegex(VaultError, "revoke_confirmation_required"):
                self.vault.revoke("REVOKE:wrong", envelope_revoker=lambda: None)

            def fail_revoke() -> None:
                raise RuntimeError(f"path detail {self.root}")

            with self.assertRaisesRegex(VaultError, "revoke_incomplete") as caught:
                self.vault.revoke(
                    f"REVOKE:{self.vault_id}", envelope_revoker=fail_revoke
                )
            self.assertEqual(self.index.get_vault_state(), "revoke_incomplete")
            self.assertNotIn(str(self.root), repr(caught.exception))
            self.assertTrue(offline_recovery.exists())

            result = self.vault.revoke(
                f"REVOKE:{self.vault_id}", envelope_revoker=lambda: None
            )
            self.assertEqual(result.state, "revoked")
            self.assertEqual(self.index.get_vault_state(), "revoked")
            self.assertTrue(offline_recovery.exists())
            self.assertFalse(result.secure_erase_claimed)
            with self.assertRaisesRegex(VaultError, "vault_revoked"):
                self._put()
        finally:
            offline_recovery.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
