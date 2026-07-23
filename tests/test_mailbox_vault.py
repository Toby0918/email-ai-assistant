"""End-to-end synthetic tests for encrypted record lifecycle semantics."""

from __future__ import annotations

import tempfile
import threading
import unittest
import sqlite3
from contextlib import closing
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
        self.crash_after_write = False
        self.fail_unlink = False

    def write(self, relative_path: str, ciphertext: bytes) -> None:
        if self.fail_write:
            raise VaultError("ciphertext_write_failed")
        super().write(relative_path, ciphertext)
        if self.crash_after_write:
            self.crash_after_write = False
            raise RuntimeError("synthetic crash after ciphertext commit")

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

    def _reopen(self, identifiers: tuple[str, ...]) -> None:
        self.crypto.close()
        self.crypto = VaultCrypto(
            self.master,
            vault_id=self.vault_id,
            rng=CounterRng(),
            max_plaintext_size=1_024,
        )
        self.index = VaultIndex(
            self.root / "vault-index.sqlite3", vault_id=self.vault_id,
        )
        self.index.validate()
        self.store = FailingStore(self.root)
        self.identifiers = iter(identifiers)
        self.vault = MailboxVault(
            self.root,
            vault_id=self.vault_id,
            crypto=self.crypto,
            index=self.index,
            ciphertext_store=self.store,
            clock=lambda: self.now,
            random_identifier=lambda: next(self.identifiers),
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

    def test_planned_purge_is_exact_and_prioritizes_delete_pending(self) -> None:
        pending_id = self._put(b"pending-plan", expiry=self.now + 1)
        expired_id = self._put(b"expired-plan", expiry=self.now)
        live_id = self._put(b"live-plan", expiry=self.now + 1)
        self.index.mark_delete_pending(pending_id)

        first_plan = self.vault.plan_expired_purge(limit=1)
        first = self.vault.purge_planned(first_plan)
        second_plan = self.vault.plan_expired_purge(limit=1)
        second = self.vault.purge_planned(second_plan)

        self.assertEqual(first_plan, (pending_id,))
        self.assertEqual(second_plan, (expired_id,))
        self.assertEqual((first.deleted_count, second.deleted_count), (1, 1))
        self.assertIsNotNone(self.index.get_record(live_id))

    def test_corpus_reference_check_requires_active_metadata_and_ciphertext(self) -> None:
        active_id = self._put(b"active-reference")
        pending_id = self._put(b"pending-reference")
        missing_ciphertext_id = self._put(b"missing-reference")
        missing = self.index.get_record(missing_ciphertext_id)
        self.index.mark_delete_pending(pending_id)
        self.store.unlink(missing.encrypted_relpath)

        dangling = self.vault.count_inactive_or_missing_records((
            active_id, pending_id, missing_ciphertext_id, "f" * 32,
        ))

        self.assertEqual(dangling, 2)
        self.assertEqual(self.vault.verify().missing_count, 1)

    def test_lifecycle_id_boundaries_allow_full_purge_and_large_verify(self) -> None:
        purge_ids = tuple(f"{position:032x}" for position in range(1_000))
        report = self.vault.purge_planned(purge_ids)

        self.assertEqual(report.deleted_count, 0)
        with self.assertRaisesRegex(VaultError, "invalid_record_id"):
            self.vault.purge_planned(
                tuple(f"{position:032x}" for position in range(1_001))
            )
        verify_ids = tuple(f"{position:032x}" for position in range(1_200))
        self.assertEqual(
            self.vault.count_inactive_or_missing_records(verify_ids), 1_200,
        )

    def test_planned_purge_rejects_a_live_record(self) -> None:
        live_id = self._put(b"not-expired")

        with self.assertRaisesRegex(VaultError, "invalid_expiry"):
            self.vault.purge_planned((live_id,))

        self.assertIsNotNone(self.index.get_record(live_id))

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

    def test_ciphertext_commit_is_write_pending_instead_of_orphaned(self) -> None:
        self.store.crash_after_write = True
        with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            self.vault.put_record_if_absent(
                b"WRITE-PENDING-SYNTHETIC", expires_at_utc=self.now + 60
            )
        report = self.vault.verify()
        self.assertEqual(report.total_count, 0)
        self.assertEqual(report.write_pending_count, 1)
        self.assertEqual(report.orphan_count, 0)
        self.assertEqual(report.missing_count, 0)
        self.assertNotIn("records/", repr(report))

    def test_close_reopen_retry_activates_original_write_intent(self) -> None:
        first_created = self.now
        first_expiry = self.now + 60
        self.store.crash_after_write = True
        with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            self.vault.put_record_if_absent(
                b"CRASH-SAFE-SYNTHETIC", expires_at_utc=first_expiry,
            )
        pending = self.index.list_write_intents()[0]
        pending_mac = pending.metadata_mac
        self.assertEqual(len(pending_mac), 32)
        self.assertNotIn(pending_mac.hex(), repr(pending))

        self.now += 10
        self._reopen(("9" * 32, "8" * 32))
        retried = self.vault.put_record_if_absent(
            b"CRASH-SAFE-SYNTHETIC",
            expires_at_utc=first_expiry + 60,
            extend_expiry_on_duplicate=True,
        )
        metadata = self.index.get_record(retried.record_id)
        report = self.vault.verify()

        self.assertTrue(retried.created)
        self.assertEqual(
            retried.record_id, "0123456789abcdef0123456789abcdef",
        )
        self.assertEqual(metadata.created_at_utc, first_created)
        self.assertEqual(metadata.expires_at_utc, first_expiry)
        self.assertEqual(len(metadata.metadata_mac), 32)
        self.assertNotEqual(metadata.metadata_mac, pending_mac)
        self.assertNotIn(metadata.metadata_mac.hex(), repr(metadata))
        self.assertEqual(report.total_count, 1)
        self.assertEqual(report.write_pending_count, 0)
        self.assertEqual(report.orphan_count, 0)
        self.assertEqual(len(self.store.iter_paths()), 1)
        recovered = self.vault.get_record(retried.record_id)
        self.addCleanup(recovered.wipe)
        self.assertEqual(bytes(recovered), b"CRASH-SAFE-SYNTHETIC")

    def test_close_reopen_retry_atomically_constrains_pending_expiry(self) -> None:
        original_expiry = self.now + 120
        requested_expiry = self.now + 60
        self.store.crash_after_write = True
        with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            self.vault.put_record_if_absent(
                b"EARLIER-RETRY-SYNTHETIC", expires_at_utc=original_expiry,
            )

        self.now += 10
        self._reopen(("9" * 32, "8" * 32))
        retried = self.vault.put_record_if_absent(
            b"EARLIER-RETRY-SYNTHETIC", expires_at_utc=requested_expiry,
        )

        metadata = self.index.get_record(retried.record_id)
        self.assertEqual(metadata.expires_at_utc, requested_expiry)
        self.assertEqual(metadata.created_at_utc, self.now - 10)
        self.assertEqual(self.index.list_write_intents(), [])

    def test_duplicate_expiry_extension_is_explicit_strict_and_monotonic(self) -> None:
        first = self.vault.put_record_if_absent(
            b"RAW-BYTES", expires_at_utc=self.now + 60,
        )
        second = self.vault.put_record_if_absent(
            b"RAW-BYTES", expires_at_utc=self.now + 90,
        )
        third = self.vault.put_record_if_absent(
            b"RAW-BYTES",
            expires_at_utc=self.now + 120,
            extend_expiry_on_duplicate=True,
        )
        fourth = self.vault.put_record_if_absent(
            b"RAW-BYTES",
            expires_at_utc=self.now + 100,
            extend_expiry_on_duplicate=True,
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertFalse(third.created)
        self.assertFalse(fourth.created)
        self.assertEqual(
            {first.record_id, second.record_id, third.record_id, fourth.record_id},
            {first.record_id},
        )
        self.assertEqual(
            self.index.get_record(first.record_id).expires_at_utc,
            self.now + 120,
        )
        for invalid in (None, 0, 1, "yes"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(VaultError, "invalid_expiry"):
                    self.vault.put_record_if_absent(
                        b"RAW-BYTES",
                        expires_at_utc=self.now + 180,
                        extend_expiry_on_duplicate=invalid,  # type: ignore[arg-type]
                    )

    def test_constrain_record_expiry_only_reduces_active_record(self) -> None:
        record_id = self._put(expiry=self.now + 120)

        self.vault.constrain_record_expiry(record_id, self.now + 60)
        self.vault.constrain_record_expiry(record_id, self.now + 90)

        self.assertEqual(
            self.index.get_record(record_id).expires_at_utc, self.now + 60,
        )
        self.vault.constrain_record_expiry(record_id, self.now + 30)
        self.assertEqual(
            self.index.get_record(record_id).expires_at_utc, self.now + 30,
        )
        self.index.mark_delete_pending(record_id)
        with self.assertRaisesRegex(VaultError, "record_not_found"):
            self.vault.constrain_record_expiry(record_id, self.now + 30)
        for invalid in (None, True, 1.5, "100"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(VaultError, "invalid_expiry"):
                    self.vault.constrain_record_expiry(
                        record_id, invalid,  # type: ignore[arg-type]
                    )

    def test_tampered_write_pending_ciphertext_fails_closed(self) -> None:
        self.store.crash_after_write = True
        with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            self.vault.put_record_if_absent(
                b"TAMPERED-PENDING", expires_at_utc=self.now + 60,
            )
        intent = self.index.list_write_intents()[0]
        path = self.root / intent.encrypted_relpath
        frame = bytearray(path.read_bytes())
        frame[-1] ^= 1
        path.write_bytes(frame)
        self._reopen(("9" * 32, "8" * 32))

        with self.assertRaisesRegex(VaultError, "record_authentication_failed"):
            self.vault.put_record_if_absent(
                b"TAMPERED-PENDING", expires_at_utc=self.now + 60,
            )

        report = self.vault.verify()
        self.assertEqual(report.total_count, 0)
        self.assertEqual(report.write_pending_count, 1)
        self.assertEqual(report.orphan_count, 0)
        self.assertEqual(len(self.store.iter_paths()), 1)

    def test_expired_write_pending_is_purged_within_shared_limit(self) -> None:
        self.store.crash_after_write = True
        with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            self.vault.put_record_if_absent(
                b"EXPIRED-PENDING", expires_at_utc=self.now,
            )

        report = self.vault.purge_expired(limit=1)

        self.assertEqual(report.deleted_count, 1)
        self.assertEqual(report.remaining_eligible_count, 0)
        self.assertEqual(self.index.list_write_intents(), [])
        self.assertEqual(self.store.iter_paths(), set())

    def test_tampered_pending_expiry_cannot_escape_purge_planning(self) -> None:
        self.store.crash_after_write = True
        with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            self.vault.put_record_if_absent(
                b"PENDING-EXPIRY-TAMPER", expires_at_utc=self.now,
            )
        with closing(sqlite3.connect(self.root / "vault-index.sqlite3")) as connection:
            connection.execute(
                "UPDATE write_intents SET expires_at_utc=?",
                (self.now + 3_600,),
            )
            connection.commit()

        with self.assertRaisesRegex(VaultError, "record_authentication_failed"):
            self.vault.plan_expired_purge(limit=1)

    def test_tampered_active_expiry_fails_closed_on_read_and_verify(self) -> None:
        record_id = self._put(b"ACTIVE-EXPIRY-TAMPER", expiry=self.now + 60)
        with closing(sqlite3.connect(self.root / "vault-index.sqlite3")) as connection:
            connection.execute(
                "UPDATE records SET expires_at_utc=? WHERE record_id=?",
                (self.now + 3_600, record_id),
            )
            connection.commit()

        for operation in (
            lambda: self.vault.get_record(record_id),
            self.vault.verify,
        ):
            with self.subTest(operation=repr(operation)):
                with self.assertRaisesRegex(
                    VaultError, "record_authentication_failed",
                ):
                    operation()

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

    def test_verify_detects_index_dedup_hmac_tamper(self) -> None:
        record_id = self._put()
        with closing(sqlite3.connect(self.root / "vault-index.sqlite3")) as connection:
            connection.execute(
                "UPDATE records SET dedup_hmac=? WHERE record_id=?",
                (b"X" * 32, record_id),
            )
            connection.commit()

        with self.assertRaisesRegex(VaultError, "record_authentication_failed"):
            self.vault.verify()

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

    def test_coordinated_mutation_keeps_one_lock_across_nested_vault_calls(self) -> None:
        lock_path = self.root / ".mutation.lock"

        with self.vault.coordinated_mutation():
            self.assertTrue(lock_path.exists())
            record_id = self._put(b"COORDINATED-NESTED")
            with self.vault.coordinated_mutation():
                self.assertTrue(lock_path.exists())
                self.vault.constrain_record_expiry(record_id, self.now + 30)
            self.assertTrue(lock_path.exists())

        self.assertFalse(lock_path.exists())
        self.assertEqual(
            self.index.get_record(record_id).expires_at_utc, self.now + 30,
        )

    def test_coordinated_mutation_rejects_other_instance_and_thread(self) -> None:
        other = MailboxVault(
            self.root,
            vault_id=self.vault_id,
            crypto=self.crypto,
            index=self.index,
            ciphertext_store=self.store,
            clock=lambda: self.now,
        )
        thread_errors: list[str] = []

        def compete() -> None:
            try:
                with self.vault.coordinated_mutation():
                    self.fail("other thread acquired coordinated mutation")
            except VaultError as error:
                thread_errors.append(error.code)

        with self.vault.coordinated_mutation():
            contender = threading.Thread(target=compete)
            contender.start()
            contender.join(timeout=5)
            self.assertFalse(contender.is_alive())
            with self.assertRaisesRegex(VaultError, "vault_busy"):
                with other.coordinated_mutation():
                    self.fail("other instance acquired coordinated mutation")

        self.assertEqual(thread_errors, ["vault_busy"])

    def test_coordinated_mutation_releases_lock_after_exception(self) -> None:
        lock_path = self.root / ".mutation.lock"

        with self.assertRaisesRegex(RuntimeError, "synthetic coordinated failure"):
            with self.vault.coordinated_mutation():
                raise RuntimeError("synthetic coordinated failure")

        self.assertFalse(lock_path.exists())
        with self.vault.coordinated_mutation():
            self.assertTrue(lock_path.exists())
        self.assertFalse(lock_path.exists())

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

    def test_revoke_wipes_crypto_when_final_revoked_state_write_fails(self) -> None:
        original_set_state = self.index.set_vault_state

        def fail_revoked(state: str) -> None:
            if state == "revoked":
                raise VaultError("index_write_failed")
            original_set_state(state)

        self.index.set_vault_state = fail_revoked  # type: ignore[method-assign]
        try:
            with self.assertRaisesRegex(VaultError, "index_write_failed"):
                self.vault.revoke(
                    f"REVOKE:{self.vault_id}", envelope_revoker=lambda: None
                )
        finally:
            self.index.set_vault_state = original_set_state  # type: ignore[method-assign]

        self.assertEqual(self.index.get_vault_state(), "revoke_incomplete")
        self.assertEqual(bytes(self.crypto._record_encryption_key), bytes(32))
        with self.assertRaisesRegex(VaultError, "crypto_closed"):
            self.crypto.encrypt("0" * 32, b"synthetic")

    def test_revoke_keeps_primary_error_when_incomplete_state_write_fails(self) -> None:
        original_set_state = self.index.set_vault_state

        def fail_incomplete(state: str) -> None:
            if state == "revoke_incomplete":
                raise VaultError("index_write_failed")
            original_set_state(state)

        def fail_revoke() -> None:
            raise RuntimeError("synthetic envelope failure")

        self.index.set_vault_state = fail_incomplete  # type: ignore[method-assign]
        try:
            with self.assertRaisesRegex(VaultError, "revoke_incomplete"):
                self.vault.revoke(
                    f"REVOKE:{self.vault_id}", envelope_revoker=fail_revoke
                )
        finally:
            self.index.set_vault_state = original_set_state  # type: ignore[method-assign]

        self.assertEqual(self.index.get_vault_state(), "revoking")
        self.assertEqual(bytes(self.crypto._dedup_hmac_key), bytes(32))
        with self.assertRaisesRegex(VaultError, "crypto_closed"):
            self.crypto.encrypt("0" * 32, b"synthetic")


if __name__ == "__main__":
    unittest.main()
