"""Synthetic staging-boundary and administrator CLI isolation tests."""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.mailbox_ingest.knowledge_stage_source import open_knowledge_stage_source
from backend.mailbox_ingest.models import SecretBuffer
from backend.mailbox_ingest.scan_record import encode_scan_record
from backend.private_knowledge.deidentifier import deidentify_private_text
from backend.private_knowledge.errors import PrivateKnowledgeError
from backend.private_knowledge.key_store import SecretBytes
from backend.private_knowledge.repository import CandidateBatchStore
from backend.private_knowledge.residual_scanner import ResidualFinding, scan_residuals
from scripts.manage_mailbox_vault import (
    COMMANDS,
    StageKnowledgeResult,
    execute_stage_knowledge_command,
    run_cli,
    stage_knowledge,
)
from tests.test_manage_mailbox_vault import fake_dependencies


def selection(record_ids: list[str]) -> dict[str, object]:
    return {
        "schema_version": "StageKnowledgeSelectionV1",
        "vault_id": "11111111-2222-4333-8444-555555555555",
        "scope_fingerprint": "a" * 64,
        "window_start": "2024-07-14T00:00:00Z",
        "window_end": "2026-07-14T00:00:00Z",
        "expires_at": "2026-07-15T12:05:00Z",
        "record_ids": record_ids,
        "business_review": {
            "actor_ref": "actor-business-001", "role": "business",
            "approved_at": "2026-07-14T12:00:00Z",
        },
        "privacy_review": {
            "actor_ref": "actor-privacy-001", "role": "privacy_security",
            "approved_at": "2026-07-14T12:05:00Z",
        },
    }


class LiveState:
    raw = 0
    mapping = 0
    max_raw = 0
    max_mapping = 0


class RawRecord:
    __slots__ = ("text", "context", "_state")

    def __init__(self, text: str, state: LiveState) -> None:
        self.text = text
        self.context = {"people": ["Alex Example"], "organizations": []}
        self._state = state

    def __enter__(self):
        self._state.raw += 1
        self._state.max_raw = max(self._state.max_raw, self._state.raw)
        return self

    def __exit__(self, *_args):
        self.text = ""
        self.context = {}
        self._state.raw -= 1


class TrackedDeidentified:
    __slots__ = ("_inner", "_state")

    def __init__(self, text: str, context: object, state: LiveState) -> None:
        self._inner = deidentify_private_text(text, context)
        self._state = state

    @property
    def text(self) -> str:
        return self._inner.text

    def __enter__(self):
        self._state.mapping += 1
        self._state.max_mapping = max(self._state.max_mapping, self._state.mapping)
        self._inner.__enter__()
        return self

    def __exit__(self, *_args):
        self._inner.close()
        self._state.mapping -= 1


class StageKnowledgeTests(unittest.TestCase):
    def test_default_adapter_enforces_deadline_scope_and_writes_encrypted_batch(self) -> None:
        state = LiveState()
        state.raw = state.mapping = state.max_raw = state.max_mapping = 0
        batch_id = "22222222-3333-4444-8555-666666666666"
        record_id = "1" * 32
        key = b"K" * 32

        class Source:
            evidence = ("3-5", "2-3")
            closed = False

            def read_one_record(self, selected: str):
                self.assert_record = selected
                return RawRecord("Alex Example requested delivery status.", state)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.closed = True

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            manifest = root / "selection.json"
            manifest.write_text(json.dumps(selection([record_id])), encoding="utf-8")
            source = Source()
            calls: list[object] = []

            def source_factory(*_args, **kwargs):
                calls.append(kwargs)
                return source

            arguments = argparse.Namespace(
                vault=root / "raw-vault", authorization_id="AUTH-STAGE-1",
                account="one@example.test", selection_manifest=manifest,
                candidate_batch_root=root / "candidate",
            )
            result = execute_stage_knowledge_command(
                arguments,
                source_factory=source_factory,
                protector_factory=lambda: object(),
                candidate_key_loader=lambda *_args: SecretBytes(key),
                path_validator=lambda *_args: None,
                current_time=lambda: datetime(2026, 7, 14, 13, tzinfo=timezone.utc),
                epoch_clock=lambda: 1_752_500_000,
                batch_id_factory=lambda: batch_id,
                project_root=Path("C:/synthetic-project"),
            )

            batch = CandidateBatchStore(
                root / "candidate", key, batch_id=batch_id
            )
            ciphertext = batch.path.read_bytes()
            evidence, candidates = batch.read_with_evidence()

        self.assertEqual(result.code, "stage_complete")
        self.assertTrue(source.closed)
        self.assertEqual(source.assert_record, record_id)
        self.assertEqual(evidence, ("3-5", "2-3"))
        self.assertNotIn(b"Alex Example", ciphertext)
        self.assertIn("<PERSON_1>", candidates[0].text)
        self.assertEqual(calls[0]["expected_vault_id"], selection([record_id])["vault_id"])
        self.assertEqual(calls[0]["expected_scope"], "a" * 64)

    def test_default_adapter_rejects_expired_review_before_opening_vault(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            value = selection(["2" * 32])
            value["expires_at"] = "2026-07-14T12:30:00Z"
            manifest = root / "selection.json"
            manifest.write_text(json.dumps(value), encoding="utf-8")
            arguments = argparse.Namespace(
                vault=root / "raw-vault", authorization_id="AUTH-STAGE-1",
                account="one@example.test", selection_manifest=manifest,
                candidate_batch_root=root / "candidate",
            )
            calls: list[object] = []
            with self.assertRaisesRegex(PrivateKnowledgeError, "stage_selection_expired"):
                execute_stage_knowledge_command(
                    arguments,
                    source_factory=lambda *_args, **_kwargs: calls.append("source"),
                    protector_factory=lambda: calls.append("protector"),
                    candidate_key_loader=lambda *_args: calls.append("key"),
                    path_validator=lambda *_args: calls.append("path"),
                    current_time=lambda: datetime(2026, 7, 14, 13, tzinfo=timezone.utc),
                    epoch_clock=lambda: 1_752_500_000,
                    batch_id_factory=lambda: str(uuid.uuid4()),
                    project_root=Path("C:/synthetic-project"),
                )
            self.assertEqual(calls, [])

    def test_injected_vault_source_validates_scope_window_and_releases_plaintext(self) -> None:
        vault_id = "11111111-2222-4333-8444-555555555555"
        scope = "a" * 64
        record_id = "9" * 32
        payload = encode_scan_record(
            scope=scope, fingerprint="b" * 64, opaque_folder_id="c" * 64,
            mailbox="INBOX", uidvalidity=1, uid=7,
            internal_date=datetime(2025, 7, 14, tzinfo=timezone.utc),
            expires_at_utc=1_800_000_000,
            header=(
                b"From: Alex Example <alex@partner.example>\r\n"
                b"To: Internal User <one@example.test>\r\n"
                b"Message-ID: <synthetic-1@partner.example>\r\n\r\n"
            ),
            bodies=(b"Please confirm delivery status.",), attachments=(),
            candidate_id_factory=lambda: "d" * 32,
        )

        class Opened:
            identity = type("Identity", (), {"vault_id": vault_id})()
            vault = type("Vault", (), {
                "get_record": staticmethod(lambda selected: SecretBuffer(payload)
                                if selected == record_id else None)
            })()
            closed = False

            def require_authorization_scope(self, _authorization, _account):
                return type("Scope", (), {"opaque_scope_id": scope})()

            def close(self):
                self.closed = True

        opened = Opened()
        source = open_knowledge_stage_source(
            Path("E:/synthetic-vault"),
            authorization_id="AUTH-STAGE-1", account="one@example.test",
            expected_vault_id=vault_id, expected_scope=scope,
            window_start=datetime(2024, 7, 14, tzinfo=timezone.utc),
            window_end=datetime(2026, 7, 14, tzinfo=timezone.utc),
            project_root=Path("C:/synthetic-project"),
            validate_existing=lambda *_args: object(),
            dpapi_factory=lambda: object(),
            opener=lambda *_args, **_kwargs: opened,
            clock=lambda: 1_750_000_000,
        )
        with source:
            context = source.read_one_record(record_id)
            with context as raw:
                self.assertIn("Alex Example", raw.text)
                self.assertEqual(raw.context["people"], ["Alex Example", "Internal User"])
            self.assertEqual(raw.text, "")
            self.assertEqual(source.evidence, ("1", "1"))
        self.assertTrue(opened.closed)

    def test_one_at_a_time_release_then_encrypted_candidate_only_write(self) -> None:
        state = LiveState()
        state.raw = state.mapping = state.max_raw = state.max_mapping = 0
        record_ids = ["1" * 32, "2" * 32]
        texts = {
            record_ids[0]: "Alex Example requested delivery status.",
            record_ids[1]: "Alex Example requested a reply.",
        }
        writes: list[object] = []

        def writer(candidates):
            self.assertEqual((state.raw, state.mapping), (0, 0))
            self.assertTrue(all(not hasattr(item, "raw_id") for item in candidates))
            self.assertNotIn("Alex Example", repr(candidates))
            writes.append(candidates)
            return tuple(item.candidate_id for item in candidates)

        result = stage_knowledge(
            selection(record_ids),
            read_one_record=lambda record_id: RawRecord(texts[record_id], state),
            deidentify=lambda text, context: TrackedDeidentified(text, context, state),
            scan_residuals=scan_residuals,
            write_encrypted_candidate_batch=writer,
        )

        self.assertEqual(result.code, "stage_complete")
        self.assertEqual((result.accepted_count, result.rejected_count), (2, 0))
        self.assertEqual((state.max_raw, state.max_mapping), (1, 1))
        self.assertEqual(len(writes), 1)
        rendered = repr(result)
        self.assertNotIn(record_ids[0], rendered)
        self.assertNotIn("Alex Example", rendered)

    def test_any_residual_blocks_all_writes_and_callback_errors_are_fixed(self) -> None:
        record_ids = ["3" * 32, "4" * 32]
        writes: list[object] = []
        state = LiveState()
        state.raw = state.mapping = state.max_raw = state.max_mapping = 0
        calls = 0

        def residuals(_value):
            nonlocal calls
            calls += 1
            return () if calls == 1 else (ResidualFinding("residual_email", 1),)

        blocked = stage_knowledge(
            selection(record_ids),
            read_one_record=lambda _record_id: RawRecord("Alex Example replied.", state),
            deidentify=lambda text, context: TrackedDeidentified(text, context, state),
            scan_residuals=residuals,
            write_encrypted_candidate_batch=lambda value: writes.append(value),
        )
        self.assertEqual(blocked, StageKnowledgeResult("stage_residual_blocked", 0, 2, ()))
        self.assertEqual(writes, [])
        self.assertEqual((state.raw, state.mapping), (0, 0))

        failed = stage_knowledge(
            selection(["5" * 32]),
            read_one_record=lambda _record_id: (_ for _ in ()).throw(
                RuntimeError("SENSITIVE-CANARY")
            ),
            deidentify=deidentify_private_text,
            scan_residuals=scan_residuals,
            write_encrypted_candidate_batch=lambda _value: None,
        )
        self.assertEqual(failed.code, "stage_callback_failed")
        self.assertNotIn("SENSITIVE-CANARY", repr(failed))

    def test_selection_is_exact_bounded_unique_scope_and_dual_reviewed(self) -> None:
        invalid_values = []
        duplicate = selection(["6" * 32, "6" * 32])
        invalid_values.append(duplicate)
        too_many = selection([f"{number:032x}" for number in range(201)])
        invalid_values.append(too_many)
        unknown = selection(["7" * 32])
        unknown["unknown"] = True
        invalid_values.append(unknown)
        same_actor = selection(["8" * 32])
        same_actor["privacy_review"]["actor_ref"] = "actor-business-001"  # type: ignore[index]
        invalid_values.append(same_actor)
        stale_review = selection(["9" * 32])
        stale_review["expires_at"] = "2026-07-16T12:05:01Z"
        invalid_values.append(stale_review)

        for value in invalid_values:
            called: list[object] = []
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "stage_selection_invalid"
            ):
                stage_knowledge(
                    value,
                    read_one_record=lambda _value: called.append("read"),
                    deidentify=lambda *_args: called.append("deidentify"),
                    scan_residuals=lambda _value: (),
                    write_encrypted_candidate_batch=lambda _value: called.append("write"),
                )
            self.assertEqual(called, [])

    def test_stage_command_is_local_separate_from_exact_eight_core_commands(self) -> None:
        self.assertEqual(len(COMMANDS), 8)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            manifest = root / "selection.json"
            batch = root / "candidate"
            manifest.write_text("{}", encoding="utf-8")
            events: list[object] = []
            expected = StageKnowledgeResult("stage_complete", 1, 0, (str(uuid.uuid4()),))
            argv = [
                "stage-knowledge", "--vault", str(root / "vault"),
                "--authorization-id", "AUTH-STAGE-1",
                "--account", "one@example.test",
                "--selection-manifest", str(manifest),
                "--candidate-batch-root", str(batch),
            ]
            code = run_cli(
                argv,
                dependencies=fake_dependencies(events),
                stage_runner=lambda _arguments: expected,
            )
        self.assertEqual(code, 0)
        labels = [event[0] if isinstance(event, tuple) else event for event in events]
        self.assertNotIn("preflight", labels)
        self.assertNotIn("getpass", labels)
        self.assertIn(("emit", expected.to_dict()), events)


if __name__ == "__main__":
    unittest.main()
