"""Aggregate report and administrator-only private evaluation CLI tests."""

from __future__ import annotations

import base64
import copy
import json
import math
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

from backend.private_evaluation.metrics import ModelMetrics
from backend.private_evaluation.reporting import (
    AggregateReport,
    PrivateEvaluationError,
    make_report,
    write_aggregate_report,
)
from backend.private_evaluation.schema import EvaluationDatasetV1
from backend.private_evaluation.selection import derive_selection_key, select_private_cases
from backend.private_evaluation.staging_repository import EvaluationStageV1
from tests.private_evaluation_fixtures import dataset_mapping, envelope_json_for
from tests.support import load_script_module


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = load_script_module(
    ROOT / "scripts" / "evaluate_private_deepseek.py",
    "evaluate_private_deepseek_test_module",
)


def perfect_metrics() -> ModelMetrics:
    return ModelMetrics(1.0, 0, 0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0)


def comparison_report() -> AggregateReport:
    metric = perfect_metrics()
    return make_report(
        status="comparison_complete", decision="retain_flash",
        flash_attempted=200, flash_completed=200,
        pro_attempted=40, pro_completed=40,
        flash_metrics=metric, pair_flash_metrics=metric, pro_metrics=metric,
    )


class AggregateReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / "aggregate.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_exact_shape_allowlists_and_atomic_write(self) -> None:
        report = comparison_report()
        write_aggregate_report(report, self.path)
        decoded = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(set(decoded), {
            "schema_version", "status_code", "models", "counts", "metrics",
            "error_code_counts", "decision_code",
        })
        self.assertEqual(decoded["models"], {
            "flash": "deepseek-v4-flash", "pro": "deepseek-v4-pro",
        })
        self.assertNotIn("prompt", self.path.read_text(encoding="utf-8").lower())
        self.assertEqual(AggregateReport.from_mapping(decoded).to_mapping(), decoded)
        self.assertEqual(tuple(self.root.glob(".*.tmp")), ())

    def test_unknown_strings_bool_counts_nonfinite_numbers_and_nested_extra_fail_closed(self) -> None:
        base = comparison_report().to_mapping()
        mutations = []
        value = copy.deepcopy(base)
        value["status_code"] = "prompt-current-request"
        mutations.append(value)
        value = copy.deepcopy(base)
        value["counts"]["flash_attempted"] = True
        mutations.append(value)
        value = copy.deepcopy(base)
        value["metrics"]["flash"]["p95_seconds"] = math.nan
        mutations.append(value)
        value = copy.deepcopy(base)
        value["error_code_counts"]["raw_response"] = 1
        mutations.append(value)
        value = copy.deepcopy(base)
        value["metrics"]["flash"]["sample"] = "Current request"
        mutations.append(value)
        value = copy.deepcopy(base)
        value["case_id"] = "11111111-2222-4333-8444-555555555555"
        mutations.append(value)

        for mapping in mutations:
            with self.subTest(keys=tuple(mapping)), self.assertRaisesRegex(
                PrivateEvaluationError, "aggregate_serialization_violation"
            ) as caught:
                AggregateReport.from_mapping(mapping)
            self.assertNotIn("Current request", repr(caught.exception))

    def test_failed_replace_preserves_previous_report_and_removes_stage(self) -> None:
        self.path.write_text('{"previous":true}', encoding="utf-8")
        with patch(
            "backend.private_evaluation.reporting.os.replace",
            side_effect=OSError("private path detail"),
        ), self.assertRaisesRegex(
            PrivateEvaluationError, "aggregate_serialization_violation"
        ) as caught:
            write_aggregate_report(comparison_report(), self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), '{"previous":true}')
        self.assertEqual(tuple(self.root.glob(".*.tmp")), ())
        self.assertNotIn("private path detail", repr(caught.exception))


class FakeClient:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = 0

    def __call__(self, _prompt: str, **_options: object) -> str:
        value = self.outputs[self.calls]
        self.calls += 1
        return value


class PrivateEvaluationCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = EvaluationDatasetV1.from_mapping(dataset_mapping())
        self.stage = EvaluationStageV1.from_mapping({
            "schema_version": "PrivateEvaluationStageV1",
            "stage_namespace": "00000000-0000-4000-8000-000000000777",
            "cases": dataset_mapping()["cases"],
        })
        key = derive_selection_key(bytearray(b"C" * 32), self.dataset.dataset_namespace)
        self.selection = select_private_cases(self.dataset, key)
        self.stage_path = Path("C:/SyntheticExternal/stage/private.pkevalstage")
        self.path = Path("C:/SyntheticExternal/private.pkeval")
        self.report_path = Path("C:/SyntheticExternal/aggregate.json")
        self.events: list[str] = []
        self.emitted: list[dict[str, object]] = []
        self.key = bytearray(b"C" * 32)
        self.flash = FakeClient([envelope_json_for(case) for case in self.selection.selected])
        self.pro = FakeClient([envelope_json_for(case) for case in self.selection.paired])
        self.written_reports: list[AggregateReport] = []

    def dependencies(
        self,
        *,
        judge=lambda _view: True,
        configured=True,
        terminal=True,
        readiness_error: BaseException | None = None,
        key_error: Exception | None = None,
        stage_error: Exception | None = None,
    ):
        required = {
            "key_loader", "read_stage", "build_dataset", "write_dataset",
            "read_dataset", "derive_selection_key", "select_cases",
            "terminal_available", "readiness_check", "judge_factory", "provider_configured",
            "client_factory", "report_writer", "emit",
        }
        actual = {item.name for item in fields(SCRIPT.EvaluationCliDependencies)}
        self.assertTrue(required.issubset(actual), sorted(required - actual))

        def key_loader():
            self.events.append("key")
            if key_error is not None:
                raise key_error
            return self.key

        def read_stage(path, key):
            self.events.append("stage-read")
            self.assertEqual(path, self.stage_path)
            self.assertEqual(bytes(key), b"C" * 32)
            if stage_error is not None:
                raise stage_error
            return self.stage

        def build_dataset(stage):
            self.events.append("build")
            self.assertIs(stage, self.stage)
            return self.dataset

        def write_dataset(path, dataset, key):
            self.events.append("dataset-write")
            self.assertEqual(path, self.path)
            self.assertIs(dataset, self.dataset)
            self.assertEqual(bytes(key), b"C" * 32)

        def read_dataset(path, key):
            self.events.append("read")
            self.assertEqual(path, self.path)
            self.assertEqual(bytes(key), b"C" * 32)
            return self.dataset

        def derive(key, namespace):
            self.events.append("derive")
            return derive_selection_key(key, namespace)

        def select(dataset, key):
            self.events.append("select")
            return select_private_cases(dataset, key)

        def provider_configured():
            self.events.append("provider")
            return configured

        def terminal_available():
            self.events.append("tty")
            return terminal

        def readiness_check():
            self.events.append("readiness")
            if readiness_error is not None:
                raise readiness_error

        def judge_factory():
            self.events.append("judge")
            return judge

        def client_factory(model):
            self.events.append("client:" + model)
            return self.flash if model == "deepseek-v4-flash" else self.pro

        def report_writer(report, path):
            self.events.append("report")
            self.assertEqual(path, self.report_path)
            self.assertIsInstance(report, AggregateReport)
            self.written_reports.append(report)

        return SCRIPT.EvaluationCliDependencies(
            key_loader=key_loader, read_stage=read_stage,
            build_dataset=build_dataset, write_dataset=write_dataset,
            read_dataset=read_dataset,
            derive_selection_key=derive, select_cases=select,
            terminal_available=terminal_available, readiness_check=readiness_check,
            judge_factory=judge_factory,
            provider_configured=provider_configured,
            client_factory=client_factory, report_writer=report_writer,
            emit=self.emitted.append,
        )

    def test_build_reads_stage_validates_selection_and_writes_without_provider_or_judge(self) -> None:
        code = SCRIPT.run_cli(
            ["build", "--staging", str(self.stage_path), "--dataset", str(self.path)],
            dependencies=self.dependencies(),
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            self.events,
            ["key", "stage-read", "build", "derive", "select", "dataset-write"],
        )
        self.assertEqual(self.emitted, [{
            "ok": True, "code": "dataset_built", "case_count": 200,
        }])
        self.assertEqual(bytes(self.key), b"\x00" * 32)

    def test_build_stage_failure_is_fixed_content_free_and_writes_nothing(self) -> None:
        stage_detail = "SENSITIVE-STAGE-DETAIL"
        code = SCRIPT.run_cli(
            ["build", "--staging", str(self.stage_path), "--dataset", str(self.path)],
            dependencies=self.dependencies(
                stage_error=PrivateEvaluationError("evaluation_stage_decrypt_invalid")
            ),
        )
        self.assertEqual(code, 2)
        self.assertEqual(self.events, ["key", "stage-read"])
        self.assertEqual(self.emitted, [{
            "ok": False, "code": "evaluation_stage_decrypt_invalid",
        }])
        self.assertNotIn(stage_detail, json.dumps(self.emitted))
        self.assertEqual(bytes(self.key), b"\x00" * 32)

    def test_verify_is_local_only_and_never_checks_provider_or_constructs_client(self) -> None:
        code = SCRIPT.run_cli(
            ["verify", "--dataset", str(self.path)],
            dependencies=self.dependencies(),
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.events, ["key", "read", "derive", "select"])
        self.assertEqual(self.emitted, [{"ok": True, "code": "dataset_verified", "case_count": 200}])
        self.assertEqual(bytes(self.key), b"\x00" * 32)

    def test_run_requires_flag_confirmation_and_tty_before_hidden_key(self) -> None:
        cases = (
            ([], "human_judge_unavailable", []),
            (["--interactive-judge"], "operator_confirmation_required", []),
            (["--interactive-judge", "--confirm-private-evaluation", "WRONG"],
             "operator_confirmation_required", []),
            (["--interactive-judge", "--confirm-private-evaluation",
              "I_CONFIRM_200_FLASH_40_PRO"], "human_judge_unavailable", ["tty"]),
        )
        for extra, expected, expected_events in cases:
            self.events.clear()
            self.emitted.clear()
            self.key[:] = b"C" * 32
            with self.subTest(expected=expected):
                arguments = [
                    "run", "--dataset", str(self.path), "--report", str(self.report_path),
                ] + extra
                code = SCRIPT.run_cli(
                    arguments,
                    dependencies=self.dependencies(terminal=expected != "human_judge_unavailable" or not expected_events),
                )
                self.assertEqual(code, 2)
                self.assertEqual(self.emitted[-1], {"ok": False, "code": expected})
                self.assertEqual(self.events, expected_events)

    def test_key_eof_judge_unavailable_and_provider_config_stop_before_clients(self) -> None:
        arguments = [
            "run", "--dataset", str(self.path), "--report", str(self.report_path),
            "--confirm-private-evaluation", "I_CONFIRM_200_FLASH_40_PRO",
            "--interactive-judge",
        ]
        cases = (
            ({"key_error": EOFError("SENSITIVE-EOF")}, "evaluation_key_unavailable",
             ["tty", "readiness", "key"]),
            ({"judge": None}, "human_judge_unavailable",
             ["tty", "readiness", "key", "read", "derive", "select", "judge"]),
            ({"configured": False}, "provider_configuration_unavailable",
             ["tty", "readiness", "key", "read", "derive", "select", "judge", "provider"]),
        )
        for options, expected, expected_events in cases:
            self.events.clear()
            self.emitted.clear()
            self.key[:] = b"C" * 32
            with self.subTest(expected=expected):
                code = SCRIPT.run_cli(
                    arguments, dependencies=self.dependencies(**options)
                )
                self.assertEqual(code, 2)
                self.assertEqual(self.emitted, [{"ok": False, "code": expected}])
                self.assertEqual(self.events, expected_events)
                self.assertFalse(any(item.startswith("client:") for item in self.events))

    def test_successful_run_constructs_clients_only_after_local_preflight_and_writes_report(self) -> None:
        code = SCRIPT.run_cli(
            [
                "run", "--dataset", str(self.path), "--report", str(self.report_path),
                "--confirm-private-evaluation", "I_CONFIRM_200_FLASH_40_PRO",
                "--interactive-judge",
            ],
            dependencies=self.dependencies(),
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.events[:8], [
            "tty", "readiness", "key", "read", "derive", "select", "judge", "provider",
        ])
        self.assertEqual(self.events[8:10], [
            "client:deepseek-v4-flash", "client:deepseek-v4-pro",
        ])
        self.assertEqual(self.events[-1], "report")
        self.assertEqual((self.flash.calls, self.pro.calls), (200, 40))
        self.assertEqual(self.emitted[-1], {
            "ok": True, "status_code": "comparison_complete",
            "decision_code": "retain_flash",
        })
        self.assertEqual(bytes(self.key), b"\x00" * 32)

    def test_readiness_eof_cancel_and_invalid_input_stop_before_key_or_clients(self) -> None:
        arguments = [
            "run", "--dataset", str(self.path), "--report", str(self.report_path),
            "--confirm-private-evaluation", "I_CONFIRM_200_FLASH_40_PRO",
            "--interactive-judge",
        ]
        for failure in (
            EOFError("synthetic-readiness-eof"),
            KeyboardInterrupt(),
            PrivateEvaluationError("human_judge_failed"),
        ):
            self.events.clear()
            self.emitted.clear()
            with self.subTest(failure=type(failure).__name__):
                code = SCRIPT.run_cli(
                    arguments,
                    dependencies=self.dependencies(readiness_error=failure),
                )
                self.assertEqual(code, 2)
                self.assertEqual(self.events, ["tty", "readiness"])
                self.assertEqual(self.emitted, [{
                    "ok": False, "code": "human_judge_failed",
                }])
                self.assertFalse(any(item.startswith("client:") for item in self.events))

    def test_judge_failure_stops_before_the_next_provider_call_and_is_aggregate_only(self) -> None:
        code = SCRIPT.run_cli(
            [
                "run", "--dataset", str(self.path), "--report", str(self.report_path),
                "--confirm-private-evaluation", "I_CONFIRM_200_FLASH_40_PRO",
                "--interactive-judge",
            ],
            dependencies=self.dependencies(
                judge=lambda _view: (_ for _ in ()).throw(EOFError("SENSITIVE-EOF"))
            ),
        )
        self.assertEqual(code, 0)
        self.assertEqual((self.flash.calls, self.pro.calls), (1, 0))
        self.assertEqual(len(self.written_reports), 1)
        report = self.written_reports[0]
        self.assertEqual(report.error_code_counts, {"human_judge_failed": 1})
        rendered = json.dumps(report.to_mapping(), sort_keys=True)
        self.assertNotIn("SENSITIVE-EOF", rendered)
        self.assertNotIn("case_id", rendered)

    def test_parser_rejects_all_override_surfaces_before_key_or_other_side_effect(self) -> None:
        forbidden = (
            "--model", "--base-url", "--key", "--key-file", "--namespace",
            "--prompt", "--case-count", "--threshold", "--retry", "--stream",
            "--batch", "--force", "--overwrite", "--switch-production",
            "--transcript", "--export", "--save", "--output",
        )
        for option in forbidden:
            self.events.clear()
            self.emitted.clear()
            with self.subTest(option=option):
                code = SCRIPT.run_cli(
                    ["verify", "--dataset", str(self.path), option, "x"],
                    dependencies=self.dependencies(),
                )
                self.assertEqual(code, 2)
                self.assertEqual(self.events, [])
                self.assertEqual(self.emitted, [{"ok": False, "code": "argument_invalid"}])

        for arguments in (
            ["build", "--staging", str(self.stage_path), "--dataset", str(self.path), "--force"],
            ["run", "--dataset", str(self.path), "--report", str(self.report_path),
             "--confirm-private-evaluation", "I_CONFIRM_200_FLASH_40_PRO",
             "--interactive-judge", "--transcript", "x"],
        ):
            self.events.clear()
            self.emitted.clear()
            code = SCRIPT.run_cli(arguments, dependencies=self.dependencies())
            self.assertEqual(code, 2)
            self.assertEqual(self.events, [])
            self.assertEqual(self.emitted, [{"ok": False, "code": "argument_invalid"}])

    def test_hidden_base64_key_loader_accepts_exact_32_bytes_and_uses_fixed_errors(self) -> None:
        encoded = base64.b64encode(b"Z" * 32).decode("ascii")
        key = SCRIPT._load_live_key(getpass_fn=lambda _prompt: encoded)
        self.assertIsInstance(key, bytearray)
        self.assertEqual(bytes(key), b"Z" * 32)
        for raw in ("not-base64", base64.b64encode(b"short").decode("ascii")):
            with self.subTest(raw=raw), self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_key_unavailable"
            ) as caught:
                SCRIPT._load_live_key(getpass_fn=lambda _prompt, raw=raw: raw)
            self.assertNotIn(raw, repr(caught.exception))


if __name__ == "__main__":
    unittest.main()
