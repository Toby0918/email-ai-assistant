"""Metadata-only SQLite index tests for the encrypted mailbox vault."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest import mock

from backend.mailbox_ingest.errors import VaultError
from backend.mailbox_ingest.models import SecretBuffer, VaultRecord
from backend.mailbox_ingest.vault import MailboxVault
from backend.mailbox_ingest.vault_crypto import VaultCrypto
from backend.mailbox_ingest.vault_index import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    VaultIndex,
    VaultMutationLock,
)


RECORD_COLUMNS = (
    "record_id",
    "encrypted_relpath",
    "dedup_hmac",
    "created_at_utc",
    "expires_at_utc",
    "ciphertext_size",
    "format_version",
    "key_version",
    "lifecycle_state",
    "metadata_mac",
)
STATE_COLUMNS = ("singleton", "vault_id", "lifecycle_state")
INTENT_COLUMNS = RECORD_COLUMNS[:-2] + ("metadata_mac",)


def _record(
    record_id: str = "0123456789abcdef0123456789abcdef",
    *,
    relpath: str = "records/ab/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.mvlt",
    expires_at: int = 2_000,
    state: str = "active",
) -> VaultRecord:
    return VaultRecord(
        record_id=record_id,
        encrypted_relpath=relpath,
        dedup_hmac=b"H" * 32,
        created_at_utc=1_000,
        expires_at_utc=expires_at,
        ciphertext_size=128,
        format_version=1,
        key_version=1,
        lifecycle_state=state,
    )


class VaultIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / "vault-index.sqlite3"
        self.vault_id = "11111111-2222-4333-8444-555555555555"
        self.index = VaultIndex(self.path, vault_id=self.vault_id)
        self.index.initialize()
        self.master = SecretBuffer(b"M" * 32)
        self.crypto = VaultCrypto(
            self.master,
            vault_id=self.vault_id,
            rng=lambda size: b"N" * size,
            max_plaintext_size=1_024,
        )
        self.index.bind_metadata_authenticator(self.crypto)

    def tearDown(self) -> None:
        self.crypto.close()
        self.master.wipe()
        self.temporary.cleanup()

    def test_exact_schema_and_durable_local_pragmas(self) -> None:
        with closing(self.index._connect()) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            records = tuple(
                row[1] for row in connection.execute("PRAGMA table_info(records)")
            )
            state = tuple(
                row[1]
                for row in connection.execute("PRAGMA table_info(vault_state)")
            )
            intents = tuple(
                row[1]
                for row in connection.execute("PRAGMA table_info(write_intents)")
            )
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
            temp_store = connection.execute("PRAGMA temp_store").fetchone()[0]

        self.assertEqual(tables, {"records", "write_intents", "vault_state"})
        self.assertEqual(records, RECORD_COLUMNS)
        self.assertEqual(intents, INTENT_COLUMNS)
        self.assertEqual(state, STATE_COLUMNS)
        self.assertEqual(application_id, APPLICATION_ID)
        self.assertEqual(user_version, SCHEMA_VERSION)
        self.assertEqual(journal_mode.lower(), "delete")
        self.assertEqual(synchronous, 2)
        self.assertEqual(temp_store, 2)

    def test_older_schema_fails_closed_without_implicit_migration(self) -> None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("DROP TABLE write_intents")
            connection.execute("PRAGMA user_version=1")
            connection.commit()

        with self.assertRaisesRegex(VaultError, "index_schema_invalid"):
            self.index.initialize()

        with closing(sqlite3.connect(self.path)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(tables, {"records", "vault_state"})
        self.assertEqual(user_version, 1)

    def test_schema_rejects_removed_unique_constraint(self) -> None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "ALTER TABLE write_intents RENAME TO old_write_intents"
            )
            connection.execute("""
                CREATE TABLE write_intents (
                    record_id TEXT PRIMARY KEY,
                    encrypted_relpath TEXT NOT NULL UNIQUE,
                    dedup_hmac BLOB NOT NULL,
                    created_at_utc INTEGER NOT NULL,
                    expires_at_utc INTEGER NOT NULL,
                    ciphertext_size INTEGER NOT NULL,
                    format_version INTEGER NOT NULL,
                    key_version INTEGER NOT NULL,
                    metadata_mac BLOB NOT NULL
                )
            """)
            connection.execute("DROP TABLE old_write_intents")
            connection.commit()

        with self.assertRaisesRegex(VaultError, "index_schema_invalid"):
            self.index.validate()

    def test_schema_rejects_injected_trigger(self) -> None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "CREATE TRIGGER injected_metadata_trigger "
                "AFTER INSERT ON records BEGIN SELECT 1; END"
            )
            connection.commit()

        with self.assertRaisesRegex(VaultError, "index_schema_invalid"):
            self.index.validate()

    def test_schema_rejects_unexpected_view_and_explicit_index(self) -> None:
        objects = (
            (
                "view",
                "CREATE VIEW injected_metadata_view AS SELECT record_id FROM records",
                "DROP VIEW injected_metadata_view",
            ),
            (
                "index",
                "CREATE INDEX injected_metadata_index ON records(expires_at_utc)",
                "DROP INDEX injected_metadata_index",
            ),
        )
        for label, create_sql, drop_sql in objects:
            with self.subTest(label=label):
                with closing(sqlite3.connect(self.path)) as connection:
                    connection.execute(create_sql)
                    connection.commit()
                with self.assertRaisesRegex(VaultError, "index_schema_invalid"):
                    self.index.validate()
                with closing(sqlite3.connect(self.path)) as connection:
                    connection.execute(drop_sql)
                    connection.commit()

    def test_existing_index_is_bound_to_exact_vault_id(self) -> None:
        other = VaultIndex(
            self.path,
            vault_id="99999999-8888-4777-8666-555555555555",
        )

        with self.assertRaisesRegex(VaultError, "index_schema_invalid"):
            other.initialize()

    def test_sibling_index_cannot_reuse_another_instance_authenticator(self) -> None:
        sibling = VaultIndex(self.path, vault_id=self.vault_id)

        with self.assertRaisesRegex(
            VaultError, "record_authentication_failed"
        ):
            sibling.list_records()

    def test_index_filesystem_errors_are_fixed_and_path_safe(self) -> None:
        nested_path = self.root / "nested" / "index.sqlite3"
        nested = VaultIndex(nested_path, vault_id=self.vault_id)
        with mock.patch.object(
            Path, "mkdir", side_effect=OSError(f"denied {nested_path}")
        ):
            with self.assertRaises(VaultError) as caught:
                nested.initialize()

        self.assertEqual(caught.exception.code, "index_initialize_failed")
        self.assertNotIn(str(nested_path), repr(caught.exception))

    def test_connect_closes_connection_when_pragma_setup_fails(self) -> None:
        connection = mock.Mock()
        connection.execute.side_effect = sqlite3.OperationalError(
            "synthetic pragma failure"
        )
        with mock.patch(
            "backend.mailbox_ingest.vault_index.sqlite3.connect",
            return_value=connection,
        ):
            with self.assertRaises(VaultError) as caught:
                self.index.list_records()

        self.assertEqual(caught.exception.code, "index_read_failed")
        connection.close.assert_called_once_with()

    def test_crud_round_trip_preserves_only_approved_metadata(self) -> None:
        record = _record()

        self.index.add_record(record)
        loaded = self.index.get_record(record.record_id)
        self.index.mark_delete_pending(record.record_id)
        pending = self.index.get_record(record.record_id)
        self.index.delete_record(record.record_id)

        self.assertEqual(replace(loaded, metadata_mac=b""), record)
        self.assertEqual(len(loaded.metadata_mac), 32)
        self.assertEqual(pending.lifecycle_state, "delete_pending")
        self.assertIsNone(self.index.get_record(record.record_id))
        self.assertNotIn(record.encrypted_relpath, repr(record))
        self.assertNotIn(record.dedup_hmac.hex(), repr(record))

    def test_plaintext_canary_never_appears_in_database_bytes(self) -> None:
        canary = b"SYNTHETIC-PLAINTEXT-CANARY"
        identifiers = iter(("1" * 32, "a" * 32))
        vault = MailboxVault(
            self.root,
            vault_id=self.vault_id,
            crypto=self.crypto,
            index=self.index,
            clock=lambda: 1_000,
            random_identifier=lambda: next(identifiers),
        )
        vault.put_record(canary, expires_at_utc=2_000)

        for artifact in self.root.rglob("*"):
            if artifact.is_file():
                self.assertNotIn(canary, artifact.read_bytes())

    def test_invalid_metadata_and_path_traversal_fail_closed(self) -> None:
        invalid_records = (
            _record(record_id="not-random"),
            _record(relpath="../outside.mvlt"),
            _record(relpath="records/plain-name.eml"),
            VaultRecord(
                record_id="0123456789abcdef0123456789abcdef",
                encrypted_relpath="records/ab/a.mvlt",
                dedup_hmac=b"short",
                created_at_utc=1,
                expires_at_utc=2,
                ciphertext_size=3,
                format_version=1,
                key_version=1,
                lifecycle_state="active",
            ),
            _record(state="unknown"),
        )
        for record in invalid_records:
            with self.subTest(record=repr(record)):
                with self.assertRaises(VaultError) as caught:
                    self.index.add_record(record)
                self.assertRegex(caught.exception.code, r"^[a-z0-9_]+$")
                self.assertNotIn("outside", repr(caught.exception))

    def test_reads_reject_corrupt_record_metadata_with_fixed_error(self) -> None:
        record = _record()
        self.index.add_record(record)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "UPDATE records SET expires_at_utc='malformed' WHERE record_id=?",
                (record.record_id,),
            )
            connection.commit()

        with self.assertRaisesRegex(VaultError, "invalid_record_metadata"):
            self.index.get_record(record.record_id)
        with self.assertRaisesRegex(VaultError, "invalid_record_metadata"):
            self.index.list_records()

    def test_reads_map_corrupt_row_shape_to_fixed_error(self) -> None:
        record = _record()
        self.index.add_record(record)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "ALTER TABLE records RENAME COLUMN expires_at_utc TO malformed"
            )
            connection.commit()

        with self.assertRaises(Exception) as caught:
            self.index.get_record(record.record_id)
        self.assertIsInstance(caught.exception, VaultError)
        self.assertEqual(caught.exception.code, "invalid_record_metadata")

    def test_duplicate_insert_rolls_back_without_corrupting_existing_row(self) -> None:
        original = _record()
        self.index.add_record(original)

        with self.assertRaisesRegex(VaultError, "index_write_failed"):
            self.index.add_record(_record(relpath="records/cd/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.mvlt"))

        loaded = self.index.get_record(original.record_id)
        self.assertEqual(replace(loaded, metadata_mac=b""), original)
        self.assertEqual(len(self.index.list_records()), 1)

    def test_expired_and_delete_pending_queries_are_bounded(self) -> None:
        for position in range(5):
            record_id = f"{position + 1:032x}"
            self.index.add_record(
                _record(
                    record_id,
                    relpath=f"records/{position:02x}/{position + 20:032x}.mvlt",
                    expires_at=1_000 + position,
                    state="delete_pending" if position == 4 else "active",
                )
            )

        expired = self.index.list_expired(now_utc=2_000, limit=2)
        pending = self.index.list_delete_pending(limit=2)

        self.assertEqual(len(expired), 2)
        self.assertEqual(len(pending), 1)
        with self.assertRaisesRegex(VaultError, "invalid_limit"):
            self.index.list_expired(now_utc=2_000, limit=0)
        with self.assertRaisesRegex(VaultError, "invalid_limit"):
            self.index.list_expired(now_utc=2_000, limit=1_001)

    def test_vault_lifecycle_state_is_fixed_and_persistent(self) -> None:
        self.assertEqual(self.index.get_vault_state(), "active")
        for state in ("revoking", "revoke_incomplete", "revoked"):
            self.index.set_vault_state(state)
            self.assertEqual(self.index.get_vault_state(), state)
        with self.assertRaisesRegex(VaultError, "invalid_lifecycle_state"):
            self.index.set_vault_state("custom secret detail")

    def test_exclusive_mutation_lock_rejects_concurrent_holder(self) -> None:
        first = VaultMutationLock(self.root / ".mutation.lock")
        second = VaultMutationLock(self.root / ".mutation.lock")

        with first:
            with self.assertRaisesRegex(VaultError, "vault_busy"):
                with second:
                    self.fail("second lock must not be acquired")

        with second:
            self.assertTrue((self.root / ".mutation.lock").exists())
        self.assertTrue((self.root / ".mutation.lock").exists())

    def test_mutation_lock_closes_descriptor_when_fsync_fails(self) -> None:
        lock = VaultMutationLock(self.root / ".mutation.lock")
        with (
            mock.patch.object(os, "open", return_value=73),
            mock.patch.object(os, "fsync", side_effect=OSError("synthetic fsync")),
            mock.patch.object(os, "close") as close,
            mock.patch.object(Path, "unlink") as unlink,
        ):
            with self.assertRaises(VaultError) as caught:
                lock.__enter__()

        self.assertEqual(caught.exception.code, "vault_busy")
        close.assert_called_once_with(73)
        unlink.assert_not_called()
        self.assertIsNone(lock._descriptor)


if __name__ == "__main__":
    unittest.main()
