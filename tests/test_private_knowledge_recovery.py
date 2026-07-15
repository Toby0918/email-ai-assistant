"""Synthetic crash-recovery probes for private-knowledge state transitions."""

from __future__ import annotations

import argparse
import base64
import json
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.private_knowledge.candidate_imports import (
    ImportedCandidate,
    ImportedCandidateStore,
)
from backend.private_knowledge.cli_service import PrivateKnowledgeCommandService
from backend.private_knowledge.errors import PrivateKnowledgeError
from backend.private_knowledge.key_store import (
    initialize_private_keys,
    open_authority_keys,
    open_candidate_key,
)
from backend.private_knowledge.repository import AuthorityRepository
from backend.private_knowledge.schema import KnowledgeCardV1


class Protector:
    def protect(self, value: bytes) -> bytes:
        return b"P" + value[::-1]

    def unprotect(self, value: bytes) -> bytes:
        if not value.startswith(b"P"):
            raise ValueError
        return value[1:][::-1]


class PrivateKnowledgeRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.authority = self.root / "authority"
        self.candidate_root = self.root / "candidate"
        self.authority_id = str(uuid.uuid4())
        self.candidate_id = str(uuid.uuid4())
        self.now = datetime(2026, 7, 14, 13, tzinfo=timezone.utc)
        self.service = PrivateKnowledgeCommandService(
            protector=Protector(), clock=lambda: self.now,
            project_root=Path("C:/synthetic-project"),
            storage_path_validator=lambda *_paths: None,
        )
        self.service.dispatch(argparse.Namespace(
            command="init", authority_root=self.authority,
            candidate_root=self.candidate_root,
            authority_id=self.authority_id,
        ))
        with open_authority_keys(self.authority, Protector()) as keys:
            ImportedCandidateStore(
                self.authority, keys.authority_key,
                authority_id=self.authority_id,
            ).add(ImportedCandidate(
                self.candidate_id,
                ("A synthetic support note requests current status.",),
                ("3-5", "2-3"), "2026-08-13T13:00:00Z",
            ))
        self.proposal = self.root / "reviewed-proposal.json"
        self.proposal.write_text(json.dumps({
            "schema_version": "KnowledgeProposalV1",
            "rule_type": "action", "language": "en",
            "applicability": {
                "accountability": "general", "direction": "inbound",
                "categories": ["order_followup"],
            },
            "generic_rule": "Verify progress before preparing a response.",
            "normalized_signals": ["delivery_status"],
            "enum_mapping": {
                "priorities": ["normal"],
                "categories": ["order_followup"],
                "risks": ["delivery_risk"],
                "actions": ["check_delivery"],
            },
            "safe_reply_guidance": "Acknowledge without promising a date.",
            "creator_actor_ref": "actor-creator-001",
            "privacy_checked_at": "2026-07-14T13:00:00Z",
        }, sort_keys=True), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _create_arguments(self) -> argparse.Namespace:
        return argparse.Namespace(
            command="create", authority_root=self.authority,
            authority_id=self.authority_id, candidate_id=self.candidate_id,
            reviewed_proposal=self.proposal,
        )

    def _stores(self) -> tuple[AuthorityRepository, ImportedCandidateStore]:
        keys = open_authority_keys(self.authority, Protector())
        self.addCleanup(keys.close)
        return (
            AuthorityRepository(
                self.authority, keys.authority_key,
                authority_id=self.authority_id,
            ),
            ImportedCandidateStore(
                self.authority, keys.authority_key,
                authority_id=self.authority_id,
            ),
        )

    def test_create_retry_reconciles_exact_card_after_import_delete_failure(self) -> None:
        with patch.object(
            ImportedCandidateStore, "delete",
            side_effect=PrivateKnowledgeError("candidate_import_write_failed"),
        ), self.assertRaisesRegex(
            PrivateKnowledgeError, "candidate_import_write_failed"
        ):
            self.service.dispatch(self._create_arguments())

        repository, imports = self._stores()
        first_card = repository.get(self.candidate_id)
        self.assertIsNotNone(first_card)
        self.assertIsNotNone(imports.get(self.candidate_id))

        result = self.service.dispatch(self._create_arguments())

        self.assertEqual(result.code, "candidate_created")
        self.assertEqual(repository.get(self.candidate_id), first_card)
        self.assertEqual(len(repository.list_cards()), 1)
        self.assertIsNone(imports.get(self.candidate_id))

    def test_create_retry_rejects_mismatched_existing_card_without_consuming_import(self) -> None:
        with patch.object(
            ImportedCandidateStore, "delete",
            side_effect=PrivateKnowledgeError("candidate_import_write_failed"),
        ), self.assertRaises(PrivateKnowledgeError):
            self.service.dispatch(self._create_arguments())
        repository, imports = self._stores()
        existing = repository.get(self.candidate_id)
        self.assertIsNotNone(existing)
        mapping = existing.to_mapping()  # type: ignore[union-attr]
        mapping["generic_rule"] = "Escalate unresolved progress before replying."
        mismatched = KnowledgeCardV1.from_mapping(mapping)
        repository.replace(mismatched)

        with self.assertRaisesRegex(PrivateKnowledgeError, "card_exists"):
            self.service.dispatch(self._create_arguments())

        self.assertEqual(repository.get(self.candidate_id), mismatched)
        self.assertIsNotNone(imports.get(self.candidate_id))

    def test_key_initialization_resumes_after_second_envelope_protection_failure(self) -> None:
        authority = self.root / "recover-authority"
        candidate = self.root / "recover-candidate"

        class FailSecondProtector(Protector):
            calls = 0

            def protect(self, value: bytes) -> bytes:
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("SYNTHETIC-CANARY")
                return super().protect(value)

        with self.assertRaisesRegex(
            PrivateKnowledgeError, "key_protection_failed"
        ):
            initialize_private_keys(
                authority, candidate, FailSecondProtector(),
                rng=lambda size: (b"A" if size == 96 else b"C") * size,
            )
        authority_envelope = (authority / "authority-keys.pkenv").read_bytes()
        self.assertFalse((candidate / "candidate-key.pkenv").exists())

        initialize_private_keys(
            authority, candidate, Protector(), rng=lambda size: b"D" * size
        )

        self.assertEqual(
            (authority / "authority-keys.pkenv").read_bytes(),
            authority_envelope,
        )
        with open_authority_keys(authority, Protector()) as authority_keys, \
                open_candidate_key(candidate, Protector()) as candidate_key:
            self.assertEqual(bytes(authority_keys.authority_key), b"A" * 32)
            self.assertEqual(bytes(candidate_key), b"D" * 32)

    def test_key_initialization_rejects_existing_purpose_magic_and_length_mismatch(self) -> None:
        cases = {
            "purpose": lambda value: value.update({"purpose": "candidate"}),
            "magic": lambda value: value.update({
                "protected": base64.b64encode(
                    Protector().protect(b"X" * (len(b"PKAUTHKEY1") + 96))
                ).decode("ascii")
            }),
            "length": lambda value: value.update({
                "protected": base64.b64encode(
                    Protector().protect(b"PKAUTHKEY1" + b"A" * 95)
                ).decode("ascii")
            }),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                authority = self.root / f"tampered-authority-{label}"
                candidate = self.root / f"tampered-candidate-{label}"
                initialize_private_keys(authority, candidate, Protector())
                (candidate / "candidate-key.pkenv").unlink()
                envelope_path = authority / "authority-keys.pkenv"
                value = json.loads(envelope_path.read_text(encoding="ascii"))
                mutate(value)
                envelope_path.write_text(
                    json.dumps(value, sort_keys=True, separators=(",", ":")),
                    encoding="ascii",
                )
                tampered = envelope_path.read_bytes()

                with self.assertRaisesRegex(
                    PrivateKnowledgeError, "key_envelope_invalid"
                ):
                    initialize_private_keys(
                        authority, candidate, Protector(),
                        rng=lambda size: b"Z" * size,
                    )

                self.assertEqual(envelope_path.read_bytes(), tampered)
                self.assertFalse((candidate / "candidate-key.pkenv").exists())

    def test_key_initialization_validates_existing_peer_before_writing_missing_envelope(self) -> None:
        authority = self.root / "missing-authority"
        candidate = self.root / "tampered-candidate"
        initialize_private_keys(authority, candidate, Protector())
        (authority / "authority-keys.pkenv").unlink()
        candidate_path = candidate / "candidate-key.pkenv"
        value = json.loads(candidate_path.read_text(encoding="ascii"))
        value["purpose"] = "authority"
        candidate_path.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")),
            encoding="ascii",
        )
        tampered = candidate_path.read_bytes()

        with self.assertRaisesRegex(
            PrivateKnowledgeError, "key_envelope_invalid"
        ):
            initialize_private_keys(
                authority, candidate, Protector(), rng=lambda size: b"Z" * size
            )

        self.assertFalse((authority / "authority-keys.pkenv").exists())
        self.assertEqual(candidate_path.read_bytes(), tampered)

    def test_cli_init_resumes_after_import_store_initialization_failure(self) -> None:
        authority = self.root / "state-recovery-authority"
        candidate = self.root / "state-recovery-candidate"
        arguments = argparse.Namespace(
            command="init", authority_root=authority,
            candidate_root=candidate, authority_id=str(uuid.uuid4()),
        )

        with patch.object(
            ImportedCandidateStore,
            "initialize",
            side_effect=PrivateKnowledgeError("candidate_import_write_failed"),
        ), self.assertRaisesRegex(
            PrivateKnowledgeError, "candidate_import_write_failed"
        ):
            self.service.dispatch(arguments)

        self.assertTrue((authority / "authority.pkauth").is_file())
        self.assertFalse((authority / "candidate-imports.pkimpt").exists())

        result = self.service.dispatch(arguments)

        self.assertEqual(result.code, "private_knowledge_initialized")
        self.assertTrue((authority / "candidate-imports.pkimpt").is_file())


if __name__ == "__main__":
    unittest.main()
