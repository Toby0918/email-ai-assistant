"""Evaluate recorded synthetic DeepSeek analysis results without network access."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.email_agent.analysis_schema import (  # noqa: E402
    ACTION_TYPES,
    RISK_TYPES,
    AnalysisValidationError,
    validate_analysis_result,
)
# Intentional private import: the offline gate must share production normalization.
from backend.email_agent.model_grounding import _critical_signatures  # noqa: E402
from backend.email_agent.model_text_safety import has_unconditional_commitment, has_unsafe_operation  # noqa: E402
DEFAULT_CASES = ROOT / "tests" / "fixtures" / "deepseek_eval" / "cases.json"
CASE_FIELDS = {
    "case_id",
    "provenance",
    "scenario",
    "recorded_results",
    "evidence_sources",
    "expected",
    "review_labels",
}
OPTIONAL_CASE_FIELDS = {"latency_ms"}
RESULT_FIELDS = {"rule_public_result", "model_public_result"}
RESULT_SOURCES = {
    "rule_public_result": "rule_fallback",
    "model_public_result": "ai_model",
}
EVIDENCE_FIELDS = {"source_id", "text"}
EXPECTED_FIELDS = {
    "selected_result",
    "mandatory_risk_types",
    "critical_facts",
    "required_action_types",
    "forbidden_action_types",
    "forbidden_commitment_terms",
}
CRITICAL_FACT_FIELDS = {"value", "source_id"}
REVIEW_FIELDS = {
    "mandatory_risks_retained",
    "critical_facts_grounded",
    "commitment_action_safe",
    "used_fallback",
}
def evaluate_cases(cases: list[dict[str, object]]) -> dict[str, object]:
    """Validate cases and return the stable offline quality report."""
    metrics = _validate_cases(cases)
    count = len(metrics)
    return {
        "case_count": count,
        "schema_pass_rate": _ratio(metrics, "schema_passed"),
        "mandatory_risk_retention_rate": _ratio(
            metrics, "mandatory_risks_retained"
        ),
        "unsupported_critical_fact_count": _count_false(
            metrics, "critical_facts_grounded"
        ),
        "commitment_action_violation_count": _count_false(
            metrics, "commitment_action_safe"
        ),
        "fallback_rate": _ratio(metrics, "used_fallback"),
        "latency_samples_ms": [
            float(case["latency_ms"])
            for case in metrics
            if "latency_ms" in case
        ],
    }
def _validate_cases(cases: object) -> list[dict[str, Any]]:
    if type(cases) is not list:
        raise TypeError("Evaluation cases must be a list.")
    metrics: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        checked = _validate_case(case, index)
        case_id = checked["case_id"]
        if case_id in seen_ids:
            raise ValueError(f"Duplicate evaluation case_id: {case_id}.")
        seen_ids.add(case_id)
        metrics.append(checked)
    return metrics
def _validate_case(case: object, index: int) -> dict[str, Any]:
    if type(case) is not dict:
        raise TypeError(f"Evaluation case {index} must be an object.")
    fields = set(case)
    if fields - CASE_FIELDS - OPTIONAL_CASE_FIELDS or not CASE_FIELDS <= fields:
        raise ValueError(f"Evaluation case {index} has an invalid field set.")
    case_id = _require_text(case["case_id"], f"case {index} case_id")
    provenance = _require_text(case["provenance"], f"case {index} provenance")
    if "synthetic" not in provenance.casefold():
        raise ValueError(f"Evaluation case {index} must have synthetic provenance.")
    _require_text(case["scenario"], f"case {index} scenario")
    results, schema_passed = _validate_recorded_results(case["recorded_results"], index)
    evidence = _validate_evidence(case["evidence_sources"], index)
    expected = _validate_expected(case["expected"], index)
    labels = _validate_review_labels(case["review_labels"], index)
    derived = _derive_labels(results, evidence, expected)
    _crosscheck_labels(labels, derived, index)
    metrics: dict[str, Any] = {
        "case_id": case_id,
        "schema_passed": schema_passed,
        **derived,
    }
    if "latency_ms" in case:
        _validate_latency(case["latency_ms"], index)
        metrics["latency_ms"] = case["latency_ms"]
    return metrics
def _validate_recorded_results(
    value: object, index: int
) -> tuple[dict[str, dict[str, Any]], bool]:
    if type(value) is not dict or set(value) != RESULT_FIELDS:
        raise ValueError(f"Evaluation case {index} needs rule and model results.")
    schema_passed = True
    for result_name, expected_source in RESULT_SOURCES.items():
        result = value[result_name]
        if type(result) is not dict or not result:
            raise TypeError(f"Evaluation case {index} {result_name} must be an object.")
        engine = result.get("analysis_engine")
        if type(engine) is not dict or engine.get("source") != expected_source:
            raise ValueError(
                f"Evaluation case {index} {result_name} has invalid engine evidence."
            )
        try:
            validate_analysis_result(result)
        except AnalysisValidationError:
            schema_passed = False
    return value, schema_passed


def _validate_evidence(value: object, index: int) -> dict[str, str]:
    if type(value) is not list or not value:
        raise ValueError(f"Evaluation case {index} needs evidence sources.")
    sources: dict[str, str] = {}
    for evidence in value:
        if type(evidence) is not dict or set(evidence) != EVIDENCE_FIELDS:
            raise ValueError(f"Evaluation case {index} has invalid evidence shape.")
        source_id = _require_text(evidence["source_id"], f"case {index} source_id")
        text = _require_text(evidence["text"], f"case {index} evidence text")
        if "synthetic" not in f"{source_id} {text}".casefold():
            raise ValueError(f"Evaluation case {index} evidence must be synthetic.")
        if source_id in sources:
            raise ValueError(f"Evaluation case {index} has duplicate evidence source_id.")
        sources[source_id] = text
    return sources


def _validate_expected(value: object, index: int) -> dict[str, Any]:
    if type(value) is not dict or set(value) != EXPECTED_FIELDS:
        raise ValueError(f"Evaluation case {index} has invalid expected evidence.")
    if value["selected_result"] not in RESULT_FIELDS:
        raise ValueError(f"Evaluation case {index} has invalid selected_result.")
    _validate_text_list(value["mandatory_risk_types"], f"case {index} risks", RISK_TYPES)
    _validate_text_list(
        value["required_action_types"], f"case {index} required actions", ACTION_TYPES, True
    )
    _validate_text_list(
        value["forbidden_action_types"], f"case {index} forbidden actions", ACTION_TYPES, True
    )
    _validate_text_list(
        value["forbidden_commitment_terms"], f"case {index} forbidden terms", None, True
    )
    facts = value["critical_facts"]
    if type(facts) is not list or not facts:
        raise ValueError(f"Evaluation case {index} needs critical facts.")
    for fact in facts:
        if type(fact) is not dict or set(fact) != CRITICAL_FACT_FIELDS:
            raise ValueError(f"Evaluation case {index} has invalid critical fact.")
        _require_text(fact["value"], f"case {index} critical fact value")
        _require_text(fact["source_id"], f"case {index} critical fact source_id")
    return value


def _validate_text_list(
    value: object,
    label: str,
    allowed: set[str] | None,
    required: bool = False,
) -> None:
    if type(value) is not list or (required and not value):
        raise TypeError(f"Evaluation {label} must be a valid list.")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise TypeError(f"Evaluation {label} must contain non-empty text.")
    if len(set(value)) != len(value) or (allowed is not None and not set(value) <= allowed):
        raise ValueError(f"Evaluation {label} has invalid or duplicate values.")


def _validate_review_labels(value: object, index: int) -> dict[str, bool]:
    if type(value) is not dict or set(value) != REVIEW_FIELDS:
        raise ValueError(f"Evaluation case {index} has invalid review labels.")
    for field, label in value.items():
        if type(label) is not bool:
            raise TypeError(f"Evaluation case {index} review label {field} must be boolean.")
    return value


def _derive_labels(
    results: dict[str, dict[str, Any]],
    evidence: dict[str, str],
    expected: dict[str, Any],
) -> dict[str, bool]:
    selected = results[expected["selected_result"]]
    serialized = json.dumps(selected, ensure_ascii=False, sort_keys=True)
    folded = serialized.casefold()
    risks = {item.get("type") for item in selected.get("risk_flags", []) if type(item) is dict}
    actions = {
        item.get("type") for item in selected.get("suggested_actions", []) if type(item) is dict
    }
    grounded = all(
        fact["value"].casefold() in folded
        and fact["value"].casefold() in evidence.get(fact["source_id"], "").casefold()
        for fact in expected["critical_facts"]
    )
    grounded = grounded and _critical_signatures(serialized).issubset(
        _critical_signatures("\n".join(evidence.values()))
    )
    action_safe = (
        set(expected["required_action_types"]) <= actions
        and set(expected["forbidden_action_types"]).isdisjoint(actions)
        and not any(term.casefold() in folded for term in expected["forbidden_commitment_terms"])
        and not has_unsafe_operation(serialized)
        and not has_unconditional_commitment(serialized)
    )
    return {
        "mandatory_risks_retained": set(expected["mandatory_risk_types"]) <= risks,
        "critical_facts_grounded": grounded,
        "commitment_action_safe": action_safe,
        "used_fallback": expected["selected_result"] == "rule_public_result",
    }


def _crosscheck_labels(
    labels: dict[str, bool], derived: dict[str, bool], index: int
) -> None:
    for field in REVIEW_FIELDS:
        if labels[field] != derived[field]:
            raise ValueError(f"Evaluation case {index} review label {field} disagrees with evidence.")


def _validate_latency(value: object, index: int) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Evaluation case {index} latency_ms must be numeric.")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"Evaluation case {index} latency_ms must be finite and nonnegative.")


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Evaluation {field} must be non-empty text.")
    return value


def _ratio(cases: list[dict[str, Any]], field: str) -> float | None:
    if not cases:
        return None
    return sum(case[field] for case in cases) / len(cases)


def _count_false(cases: list[dict[str, Any]], field: str) -> int:
    return sum(not case[field] for case in cases)


def _load_cases(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate recorded synthetic DeepSeek public results offline."
    )
    parser.add_argument(
        "fixture",
        nargs="?",
        type=Path,
        default=DEFAULT_CASES,
        help="JSON fixture path (defaults to the repository 50-case fixture).",
    )
    args = parser.parse_args(argv)
    try:
        report = evaluate_cases(_load_cases(args.fixture))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
