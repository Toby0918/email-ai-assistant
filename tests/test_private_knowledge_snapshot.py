"""Signed encrypted runtime snapshot publication and fallback tests."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.private_knowledge.errors import PrivateKnowledgeError
from backend.private_knowledge.runtime_loader import load_runtime_knowledge
from backend.private_knowledge.schema import KnowledgeCardV1
from backend.private_knowledge.snapshot import publish_runtime_snapshot
from backend.private_knowledge.snapshot_path import validate_snapshot_path
from tests.test_knowledge_card_schema import valid_card


UTC = timezone.utc


def approved_card() -> KnowledgeCardV1:
    value = valid_card()
    value["card_id"] = str(uuid.uuid4())
    value["review"]["business"] = {  # type: ignore[index]
        "actor_ref": "actor-business-001", "role": "business",
        "approved_at": "2026-07-14T13:00:00Z", "card_version": 1,
    }
    value["review"]["privacy"] = {  # type: ignore[index]
        "actor_ref": "actor-privacy-001", "role": "privacy_security",
        "approved_at": "2026-07-14T13:00:00Z", "card_version": 1,
    }
    value["lifecycle"] = {
        "status": "approved", "created_at": "2026-07-14T12:00:00Z",
        "expires_at": "2026-10-12T13:00:00Z",
        "review_due_at": "2026-10-12T13:00:00Z",
    }
    return KnowledgeCardV1.from_mapping(value)


class PrivateKnowledgeSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.target = self.root / "runtime" / "knowledge.pksnap"
        self.authority_id = str(uuid.uuid4())
        self.snapshot_id = str(uuid.uuid4())
        self.key = b"S" * 32
        self.signing = Ed25519PrivateKey.generate()
        self.now = datetime(2026, 7, 15, 12, tzinfo=UTC)
        self.allow_path = lambda _path: None

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _publish(self, *, crash_hook=None) -> None:
        publish_runtime_snapshot(
            self.target,
            (approved_card(),),
            authority_id=self.authority_id,
            snapshot_id=self.snapshot_id,
            encryption_key=self.key,
            signing_private_key=self.signing,
            now=self.now,
            path_validator=self.allow_path,
            crash_hook=crash_hook,
        )

    def _load(self, *, key=None, verification_key=None, now=None):
        return load_runtime_knowledge(
            self.target,
            encryption_key=key or self.key,
            verification_public_key=verification_key or self.signing.public_key(),
            clock=lambda: now or self.now,
            path_validator=self.allow_path,
        )

    def test_round_trip_returns_immutable_runtime_projection_without_authority_metadata(self) -> None:
        self._publish()

        result = self._load()

        self.assertEqual(result.code, "snapshot_loaded")
        self.assertIsInstance(result.cards, tuple)
        self.assertEqual(len(result.cards), 1)
        card = result.cards[0]
        self.assertFalse(hasattr(card, "review"))
        self.assertFalse(hasattr(card, "privacy_check"))
        self.assertFalse(hasattr(card, "lifecycle"))
        with self.assertRaises((AttributeError, TypeError)):
            card.version = 2  # type: ignore[misc]

    def test_missing_tamper_wrong_signature_wrong_decrypt_key_and_expiry_fall_back(self) -> None:
        missing = self._load()
        self.assertEqual((missing.cards, missing.code), ((), "snapshot_missing"))
        self._publish()

        wrong_signer = Ed25519PrivateKey.generate().public_key()
        self.assertEqual(
            self._load(verification_key=wrong_signer).code,
            "snapshot_signature_invalid",
        )
        self.assertEqual(self._load(key=b"T" * 32).code, "snapshot_decrypt_invalid")
        self.assertEqual(
            self._load(now=datetime(2026, 10, 12, 13, tzinfo=UTC)).code,
            "snapshot_expired",
        )

        frame = bytearray(self.target.read_bytes())
        frame[-70] ^= 1
        self.target.write_bytes(frame)
        tampered = self._load()
        self.assertEqual((tampered.cards, tampered.code), ((), "snapshot_signature_invalid"))

    def test_failed_replacement_leaves_previous_snapshot_loadable(self) -> None:
        self._publish()
        previous = self.target.read_bytes()

        with self.assertRaisesRegex(PrivateKnowledgeError, "snapshot_write_failed"):
            self._publish(crash_hook=lambda _point: (_ for _ in ()).throw(RuntimeError()))

        self.assertEqual(self.target.read_bytes(), previous)
        self.assertEqual(self._load().code, "snapshot_loaded")

    def test_publication_rejects_project_temp_authority_and_reparse_targets(self) -> None:
        forbidden = self.root / "authority"
        forbidden.mkdir()
        target = forbidden / "runtime.pksnap"
        with self.assertRaisesRegex(PrivateKnowledgeError, "snapshot_path_invalid"):
            publish_runtime_snapshot(
                target,
                (approved_card(),),
                authority_id=self.authority_id,
                snapshot_id=self.snapshot_id,
                encryption_key=self.key,
                signing_private_key=self.signing,
                now=self.now,
                forbidden_roots=(self.root, forbidden),
            )

    def test_default_path_policy_rejects_temp_onedrive_and_raw_vault(self) -> None:
        with self.assertRaisesRegex(PrivateKnowledgeError, "snapshot_path_invalid"):
            validate_snapshot_path(self.target)
        with self.assertRaisesRegex(PrivateKnowledgeError, "snapshot_path_invalid"):
            validate_snapshot_path(
                Path("C:/External/OneDrive - Synthetic/runtime/knowledge.pksnap")
            )

        vault = self.root / "synthetic-vault"
        marker = vault / "keys" / "recovery-state.json"
        marker.parent.mkdir(parents=True)
        marker.write_text("{}", encoding="utf-8")
        with patch(
            "backend.private_knowledge.snapshot_path.tempfile.gettempdir",
            return_value="C:/Synthetic-System-Temp",
        ):
            with self.assertRaisesRegex(
                PrivateKnowledgeError, "snapshot_path_invalid"
            ):
                validate_snapshot_path(vault / "runtime" / "knowledge.pksnap")

        candidate = self.root / "candidate-store"
        candidate.mkdir()
        (candidate / "candidate-key.pkenv").write_bytes(b"synthetic-marker")
        with patch(
            "backend.private_knowledge.snapshot_path.tempfile.gettempdir",
            return_value="C:/Synthetic-System-Temp",
        ):
            with self.assertRaisesRegex(
                PrivateKnowledgeError, "snapshot_path_invalid"
            ):
                validate_snapshot_path(
                    candidate / "runtime" / "knowledge.pksnap"
                )

    def test_publication_revalidates_approved_reviews_after_factory_bypass(self) -> None:
        valid = approved_card()
        invalid_reviews = replace(
            valid,
            review=(valid.review[0], None, None, None),
        )
        invalid_shape = replace(valid, applicability=("general",))  # type: ignore[arg-type]

        for invalid in (invalid_reviews, invalid_shape):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                PrivateKnowledgeError, "snapshot_schema_invalid"
            ):
                publish_runtime_snapshot(
                    self.target,
                    (invalid,),
                    authority_id=self.authority_id,
                    snapshot_id=self.snapshot_id,
                    encryption_key=self.key,
                    signing_private_key=self.signing,
                    now=self.now,
                    path_validator=self.allow_path,
                )
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
