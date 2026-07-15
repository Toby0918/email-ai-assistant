"""Private-knowledge CLI surface and content-free dispatch tests."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.private_knowledge.cli_service import PrivateKnowledgeCommandService
from backend.private_knowledge.key_store import open_candidate_key
from backend.private_knowledge.repository import CandidateBatchStore, DetachedCandidate
from scripts.manage_private_knowledge import (
    COMMANDS,
    PrivateCliDependencies,
    PrivateCliResult,
    run_cli,
)


class ManagePrivateKnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.authority_id = str(uuid.uuid4())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _argv(self, command: str) -> list[str]:
        argv = [
            command, "--authority-root", str(self.root / "authority"),
            "--authority-id", self.authority_id,
        ]
        if command == "init":
            argv += ["--candidate-root", str(self.root / "candidate")]
        elif command == "import-candidate":
            argv += [
                "--batch-root", str(self.root / "candidate"),
                "--batch-id", str(uuid.uuid4()), "--candidate-id", str(uuid.uuid4()),
            ]
        elif command == "create":
            proposal = self.root / "reviewed-proposal.json"
            proposal.write_text("{}", encoding="utf-8")
            argv += ["--candidate-id", str(uuid.uuid4()), "--reviewed-proposal", str(proposal)]
        elif command in {"business-approve", "privacy-approve", "owner-approve"}:
            argv += ["--card-id", str(uuid.uuid4()), "--actor-ref", "actor-reviewer-001"]
        elif command in {"reject", "expire", "approve", "deprecate", "revoke"}:
            argv += ["--card-id", str(uuid.uuid4())]
        elif command == "publish":
            argv += [
                "--snapshot", str(self.root / "runtime" / "knowledge.pksnap"),
                "--snapshot-id", str(uuid.uuid4()),
            ]
        return argv

    def test_exact_single_item_commands_dispatch_without_mailbox_or_secret_input(self) -> None:
        self.assertEqual(COMMANDS, (
            "init", "import-candidate", "create", "business-approve",
            "privacy-approve", "owner-approve", "reject", "expire", "approve",
            "deprecate", "revoke", "publish",
        ))
        for command in COMMANDS:
            events: list[object] = []
            dependencies = PrivateCliDependencies(
                dispatch=lambda arguments: events.append(arguments.command)
                or PrivateCliResult(f"{arguments.command}_complete", count=1),
                emit=lambda payload: events.append(payload),
            )
            with self.subTest(command=command):
                self.assertEqual(run_cli(self._argv(command), dependencies=dependencies), 0)
                self.assertEqual(events[0], command)
                self.assertEqual(events[1]["count"], 1)

    def test_raw_content_evidence_threshold_bulk_force_key_and_vault_options_are_rejected(self) -> None:
        forbidden = (
            ["--rule-text", "secret"], ["--raw-content", "secret"],
            ["--conversation-count", "3"], ["--counterparty-count", "2"],
            ["--threshold", "1"], ["--bulk"], ["--force"],
            ["--key", "secret"], ["--password", "secret"],
            ["--vault", str(self.root / "vault")], ["--record-id", "1" * 32],
        )
        for extra in forbidden:
            events: list[object] = []
            dependencies = PrivateCliDependencies(
                dispatch=lambda _arguments: events.append("dispatch"),
                emit=lambda payload: events.append(payload),
            )
            with self.subTest(extra=extra):
                self.assertEqual(
                    run_cli(self._argv("create") + extra, dependencies=dependencies),
                    2,
                )
                self.assertNotIn("dispatch", events)

    def test_errors_and_results_are_fixed_and_never_include_exception_text(self) -> None:
        events: list[object] = []
        dependencies = PrivateCliDependencies(
            dispatch=lambda _arguments: (_ for _ in ()).throw(
                RuntimeError("SENSITIVE-CANARY")
            ),
            emit=lambda payload: events.append(payload),
        )
        self.assertEqual(run_cli(self._argv("approve"), dependencies=dependencies), 2)
        self.assertEqual(events, [{"ok": False, "code": "internal_error"}])
        self.assertNotIn("SENSITIVE-CANARY", repr(events))

    def test_injected_protector_runs_candidate_to_approved_snapshot_workflow(self) -> None:
        class Protector:
            def protect(self, value: bytes) -> bytes:
                return b"P" + value[::-1]

            def unprotect(self, value: bytes) -> bytes:
                if not value.startswith(b"P"):
                    raise ValueError
                return value[1:][::-1]

        candidate_root = self.root / "candidate"
        service = PrivateKnowledgeCommandService(
            protector=Protector(),
            clock=lambda: datetime(2026, 7, 14, 13, tzinfo=timezone.utc),
            project_root=Path("C:/synthetic-project"),
            snapshot_path_validator=lambda _path: None,
            storage_path_validator=lambda *_paths: None,
        )
        emitted: list[dict[str, object]] = []
        dependencies = PrivateCliDependencies(service.dispatch, emitted.append)

        self.assertEqual(run_cli(self._argv("init"), dependencies=dependencies), 0)
        candidate_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())
        with open_candidate_key(candidate_root, Protector()) as candidate_key:
            CandidateBatchStore(
                candidate_root, candidate_key, batch_id=batch_id,
                evidence=("3-5", "2-3"),
            ).write((DetachedCandidate(
                candidate_id,
                "A placeholder asks for current delivery status.",
            ),))

        import_argv = [
            "import-candidate", "--authority-root", str(self.root / "authority"),
            "--authority-id", self.authority_id,
            "--batch-root", str(candidate_root), "--batch-id", batch_id,
            "--candidate-id", candidate_id,
        ]
        self.assertEqual(run_cli(import_argv, dependencies=dependencies), 0)
        proposal = self.root / "proposal.json"
        proposal.write_text(
            """{
              "schema_version":"KnowledgeProposalV1",
              "rule_type":"action","language":"en",
              "applicability":{"accountability":"general","direction":"inbound","categories":["order_followup"]},
              "generic_rule":"Verify shipment progress before preparing a response.",
              "normalized_signals":["delivery_status","reply_requested"],
              "enum_mapping":{"priorities":["normal"],"categories":["order_followup"],"risks":["delivery_risk"],"actions":["check_delivery","reply"]},
              "safe_reply_guidance":"Acknowledge the request without promising a date.",
              "creator_actor_ref":"actor-creator-001",
              "privacy_checked_at":"2026-07-14T13:00:00Z"
            }""",
            encoding="utf-8",
        )
        create_argv = [
            "create", "--authority-root", str(self.root / "authority"),
            "--authority-id", self.authority_id,
            "--candidate-id", candidate_id, "--reviewed-proposal", str(proposal),
        ]
        self.assertEqual(run_cli(create_argv, dependencies=dependencies), 0)
        for command, actor in (
            ("business-approve", "actor-business-001"),
            ("privacy-approve", "actor-privacy-001"),
        ):
            argv = [
                command, "--authority-root", str(self.root / "authority"),
                "--authority-id", self.authority_id, "--card-id", candidate_id,
                "--actor-ref", actor,
            ]
            self.assertEqual(run_cli(argv, dependencies=dependencies), 0)
        approve_argv = [
            "approve", "--authority-root", str(self.root / "authority"),
            "--authority-id", self.authority_id, "--card-id", candidate_id,
        ]
        self.assertEqual(run_cli(approve_argv, dependencies=dependencies), 0)
        publish_argv = [
            "publish", "--authority-root", str(self.root / "authority"),
            "--authority-id", self.authority_id,
            "--snapshot", str(self.root / "runtime" / "knowledge.pksnap"),
            "--snapshot-id", str(uuid.uuid4()),
        ]
        self.assertEqual(run_cli(publish_argv, dependencies=dependencies), 0)
        self.assertTrue((self.root / "runtime" / "knowledge.pksnap").is_file())
        self.assertTrue(all(set(item) <= {"ok", "code", "count", "item_id"} for item in emitted))


if __name__ == "__main__":
    unittest.main()
