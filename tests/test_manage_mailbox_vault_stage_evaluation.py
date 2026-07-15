"""Administrator-only evaluation staging CLI tests with synthetic injections."""

from __future__ import annotations

import argparse
import base64
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.private_evaluation.errors import PrivateEvaluationError
from backend.private_evaluation.staging_contract import StageEvaluationResult
from scripts.manage_mailbox_vault import (
    COMMANDS,
    NETWORK_COMMANDS,
    STAGE_EVALUATION_COMMAND,
    _load_stage_evaluation_key,
    execute_stage_evaluation_command,
    run_cli,
)
from tests.test_manage_mailbox_vault import fake_dependencies
from tests.test_private_evaluation_staging import stage_selection_mapping


class _RawRecord:
    __slots__ = ("text", "context", "_events")

    def __init__(self, events: list[object]) -> None:
        self.text = "Alex Example requested a safe reply."
        self.context = {"people": ["Alex Example"], "organizations": []}
        self._events = events

    def __enter__(self) -> _RawRecord:
        self._events.append("raw-enter")
        return self

    def __exit__(self, *_args: object) -> None:
        self.text = ""
        self.context = {}
        self._events.append("raw-exit")


class _Source:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.closed = False

    def __enter__(self) -> _Source:
        self.events.append("source-enter")
        return self

    def __exit__(self, *_args: object) -> None:
        self.closed = True
        self.events.append("source-exit")

    def read_one_record(self, record_id: str) -> _RawRecord:
        self.events.append(("read", record_id))
        return _RawRecord(self.events)


class ManageMailboxVaultStageEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.vault = self.root / "raw-vault"
        self.manifest = self.root / "selection.json"
        self.manifest.write_text(
            json.dumps(stage_selection_mapping()), encoding="utf-8"
        )
        self.stage_path = self.root / "evaluation.pkevalstage"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _argv(self) -> list[str]:
        return [
            "stage-evaluation",
            "--vault", str(self.vault),
            "--authorization-id", "AUTH-EVAL-STAGE-1",
            "--account", "one@example.test",
            "--selection-manifest", str(self.manifest),
            "--staging-dataset", str(self.stage_path),
        ]

    def test_command_is_local_and_emits_only_exact_content_free_success(self) -> None:
        events: list[object] = []
        expected = StageEvaluationResult("evaluation_stage_complete", 200, 0)
        code = run_cli(
            self._argv(),
            dependencies=fake_dependencies(events),
            stage_evaluation_runner=lambda _arguments: expected,
        )

        self.assertEqual(code, 0)
        self.assertEqual(len(COMMANDS), 8)
        self.assertEqual(STAGE_EVALUATION_COMMAND, "stage-evaluation")
        self.assertNotIn(STAGE_EVALUATION_COMMAND, NETWORK_COMMANDS)
        labels = [event[0] if isinstance(event, tuple) else event for event in events]
        self.assertNotIn("preflight", labels)
        self.assertNotIn("prepare", labels)
        self.assertNotIn("getpass", labels)
        self.assertNotIn("session-factory", labels)
        self.assertEqual(events, [("emit", expected.to_dict())])

    def test_command_rejects_key_provider_range_and_force_overrides(self) -> None:
        forbidden = (
            ("--key", "secret"), ("--key-file", str(self.root / "key")),
            ("--key-env", "KEY"), ("--model", "other"),
            ("--endpoint", "https://example.test"), ("--case-count", "1"),
            ("--force",), ("--retry", "1"),
        )
        for option in forbidden:
            events: list[object] = []
            with self.subTest(option=option):
                code = run_cli(
                    [*self._argv(), *option],
                    dependencies=fake_dependencies(events),
                    stage_evaluation_runner=lambda _arguments: (_ for _ in ()).throw(
                        AssertionError("runner must not be reached")
                    ),
                )
                self.assertEqual(code, 2)
                self.assertEqual(
                    events, [("emit", {"ok": False, "code": "argument_invalid"})]
                )

    def test_adapter_validates_manifest_and_path_before_hidden_key_then_reads_and_writes(self) -> None:
        events: list[object] = []
        source = _Source(events)
        key = bytearray(b"E" * 32)
        source_kwargs: dict[str, object] = {}

        def path_validator(path: Path) -> Path:
            events.append(("path", path.suffix))
            return path

        def key_loader() -> bytearray:
            events.append("evaluation-key")
            return key

        def source_factory(*_args: object, **kwargs: object) -> _Source:
            events.append("source-factory")
            source_kwargs.update(kwargs)
            return source

        def stage_writer(path: Path, cases: tuple[object, ...], supplied: bytearray) -> None:
            events.append(("write", path.suffix, len(cases)))
            self.assertEqual(bytes(supplied), b"E" * 32)

        arguments = argparse.Namespace(
            command="stage-evaluation", vault=self.vault,
            authorization_id="AUTH-EVAL-STAGE-1", account="one@example.test",
            selection_manifest=self.manifest, staging_dataset=self.stage_path,
        )
        result = execute_stage_evaluation_command(
            arguments,
            source_factory=source_factory,
            key_loader=key_loader,
            stage_writer=stage_writer,
            path_validator=path_validator,
            current_time=lambda: datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
            epoch_clock=lambda: 1_752_500_000,
            project_root=Path("C:/synthetic-project"),
        )

        self.assertEqual(result, StageEvaluationResult("evaluation_stage_complete", 200, 0))
        self.assertTrue(source.closed)
        self.assertEqual(bytes(key), bytes(32))
        self.assertLess(events.index(("path", ".pkevalstage")), events.index("evaluation-key"))
        self.assertLess(events.index("evaluation-key"), events.index("source-factory"))
        self.assertLess(events.index("source-factory"), events.index(("read", "0" * 31 + "1")))
        self.assertEqual(events[-2:], [("write", ".pkevalstage", 200), "source-exit"])
        self.assertEqual(source_kwargs["expected_vault_id"], stage_selection_mapping()["vault_id"])
        self.assertEqual(source_kwargs["expected_scope"], "a" * 64)

    def test_invalid_manifest_or_path_stops_before_key_source_and_writer(self) -> None:
        calls: list[str] = []
        arguments = argparse.Namespace(
            command="stage-evaluation", vault=self.vault,
            authorization_id="AUTH-EVAL-STAGE-1", account="one@example.test",
            selection_manifest=self.manifest, staging_dataset=self.stage_path,
        )

        def key_loader() -> bytearray:
            calls.append("key")
            return bytearray(b"E" * 32)

        with self.assertRaisesRegex(
            PrivateEvaluationError, "evaluation_stage_unavailable"
        ):
            execute_stage_evaluation_command(
                arguments,
                source_factory=lambda *_args, **_kwargs: calls.append("source"),
                key_loader=key_loader,
                stage_writer=lambda *_args: calls.append("writer"),
                path_validator=lambda _path: (_ for _ in ()).throw(
                    PrivateEvaluationError("evaluation_stage_unavailable")
                ),
                current_time=lambda: datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
                epoch_clock=lambda: 1_752_500_000,
                project_root=Path("C:/synthetic-project"),
            )
        self.assertEqual(calls, [])

        self.manifest.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(
            PrivateEvaluationError, "evaluation_stage_selection_invalid"
        ):
            execute_stage_evaluation_command(
                arguments,
                source_factory=lambda *_args, **_kwargs: calls.append("source"),
                key_loader=key_loader,
                stage_writer=lambda *_args: calls.append("writer"),
                path_validator=lambda path: path,
                current_time=lambda: datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
                epoch_clock=lambda: 1_752_500_000,
                project_root=Path("C:/synthetic-project"),
            )
        self.assertEqual(calls, [])

    def test_hidden_key_loader_accepts_only_exact_base64_32_bytes(self) -> None:
        prompts: list[str] = []
        encoded = base64.b64encode(b"E" * 32).decode("ascii")
        key = _load_stage_evaluation_key(
            getpass_fn=lambda prompt: prompts.append(prompt) or encoded
        )
        self.assertIs(type(key), bytearray)
        self.assertEqual(bytes(key), b"E" * 32)
        self.assertEqual(prompts, ["Private evaluation staging key (base64, hidden): "])

        for invalid in ("", "not-base64", base64.b64encode(b"short").decode("ascii")):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_key_unavailable"
            ) as caught:
                _load_stage_evaluation_key(getpass_fn=lambda _prompt, value=invalid: value)
            if invalid:
                self.assertNotIn(invalid, repr(caught.exception))

    def test_failure_output_is_fixed_and_never_contains_callback_detail(self) -> None:
        events: list[object] = []
        code = run_cli(
            self._argv(),
            dependencies=fake_dependencies(events),
            stage_evaluation_runner=lambda _arguments: (_ for _ in ()).throw(
                RuntimeError("SENSITIVE-CANARY")
            ),
        )
        self.assertEqual(code, 2)
        self.assertEqual(events, [("emit", {"ok": False, "code": "internal_error"})])
        self.assertNotIn("SENSITIVE-CANARY", repr(events))


if __name__ == "__main__":
    unittest.main()
