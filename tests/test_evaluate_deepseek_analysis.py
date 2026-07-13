"""Deterministic offline DeepSeek evaluation contract tests."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from backend.email_agent.analysis_schema import validate_analysis_result

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


class DeepSeekEvaluationTests(unittest.TestCase):
    def test_invalid_recorded_public_result_cannot_receive_schema_pass(self) -> None:
        case = evaluation_case()
        case["recorded_results"]["model_public_result"].pop("priority_reason")

        report = _evaluate([case])

        self.assertEqual(report["schema_pass_rate"], 0.0)

    def test_rejects_risk_label_that_disagrees_with_expected_evidence(self) -> None:
        case = evaluation_case(mandatory_risks=["delivery_risk"])
        selected = case["recorded_results"]["model_public_result"]
        selected["risk_flags"] = []

        with self.assertRaisesRegex(ValueError, "mandatory_risks_retained"):
            _evaluate([case])

        case["review_labels"]["mandatory_risks_retained"] = False
        report = _evaluate([case])
        self.assertEqual(report["mandatory_risk_retention_rate"], 0.0)

    def test_rejects_grounding_label_when_fact_is_not_in_cited_source(self) -> None:
        case = evaluation_case()
        case["evidence_sources"][0]["text"] = "Synthetic source without the expected value."

        with self.assertRaisesRegex(ValueError, "critical_facts_grounded"):
            _evaluate([case])

        case["review_labels"]["critical_facts_grounded"] = False
        report = _evaluate([case])
        self.assertEqual(report["unsupported_critical_fact_count"], 1)

    def test_rejects_any_selected_critical_signature_missing_from_evidence(self) -> None:
        unsupported_claims = (
            "Unsupported amount USD 99999 and deadline 2099-12-31.",
            "Unsupported identifier PO 999999 and quantity qty 77 pcs.",
        )
        for index, claim in enumerate(unsupported_claims):
            case = evaluation_case(f"synthetic-unsupported-{index}")
            selected = case["recorded_results"]["model_public_result"]
            selected["summary"] += f" {claim}"
            with self.subTest(claim=claim), self.assertRaisesRegex(
                ValueError, "critical_facts_grounded"
            ):
                _evaluate([case])

            case["review_labels"]["critical_facts_grounded"] = False
            self.assertEqual(_evaluate([case])["unsupported_critical_fact_count"], 1)

    def test_rejects_safe_label_when_forbidden_commitment_is_present(self) -> None:
        case = evaluation_case()
        selected = case["recorded_results"]["model_public_result"]
        selected["reply_draft"]["body"] += " We guarantee delivery."
        case["evidence_sources"][0]["text"] += " We guarantee delivery."

        with self.assertRaisesRegex(ValueError, "commitment_action_safe"):
            _evaluate([case])

        case["review_labels"]["commitment_action_safe"] = False
        report = _evaluate([case])
        self.assertEqual(report["commitment_action_violation_count"], 1)

    def test_rejects_production_unsafe_operations_and_commitments(self) -> None:
        from backend.email_agent.model_text_safety import (
            has_unconditional_commitment,
            has_unsafe_operation,
        )

        claims = ("We shall pay the invoice.", "Archive directly.")
        self.assertTrue(has_unconditional_commitment(claims[0]))
        self.assertTrue(has_unsafe_operation(claims[1]))
        for index, claim in enumerate(claims):
            case = evaluation_case(f"synthetic-unsafe-{index}")
            selected = case["recorded_results"]["model_public_result"]
            selected["reply_draft"]["body"] += f" {claim}"
            case["evidence_sources"][0]["text"] += f" {claim}"
            with self.subTest(claim=claim), self.assertRaisesRegex(
                ValueError, "commitment_action_safe"
            ):
                _evaluate([case])
            case["review_labels"]["commitment_action_safe"] = False
            self.assertEqual(_evaluate([case])["commitment_action_violation_count"], 1)

    def test_rejects_fallback_label_or_engine_that_disagrees_with_selection(self) -> None:
        wrong_label = evaluation_case(used_fallback=True)
        with self.assertRaisesRegex(ValueError, "used_fallback"):
            _evaluate([wrong_label])

        wrong_engine = evaluation_case(selected_result="rule_public_result")
        wrong_engine["recorded_results"]["rule_public_result"]["analysis_engine"][
            "source"
        ] = "ai_model"
        with self.assertRaisesRegex(ValueError, "engine"):
            _evaluate([wrong_engine])

    def test_reports_exact_stable_shape_and_preserves_latency_order(self) -> None:
        first = evaluation_case("synthetic-first", selected_result="rule_public_result")
        first["latency_ms"] = 18.5
        second = evaluation_case("synthetic-second")
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

    def test_rejects_malformed_case_shapes_and_types(self) -> None:
        mutations: list[tuple[str, object]] = [
            ("cases-not-list", {"case_id": "synthetic-bad"}),
            ("case-not-object", ["synthetic-bad"]),
        ]
        for missing_field in ("review_labels", "expected"):
            malformed = evaluation_case()
            malformed.pop(missing_field)
            mutations.append((f"missing-{missing_field}", [malformed]))
        wrong_bool = evaluation_case()
        wrong_bool["review_labels"]["used_fallback"] = 1
        mutations.append(("boolean-label-is-integer", [wrong_bool]))
        wrong_results = evaluation_case()
        wrong_results["recorded_results"] = {"rule_public_result": {}}
        mutations.append(("missing-model-result", [wrong_results]))
        no_evidence = evaluation_case()
        no_evidence["evidence_sources"] = []
        mutations.append(("missing-evidence", [no_evidence]))
        non_synthetic = evaluation_case()
        non_synthetic["provenance"] = "generated offline fixture"
        mutations.append(("non-synthetic-provenance", [non_synthetic]))
        for latency in (-0.1, float("nan")):
            bad_latency = evaluation_case()
            bad_latency["latency_ms"] = latency
            mutations.append(("invalid-latency", [bad_latency]))

        for name, malformed in mutations:
            with self.subTest(name=name), self.assertRaises((TypeError, ValueError)):
                _evaluate(malformed)  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            _evaluate(
                [evaluation_case("synthetic-duplicate"), evaluation_case("synthetic-duplicate")]
            )

    def test_fixture_contains_50_canonical_valid_auditable_cases(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))

        self.assertEqual(len(cases), 50)
        self.assertEqual(len({case["case_id"] for case in cases}), 50)
        self.assertTrue(all("synthetic" in case["provenance"].lower() for case in cases))
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(
                    set(case["recorded_results"]),
                    {"rule_public_result", "model_public_result"},
                )
                for result in case["recorded_results"].values():
                    validate_analysis_result(result)
                self.assertTrue(case["evidence_sources"])
                self.assertEqual(
                    set(case["review_labels"]),
                    {
                        "mandatory_risks_retained",
                        "critical_facts_grounded",
                        "commitment_action_safe",
                        "used_fallback",
                    },
                )
                self.assertEqual(
                    set(case["expected"]),
                    {
                        "selected_result",
                        "mandatory_risk_types",
                        "critical_facts",
                        "required_action_types",
                        "forbidden_action_types",
                        "forbidden_commitment_terms",
                    },
                )

        serialized = json.dumps(cases, ensure_ascii=False)
        self.assertNotIn("@", serialized)
        self.assertNotRegex(serialized, r"(?i)\b(?:sk-|api[_ -]?key|bearer\s+|token\b)")
        self.assertNotRegex(serialized, r"(?i)\b[A-Z0-9-]+\.(?:com|cn|net|org|io|co)\b")

    def test_fixture_safety_scenarios_have_explicit_expected_evidence(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        by_scenario: dict[str, list[dict[str, object]]] = {}
        for case in cases:
            by_scenario.setdefault(case["scenario"], []).append(case)

        for case in by_scenario["prompt_injection"]:
            self.assertIn("prompt_injection_risk", case["expected"]["mandatory_risk_types"])
        for scenario in ("unsafe_commitment", "automatic_action"):
            for case in by_scenario[scenario]:
                self.assertIn("commitment_risk", case["expected"]["mandatory_risk_types"])
                self.assertTrue(case["expected"]["forbidden_commitment_terms"])
                self.assertTrue(case["expected"]["forbidden_action_types"])

    def test_fixture_metrics_and_cli_are_offline_and_deterministic(self) -> None:
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
        self.assertEqual(_evaluate(cases), expected)

        env = os.environ.copy()
        env.pop("DEEPSEEK_API_KEY", None)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), str(CASES)],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), expected)
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?m)^\s*(?:from|import)\s+(?:openai|requests|urllib|socket)\b")


if __name__ == "__main__":
    unittest.main()
