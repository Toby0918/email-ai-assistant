"""Aggregate report and administrator-only private evaluation CLI tests."""

from __future__ import annotations

import base64
import copy
import json
import math
import tempfile
import unittest
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
        key = derive_selection_key(bytearray(b"C" * 32), self.dataset.dataset_namespace)
        self.selection = select_private_cases(self.dataset, key)
        self.path = Path("C:/SyntheticExternal/private.pkeval")
        self.report_path = Path("C:/SyntheticExternal/aggregate.json")
        self.events: list[str] = []
        self.emitted: list[dict[str, object]] = []
        self.key = bytearray(b"C" * 32)
        self.flash = FakeClient([envelope_json_for(case) for case in self.selection.selected])
        self.pro = FakeClient([envelope_json_for(case) for case in self.selection.paired])

    def dependencies(self, *, judge=lambda _view: True, configured=True):
        def key_loader():
            self.events.append("key")
            return self.key

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

        def client_factory(model):
            self.events.append("client:" + model)
            return self.flash if model == "deepseek-v4-flash" else self.pro

        def report_writer(report, path):
            self.events.append("report")
            self.assertEqual(path, self.report_path)
            self.assertIsInstance(report, AggregateReport)

        return SCRIPT.EvaluationCliDependencies(
            key_loader=key_loader, read_dataset=read_dataset,
            derive_selection_key=derive, select_cases=select,
            provider_configured=provider_configured, usefulness_judge=judge,
            client_factory=client_factory, report_writer=report_writer,
            emit=self.emitted.append,
        )

    def test_verify_is_local_only_and_never_checks_provider_or_constructs_client(self) -> None:
        code = SCRIPT.run_cli(
            ["verify", "--dataset", str(self.path)],
            dependencies=self.dependencies(),
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.events, ["key", "read", "derive", "select"])
        self.assertEqual(self.emitted, [{"ok": True, "code": "dataset_verified", "case_count": 200}])
        self.assertEqual(bytes(self.key), b"\x00" * 32)

    def test_wrong_confirmation_provider_or_missing_judge_stops_before_client_construction(self) -> None:
        cases = (
            ("WRONG", True, lambda _view: True, "operator_confirmation_required", False),
            ("I_CONFIRM_200_FLASH_40_PRO", False, lambda _view: True,
             "provider_configuration_unavailable", True),
            ("I_CONFIRM_200_FLASH_40_PRO", True, None, "human_judge_unavailable", True),
        )
        for confirmation, configured, judge, expected, provider_seen in cases:
            self.events.clear()
            self.emitted.clear()
            self.key[:] = b"C" * 32
            with self.subTest(expected=expected):
                code = SCRIPT.run_cli(
                    [
                        "run", "--dataset", str(self.path), "--report", str(self.report_path),
                        "--confirm-private-evaluation", confirmation,
                    ],
                    dependencies=self.dependencies(judge=judge, configured=configured),
                )
                self.assertEqual(code, 2)
                self.assertEqual(self.emitted[-1], {"ok": False, "code": expected})
                self.assertEqual(any(item.startswith("client:") for item in self.events), False)
                self.assertEqual("provider" in self.events, provider_seen)

    def test_successful_run_constructs_clients_only_after_local_preflight_and_writes_report(self) -> None:
        code = SCRIPT.run_cli(
            [
                "run", "--dataset", str(self.path), "--report", str(self.report_path),
                "--confirm-private-evaluation", "I_CONFIRM_200_FLASH_40_PRO",
            ],
            dependencies=self.dependencies(),
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.events[:5], ["key", "read", "derive", "select", "provider"])
        self.assertEqual(self.events[5:7], [
            "client:deepseek-v4-flash", "client:deepseek-v4-pro",
        ])
        self.assertEqual(self.events[-1], "report")
        self.assertEqual((self.flash.calls, self.pro.calls), (200, 40))
        self.assertEqual(self.emitted[-1], {
            "ok": True, "status_code": "comparison_complete",
            "decision_code": "retain_flash",
        })
        self.assertEqual(bytes(self.key), b"\x00" * 32)

    def test_parser_rejects_all_override_surfaces_before_key_or_other_side_effect(self) -> None:
        forbidden = (
            "--model", "--base-url", "--key", "--key-file", "--namespace",
            "--prompt", "--case-count", "--threshold", "--retry", "--stream",
            "--batch", "--force", "--switch-production",
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
