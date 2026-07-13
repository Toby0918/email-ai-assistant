"""Deterministic production-path DeepSeek evaluation contract tests."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.email_agent.analysis_schema import validate_analysis_result
from backend.email_agent.deepseek_analysis_schema import parse_deepseek_analysis_v1
from backend.email_agent.model_text_safety import (
    has_unconditional_commitment,
    has_unsafe_operation,
    validate_public_language,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deepseek_eval_support import evaluation_case  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "deepseek_eval" / "cases.json"
SCRIPT = ROOT / "scripts" / "evaluate_deepseek_analysis.py"
REPORT_KEYS = [
    "case_count",
    "schema_pass_rate",
    "mandatory_risk_retention_rate",
    "unsupported_critical_fact_count",
    "commitment_action_violation_count",
    "fallback_rate",
    "latency_samples_ms",
]


def _evaluate(cases: list[dict[str, object]]) -> dict[str, object]:
    from scripts.evaluate_deepseek_analysis import evaluate_cases

    return evaluate_cases(cases)


def _replay(case: dict[str, object]):
    from scripts.deepseek_eval_replay import replay_case

    return replay_case(case)


class DeepSeekEvaluationTests(unittest.TestCase):
    def test_case_is_replayed_through_production_parser_evidence_and_merge(self) -> None:
        from backend.email_agent import analysis_model_routes as routes

        cases = [
            evaluation_case("synthetic-safe"),
            evaluation_case(
                "synthetic-evidence", provider_case="evidence_failure",
                analysis_source="rule_fallback", required_actions=["reply"],
            ),
            evaluation_case(
                "synthetic-malformed", provider_case="malformed_json",
                analysis_source="rule_fallback", required_actions=["reply"],
            ),
        ]
        with patch.object(
            routes, "parse_deepseek_analysis_v1",
            wraps=routes.parse_deepseek_analysis_v1,
        ) as parser, patch.object(
            routes, "validate_envelope_evidence",
            wraps=routes.validate_envelope_evidence,
        ) as evidence, patch.object(
            routes, "merge_deepseek_analysis_v1",
            wraps=routes.merge_deepseek_analysis_v1,
        ) as merge:
            report = _evaluate(cases)

        self.assertEqual(report["case_count"], 3)
        self.assertEqual(parser.call_count, 3)
        self.assertEqual(evidence.call_count, 2)
        self.assertEqual(merge.call_count, 1)

    def test_accepted_model_result_is_valid_bilingual_and_distinct_from_rule(self) -> None:
        outcome = _replay(evaluation_case("synthetic-model"))

        self.assertEqual(outcome.result["analysis_engine"]["source"], "ai_model")
        validate_analysis_result(outcome.result)
        validate_public_language(outcome.result)
        self.assertNotEqual(
            {key: value for key, value in outcome.result.items() if key != "analysis_engine"},
            {key: value for key, value in outcome.baseline.items() if key != "analysis_engine"},
        )

    def test_fallback_is_observed_from_actual_engine_not_provider_case_flag(self) -> None:
        wrong_expectation = evaluation_case(
            "synthetic-wrong-expectation", analysis_source="rule_fallback"
        )

        with self.assertRaisesRegex(ValueError, "analysis_source"):
            _evaluate([wrong_expectation])

    def test_expected_risks_and_actions_do_not_generate_provider_output(self) -> None:
        case = evaluation_case(
            "synthetic-independent-expectations",
            mandatory_risks=["delivery_risk"],
            required_actions=["check_delivery"],
        )

        report = _evaluate([case])

        self.assertEqual(report["mandatory_risk_retention_rate"], 0.0)
        self.assertEqual(report["commitment_action_violation_count"], 1)

    def test_scenario_labels_materialize_real_untrusted_inputs_and_evidence(self) -> None:
        from scripts.deepseek_eval_replay import build_synthetic_email

        long_case = evaluation_case(
            "synthetic-long-thread", scenario="long_thread",
            required_actions=["reply"],
        )
        long_email = build_synthetic_email(long_case)
        self.assertEqual(len(long_email["thread_segments"]), 3)
        self.assertIn(long_case["fact"], long_email["thread_segments"][0]["body_text"])
        long_outcome = _replay(long_case)
        self.assertIn(long_case["fact"], long_outcome.evidence_sources["thread:0"])
        self.assertNotEqual(
            long_outcome.result["conversation_timeline"]["current_status"], "unknown"
        )

        injection_case = evaluation_case(
            "synthetic-prompt-injection", scenario="prompt_injection",
            mandatory_risks=["prompt_injection_risk"], required_actions=["escalate"],
        )
        injection_email = build_synthetic_email(injection_case)
        self.assertIn("ignore previous instructions", injection_email["body_text"].lower())
        injection_outcome = _replay(injection_case)
        self.assertIn(
            "prompt_injection_risk",
            {risk["type"] for risk in injection_outcome.result["risk_flags"]},
        )

        attachment_types = {
            "image_attachment": "image",
            "pdf_attachment": "pdf",
            "xlsx_attachment": "xlsx",
            "docx_attachment": "docx",
            "missing_attachment": "pdf",
        }
        for scenario, attachment_type in attachment_types.items():
            case = evaluation_case(f"synthetic-{scenario}", scenario=scenario)
            email = build_synthetic_email(case)
            outcome = _replay(case)
            with self.subTest(scenario=scenario):
                self.assertEqual(email["attachments"][0]["type"], attachment_type)
                self.assertEqual(
                    email["resource_limitations"][0]["type"], attachment_type
                )
                self.assertTrue(any(
                    insight["type"] == attachment_type
                    and insight["status"] == "unavailable"
                    for insight in outcome.result["attachment_insights"]
                ))

    def test_material_distinction_excludes_engine_tags_and_review_only_metadata(self) -> None:
        from scripts.evaluate_deepseek_analysis import _materially_distinct

        baseline = _replay(evaluation_case("synthetic-distinction-baseline")).baseline
        tag_only = copy.deepcopy(baseline)
        tag_only["tags"].append("model-only")
        tag_only["analysis_engine"] = {"source": "ai_model", "label": "synthetic"}
        review_only = copy.deepcopy(baseline)
        review_only["reply_draft"]["review_reasons"].append("model-only review note")
        review_only["analysis_engine"] = {"source": "ai_model", "label": "synthetic"}
        substantive = copy.deepcopy(baseline)
        substantive["summary"] = "模型补充了可操作的当前邮件摘要。"

        self.assertFalse(_materially_distinct(tag_only, baseline))
        self.assertFalse(_materially_distinct(review_only, baseline))
        self.assertTrue(_materially_distinct(substantive, baseline))

    def test_raw_failure_envelopes_drive_actual_rule_fallback(self) -> None:
        from scripts.deepseek_eval_replay import render_provider_output

        markers = {
            "automatic_action": "自动归档",
            "passive_commitment": "The price is guaranteed at USD 100 for PO 101.",
            "unsupported_fact": "PO 999999",
            "malformed_json": "not-json",
            "evidence_failure": "unknown:source",
        }
        for provider_case, marker in markers.items():
            case = evaluation_case(
                f"synthetic-{provider_case}", provider_case=provider_case,
                analysis_source="rule_fallback", required_actions=["reply"],
            )
            outcome = _replay(case)
            raw = render_provider_output(case, outcome.baseline)
            with self.subTest(provider_case=provider_case):
                self.assertIn(marker, raw)
                self.assertEqual(
                    outcome.result["analysis_engine"]["source"], "rule_fallback"
                )
                self.assertEqual(outcome.result, outcome.baseline)
                self.assertFalse(has_unsafe_operation(json.dumps(outcome.result)))
                self.assertFalse(
                    has_unconditional_commitment(json.dumps(outcome.result))
                )

    def test_raw_accepted_envelope_is_private_json_not_public_fixture(self) -> None:
        from scripts.deepseek_eval_replay import render_provider_output

        case = evaluation_case("synthetic-private", fact="PO 3101")
        outcome = _replay(case)
        raw = render_provider_output(case, outcome.baseline)
        envelope = parse_deepseek_analysis_v1(raw)

        self.assertEqual(envelope["schema_version"], "deepseek_analysis_v1")
        self.assertIn("field_evidence", envelope)
        self.assertNotIn("analysis_engine", raw)

    def test_reports_exact_stable_shape_and_preserves_latency_order(self) -> None:
        first = evaluation_case("synthetic-first")
        first["latency_ms"] = 18.5
        second = evaluation_case(
            "synthetic-second", provider_case="malformed_json",
            analysis_source="rule_fallback", required_actions=["reply"],
        )
        third = evaluation_case("synthetic-third")
        third["latency_ms"] = 0
        cases = [first, second, third]
        before = copy.deepcopy(cases)

        report = _evaluate(cases)

        self.assertEqual(list(report), REPORT_KEYS)
        self.assertEqual(report["fallback_rate"], 1 / 3)
        self.assertEqual(report["latency_samples_ms"], [18.5, 0.0])
        self.assertEqual(cases, before)
        self.assertEqual(_evaluate(cases), report)

    def test_empty_input_has_null_rates_zero_counts_and_no_latency(self) -> None:
        report = _evaluate([])

        self.assertEqual(list(report), REPORT_KEYS)
        self.assertEqual(report["case_count"], 0)
        self.assertIsNone(report["schema_pass_rate"])
        self.assertIsNone(report["mandatory_risk_retention_rate"])
        self.assertEqual(report["unsupported_critical_fact_count"], 0)
        self.assertEqual(report["commitment_action_violation_count"], 0)
        self.assertIsNone(report["fallback_rate"])
        self.assertEqual(report["latency_samples_ms"], [])

    def test_rejects_malformed_case_shapes_types_and_duplicates(self) -> None:
        mutations: list[tuple[str, object]] = [
            ("cases-not-list", {"case_id": "synthetic-bad"}),
            ("case-not-object", ["synthetic-bad"]),
        ]
        for missing_field in ("provider_case", "expected"):
            malformed = evaluation_case()
            malformed.pop(missing_field)
            mutations.append((f"missing-{missing_field}", [malformed]))
        non_synthetic = evaluation_case()
        non_synthetic["provenance"] = "generated offline fixture"
        mutations.append(("non-synthetic-provenance", [non_synthetic]))
        bad_source = evaluation_case()
        bad_source["expected"]["analysis_source"] = "fixture_selected"
        mutations.append(("invalid-source", [bad_source]))
        for latency in (-0.1, float("nan")):
            bad_latency = evaluation_case()
            bad_latency["latency_ms"] = latency
            mutations.append(("invalid-latency", [bad_latency]))

        for name, malformed in mutations:
            with self.subTest(name=name), self.assertRaises((TypeError, ValueError)):
                _evaluate(malformed)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            _evaluate([
                evaluation_case("synthetic-duplicate"),
                evaluation_case("synthetic-duplicate"),
            ])

    def test_fixture_contains_50_compact_synthetic_replay_cases(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))

        self.assertEqual(len(cases), 50)
        self.assertEqual(len({case["case_id"] for case in cases}), 50)
        self.assertTrue(all("synthetic" in case["provenance"].lower() for case in cases))
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                self.assertNotIn("recorded_results", case)
                self.assertNotIn("selected_result", json.dumps(case))
                self.assertIn(case["provider_case"], {
                    "accepted", "automatic_action", "passive_commitment",
                    "unsupported_fact", "malformed_json", "evidence_failure",
                })
                self.assertIn(case["expected"]["analysis_source"], {
                    "ai_model", "rule_fallback",
                })

        serialized = json.dumps(cases, ensure_ascii=False)
        self.assertNotIn("@", serialized)
        self.assertNotRegex(serialized, r"(?i)\b(?:sk-|api[_ -]?key|bearer\s+|token\b)")
        self.assertNotRegex(serialized, r"(?i)\b[A-Z0-9-]+\.(?:com|cn|net|org|io|co)\b")

    def test_fixture_metrics_cli_and_route_counts_are_offline_deterministic(self) -> None:
        from backend.email_agent import analysis_model_routes as routes

        cases = json.loads(CASES.read_text(encoding="utf-8"))
        expected = {
            "case_count": 50,
            "schema_pass_rate": 1.0,
            "mandatory_risk_retention_rate": 1.0,
            "unsupported_critical_fact_count": 0,
            "commitment_action_violation_count": 0,
            "fallback_rate": 0.2,
            "latency_samples_ms": [100.0, 101.0, 102.0, 103.0, 104.0],
        }
        with patch.object(
            routes, "parse_deepseek_analysis_v1",
            wraps=routes.parse_deepseek_analysis_v1,
        ) as parser, patch.object(
            routes, "generate_analysis", side_effect=AssertionError("network path used")
        ):
            self.assertEqual(_evaluate(cases), expected)
        self.assertEqual(parser.call_count, 50)

        env = os.environ.copy()
        env.pop("DEEPSEEK_API_KEY", None)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), str(CASES)], cwd=ROOT, env=env,
            check=False, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), expected)
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SCRIPT, ROOT / "scripts" / "deepseek_eval_replay.py")
            if path.exists()
        )
        self.assertNotRegex(
            sources, r"(?m)^\s*(?:from|import)\s+(?:openai|requests|urllib|socket)\b"
        )


if __name__ == "__main__":
    unittest.main()
