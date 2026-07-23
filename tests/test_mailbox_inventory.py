"""Content-free mailbox inventory and encrypted control-store tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.mailbox_ingest.authorization import (
    AuthorizationError,
    AuthorizationScope,
    freeze_window,
)
from backend.mailbox_ingest.control_store import ControlStoreError, EncryptedControlStore
from backend.mailbox_ingest.folder_policy import RawFolder, select_mail_folders
from backend.mailbox_ingest.inventory import InventoryError, build_inventory
from backend.mailbox_ingest.inventory_codec import (
    decode_inventory_bundle,
    encode_inventory_bundle,
)
from backend.mailbox_ingest.models import SecretBuffer
from backend.mailbox_ingest.vault_access import VaultIdentity, open_mailbox_vault
from backend.mailbox_ingest.vault_index import VaultIndex


class FakeInventorySession:
    def __init__(self) -> None:
        self.selected: list[str | bytes] = []
        self.searches: list[datetime] = []
        self.sizes = {
            2: (100, datetime(2022, 2, 28, 12, 30, tzinfo=timezone.utc)),
            3: (200, datetime(2023, 6, 1, 8, 0, tzinfo=timezone.utc)),
            4: (300, datetime(2024, 2, 29, 12, 30, tzinfo=timezone.utc)),
        }

    def examine(self, mailbox: str | bytes) -> int:
        self.selected.append(mailbox)
        return 77

    def uid_search(self, since: datetime) -> tuple[int, ...]:
        self.searches.append(since)
        return (2, 3, 4)

    def uid_fetch_size(self, uid: int):
        size, internal_date = self.sizes[uid]
        return type("SizeEvidence", (), {
            "uid": uid,
            "size": size,
            "internal_date": internal_date,
        })()


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = AuthorizationScope.create(
            "AUTH-SYNTHETIC-1", "one@example.test", hmac_key=b"S" * 32
        )
        self.folders = select_mail_folders(
            (RawFolder(("\\Inbox",), "CANARY-INBOX"),),
            hmac_key=b"F" * 32,
        )
        self.window = freeze_window(
            datetime(2024, 2, 29, 12, 30, tzinfo=timezone.utc)
        )

    def _build(self, session: FakeInventorySession | None = None):
        return build_inventory(
            session or FakeInventorySession(),
            scope=self.scope,
            folders=self.folders,
            window=self.window,
            fingerprint_key=b"I" * 32,
        )

    def test_inventory_is_content_free_and_filters_exact_internaldate_window(self) -> None:
        session = FakeInventorySession()

        bundle = self._build(session)

        public = bundle.inventory.to_dict()
        rendered = json.dumps(public, sort_keys=True)
        self.assertEqual(
            set(public),
            {
                "schema_version", "opaque_scope_id", "endpoint", "window_start",
                "window_end", "folders", "total_count", "aggregate_size",
                "fingerprint",
            },
        )
        self.assertEqual(public["schema_version"], 1)
        self.assertEqual(public["total_count"], 3)
        self.assertEqual(public["aggregate_size"], 600)
        self.assertEqual(
            set(public["folders"][0]),
            {"opaque_folder_id", "uidvalidity", "count", "aggregate_size"},
        )
        self.assertEqual(public["folders"][0]["uidvalidity"], 77)
        self.assertRegex(public["fingerprint"], r"^[0-9a-f]{64}$")
        for forbidden in (
            "CANARY-INBOX", "one@example.test", "AUTH-SYNTHETIC-1",
            '"uid"', "subject", "filename", "body",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertEqual(
            session.searches,
            [datetime(2022, 2, 28, 0, 0, tzinfo=timezone.utc)],
        )
        self.assertEqual(bundle.evidence[0].role, "inbox")
        self.assertEqual(tuple(item.uid for item in bundle.evidence[0].messages), (2, 3, 4))

    def test_fingerprint_is_deterministic_but_binds_private_evidence(self) -> None:
        first = self._build().inventory.fingerprint
        second = self._build().inventory.fingerprint
        changed_session = FakeInventorySession()
        changed_session.sizes[3] = (
            201,
            datetime(2023, 6, 1, 8, 0, tzinfo=timezone.utc),
        )

        changed = self._build(changed_session).inventory.fingerprint

        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_fingerprint_binds_private_folder_role(self) -> None:
        inbox = select_mail_folders(
            (RawFolder(("\\Inbox",), "CANARY-INBOX"),),
            hmac_key=b"F" * 32,
        )
        business_custom = select_mail_folders(
            (RawFolder((), "CANARY-INBOX"),),
            hmac_key=b"F" * 32,
        )
        self.assertEqual(inbox[0].opaque_folder_id, business_custom[0].opaque_folder_id)

        inbox_fingerprint = build_inventory(
            FakeInventorySession(),
            scope=self.scope,
            folders=inbox,
            window=self.window,
            fingerprint_key=b"I" * 32,
        ).inventory.fingerprint
        custom_fingerprint = build_inventory(
            FakeInventorySession(),
            scope=self.scope,
            folders=business_custom,
            window=self.window,
            fingerprint_key=b"I" * 32,
        ).inventory.fingerprint

        self.assertNotEqual(inbox_fingerprint, custom_fingerprint)

    def test_invalid_missing_future_or_duplicate_internaldate_fails_closed(self) -> None:
        cases = {
            "missing": None,
            "naive": datetime(2023, 1, 1),
            "future": datetime(2024, 2, 29, 12, 30, 1, tzinfo=timezone.utc),
        }
        for label, internal_date in cases.items():
            session = FakeInventorySession()
            session.sizes[3] = (200, internal_date)  # type: ignore[assignment]
            with self.subTest(label=label):
                with self.assertRaises(InventoryError):
                    self._build(session)

        duplicate = FakeInventorySession()
        duplicate.uid_search = lambda _since: (2, 2)  # type: ignore[method-assign]
        with self.assertRaises(InventoryError):
            self._build(duplicate)

    def test_control_store_is_separate_encrypted_bounded_and_tamper_evident(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EncryptedControlStore(
                root,
                vault_id="11111111-2222-4333-8444-555555555555",
                master_key=b"M" * 32,
                rng=lambda size: b"N" * size,
                max_plaintext_size=4096,
            )
            payload = {"schema_version": 1, "counter": 7, "canary": "CONTROL-CANARY"}

            store.write("inventory", payload)

            self.assertEqual(store.read("inventory"), payload)
            artifacts = list((root / "control").iterdir())
            self.assertEqual(len(artifacts), 1)
            self.assertNotIn(b"CONTROL-CANARY", artifacts[0].read_bytes())
            corrupted = bytearray(artifacts[0].read_bytes())
            corrupted[-1] ^= 1
            artifacts[0].write_bytes(corrupted)
            with self.assertRaises(ControlStoreError):
                store.read("inventory")
            self.assertFalse(any(path.suffix == ".stage" for path in artifacts[0].parent.iterdir()))

    def test_control_store_create_is_atomic_encrypted_and_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nonces = iter((b"A" * 12, b"B" * 12))
            store = EncryptedControlStore(
                root,
                vault_id="11111111-2222-4333-8444-555555555555",
                master_key=b"M" * 32,
                rng=lambda _size: next(nonces),
            )
            payload = {
                "schema_version": 1,
                "opaque_scope_id": "a" * 64,
            }

            store.create("authorization-binding", payload)

            self.assertEqual(store.read("authorization-binding"), payload)
            with self.assertRaisesRegex(ControlStoreError, "control_store_exists"):
                store.create(
                    "authorization-binding",
                    {"schema_version": 1, "opaque_scope_id": "b" * 64},
                )
            artifact = next((root / "control").iterdir())
            self.assertNotIn(b"a" * 64, artifact.read_bytes())

    def test_private_inventory_control_codec_round_trips_exact_evidence(self) -> None:
        original = self._build()

        payload = encode_inventory_bundle(original)
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["evidence"][0]["role"], "inbox")
        restored = decode_inventory_bundle(payload)

        self.assertEqual(restored.inventory.to_dict(), original.inventory.to_dict())
        self.assertEqual(restored.evidence, original.evidence)
        payload["unexpected"] = "CANARY"
        with self.assertRaises(InventoryError):
            decode_inventory_bundle(payload)

    def test_inventory_control_codec_rejects_legacy_schema_with_fixed_code(self) -> None:
        payload = encode_inventory_bundle(self._build())
        payload["schema_version"] = 1

        with self.assertRaises(InventoryError) as caught:
            decode_inventory_bundle(payload)

        self.assertEqual(caught.exception.code, "inventory_control_invalid")

    def test_inventory_control_codec_rejects_unknown_private_role(self) -> None:
        payload = encode_inventory_bundle(self._build())
        payload["evidence"][0]["role"] = "unknown"

        with self.assertRaises(InventoryError) as caught:
            decode_inventory_bundle(payload)

        self.assertEqual(caught.exception.code, "inventory_control_invalid")

    def test_inventory_preserves_canonical_wire_mailbox_for_future_selects(self) -> None:
        session = FakeInventorySession()
        folders = select_mail_folders(
            (RawFolder((), "\u5ba2\u6237", b"&W6JiNw-"),),
            hmac_key=b"F" * 32,
        )

        bundle = build_inventory(
            session,
            scope=self.scope,
            folders=folders,
            window=self.window,
            fingerprint_key=b"I" * 32,
        )
        restored = decode_inventory_bundle(encode_inventory_bundle(bundle))

        self.assertEqual(session.selected, [b"&W6JiNw-"])
        self.assertEqual(bundle.evidence[0].mailbox, "\u5ba2\u6237")
        self.assertEqual(bundle.evidence[0].wire_mailbox, b"&W6JiNw-")
        self.assertEqual(restored.evidence[0].wire_mailbox, b"&W6JiNw-")

    def test_public_vault_opener_wipes_master_and_atomic_dedup_is_repr_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault_id = "11111111-2222-4333-8444-555555555555"
            index = VaultIndex(root / "vault-index.sqlite3", vault_id=vault_id)
            index.initialize()
            loaded_master = SecretBuffer(b"M" * 32)

            with open_mailbox_vault(
                root,
                dpapi=object(),
                clock=lambda: 1_700_000_000,
                identity_loader=lambda _root: VaultIdentity(vault_id, 1),
                master_key_loader=lambda _root, _dpapi: loaded_master,
            ) as opened:
                self.assertEqual(bytes(loaded_master), bytes(32))
                scoped = opened.authorization_scope(
                    "AUTH-OPEN-1", "one@example.test"
                )
                self.assertEqual(len(scoped.opaque_scope_id), 64)
                first = opened.vault.put_record_if_absent(
                    b"ATOMIC-DEDUP-CANARY", expires_at_utc=1_700_000_100
                )
                second = opened.vault.put_record_if_absent(
                    b"ATOMIC-DEDUP-CANARY", expires_at_utc=1_700_000_100
                )
                self.assertTrue(first.created)
                self.assertFalse(second.created)
                self.assertEqual(first.record_id, second.record_id)
                self.assertNotIn(first.record_id, repr(first))
                self.assertEqual(opened.vault.verify().total_count, 1)
                opened.control.write("inventory", {"schema_version": 1})

            with self.assertRaises(Exception):
                opened.control.read("inventory")

    def test_opened_vault_owns_a_distinct_wiped_metadata_only_corpus_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault_id = "11111111-2222-4333-8444-555555555555"
            VaultIndex(root / "vault-index.sqlite3", vault_id=vault_id).initialize()

            with open_mailbox_vault(
                root,
                dpapi=object(),
                clock=lambda: 1_700_000_000,
                identity_loader=lambda _root: VaultIdentity(vault_id, 1),
                master_key_loader=lambda _root, _dpapi: SecretBuffer(b"M" * 32),
            ) as opened:
                self.assertFalse((root / "corpus-index.sqlite3").exists())
                with opened.sales_identity_key() as identity_key:
                    self.assertEqual(len(identity_key), 32)
                    self.assertEqual(repr(identity_key), "SecretBuffer(<redacted>)")
                self.assertEqual(bytes(identity_key), bytes(32))
                opened.corpus_index.initialize()
                self.assertTrue((root / "corpus-index.sqlite3").is_file())
                self.assertNotIn("M" * 8, repr(opened.corpus_index))
                corpus_index = opened.corpus_index

            with self.assertRaises(Exception):
                corpus_index.summary()

    def test_vault_authorization_binding_is_encrypted_immutable_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault_id = "11111111-2222-4333-8444-555555555555"
            VaultIndex(root / "vault-index.sqlite3", vault_id=vault_id).initialize()

            with open_mailbox_vault(
                root,
                dpapi=object(),
                clock=lambda: 1_700_000_000,
                identity_loader=lambda _root: VaultIdentity(vault_id, 1),
                master_key_loader=lambda _root, _dpapi: SecretBuffer(b"M" * 32),
            ) as opened:
                bound = opened.create_authorization_binding(
                    "AUTH-BOUND-1", "one@example.test"
                )
                required = opened.require_authorization_scope(
                    "AUTH-BOUND-1", "one@example.test"
                )
                self.assertEqual(required.opaque_scope_id, bound.opaque_scope_id)
                for authorization, account in (
                    ("AUTH-BOUND-2", "one@example.test"),
                    ("AUTH-BOUND-1", "two@example.test"),
                ):
                    with self.subTest(
                        authorization=authorization, account=account
                    ), self.assertRaises(AuthorizationError) as caught:
                        opened.require_authorization_scope(authorization, account)
                    self.assertNotIn(account, repr(caught.exception))
                with self.assertRaises(AuthorizationError):
                    opened.create_authorization_binding(
                        "AUTH-BOUND-1", "one@example.test"
                    )

            combined = b"".join(
                path.read_bytes() for path in (root / "control").iterdir()
            )
            self.assertNotIn(b"AUTH-BOUND-1", combined)
            self.assertNotIn(b"one@example.test", combined)


if __name__ == "__main__":
    unittest.main()
