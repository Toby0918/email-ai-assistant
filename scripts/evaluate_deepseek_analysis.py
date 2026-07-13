"""Evaluate synthetic DeepSeek responses through the production route offline."""

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
from backend.email_agent.model_grounding import _critical_signatures  # noqa: E402
from backend.email_agent.model_text_safety import (  # noqa: E402
    has_unconditional_commitment,
    has_unsafe_operation,
    validate_public_language,
)
from scripts.deepseek_eval_replay import replay_case  # noqa: E402


DEFAULT_CASES = ROOT / "tests" / "fixtures" / "deepseek_eval" / "cases.json"
CASE_FIELDS = {"case_id", "provenance", "scenario", "provider_case", "fact", "expected"}
OPTIONAL_CASE_FIELDS = {"latency_ms"}
PROVIDER_CASES = {
    "accepted", "automatic_action", "passive_commitment", "unsupported_fact",
    "malformed_json", "evidence_failure",
}
EXPECTED_FIELDS = {
    "analysis_source", "mandatory_risk_types", "critical_facts",
    "required_action_types", "forbidden_action_types", "forbidden_commitment_terms",
}
CRITICAL_FACT_FIELDS = {"value", "source_id"}


def evaluate_cases(cases: list[dict[str, object]]) -> dict[str, object]:
    """Replay cases and return the stable seven-field offline quality report."""
    metrics = _evaluate_cases(cases)
    count = len(metrics)
    return {
        "case_count": count,
        "schema_pass_rate": _ratio(metrics, "schema_passed"),
        "mandatory_risk_retention_rate": _ratio(metrics, "mandatory_risks_retained"),
        "unsupported_critical_fact_count": _count_false(metrics, "critical_facts_grounded"),
        "commitment_action_violation_count": _count_false(metrics, "commitment_action_safe"),
        "fallback_rate": _ratio(metrics, "used_fallback"),
        "latency_samples_ms": [
            float(case["latency_ms"]) for case in metrics if "latency_ms" in case
        ],
    }


def _evaluate_cases(cases: object) -> list[dict[str, Any]]:
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
        metrics.append(_evaluate_case(checked, index))
    return metrics


def _validate_case(case: object, index: int) -> dict[str, Any]:
    if type(case) is not dict:
        raise TypeError(f"Evaluation case {index} must be an object.")
    fields = set(case)
    if fields - CASE_FIELDS - OPTIONAL_CASE_FIELDS or not CASE_FIELDS <= fields:
        raise ValueError(f"Evaluation case {index} has an invalid field set.")
    _require_text(case["case_id"], f"case {index} case_id")
    provenance = _require_text(case["provenance"], f"case {index} provenance")
    if "synthetic" not in provenance.casefold():
        raise ValueError(f"Evaluation case {index} must have synthetic provenance.")
    _require_text(case["scenario"], f"case {index} scenario")
    _require_text(case["fact"], f"case {index} fact")
    if case["provider_case"] not in PROVIDER_CASES:
        raise ValueError(f"Evaluation case {index} has invalid provider_case.")
    _validate_expected(case["expected"], index)
    if "latency_ms" in case:
        _validate_latency(case["latency_ms"], index)
    return case


def _validate_expected(value: object, index: int) -> None:
    if type(value) is not dict or set(value) != EXPECTED_FIELDS:
        raise ValueError(f"Evaluation case {index} has invalid expected evidence.")
    if value["analysis_source"] not in {"ai_model", "rule_fallback"}:
        raise ValueError(f"Evaluation case {index} has invalid analysis_source.")
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


def _evaluate_case(case: dict[str, Any], index: int) -> dict[str, Any]:
    outcome = replay_case(case)
    result, expected = outcome.result, case["expected"]
    schema_passed = True
    try:
        validate_analysis_result(result)
    except AnalysisValidationError:
        schema_passed = False
    source = result.get("analysis_engine", {}).get("source")
    if source != expected["analysis_source"]:
        raise ValueError(
            f"Evaluation case {index} analysis_source disagrees with production route."
        )
    if source == "ai_model":
        validate_public_language(result)
        if not _materially_distinct(result, outcome.baseline):
            raise ValueError(f"Evaluation case {index} model result is not materially distinct.")
    elif result != outcome.baseline:
        raise ValueError(f"Evaluation case {index} fallback differs from rule baseline.")
    return {
        "case_id": case["case_id"], "schema_passed": schema_passed,
        **_derive_metrics(result, outcome.baseline, outcome.evidence_sources, expected),
        **({"latency_ms": case["latency_ms"]} if "latency_ms" in case else {}),
    }


def _derive_metrics(
    result: dict[str, Any], baseline: dict[str, Any],
    evidence: dict[str, str], expected: dict[str, Any],
) -> dict[str, bool]:
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
    baseline_text = json.dumps(baseline, ensure_ascii=False, sort_keys=True)
    folded = serialized.casefold()
    risks = {item.get("type") for item in result.get("risk_flags", []) if type(item) is dict}
    actions = {
        item.get("type") for item in result.get("suggested_actions", []) if type(item) is dict
    }
    grounded = all(
        fact["value"].casefold() in folded
        and fact["value"].casefold() in evidence.get(fact["source_id"], "").casefold()
        for fact in expected["critical_facts"]
    )
    model_signatures = _critical_signatures(serialized) - _critical_signatures(baseline_text)
    grounded = grounded and model_signatures.issubset(
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
        "used_fallback": result["analysis_engine"]["source"] == "rule_fallback",
    }


def _validate_text_list(
    value: object, label: str, allowed: set[str] | None, required: bool = False
) -> None:
    if type(value) is not list or (required and not value):
        raise TypeError(f"Evaluation {label} must be a valid list.")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise TypeError(f"Evaluation {label} must contain non-empty text.")
    if len(set(value)) != len(value) or (allowed is not None and not set(value) <= allowed):
        raise ValueError(f"Evaluation {label} has invalid or duplicate values.")


def _validate_latency(value: object, index: int) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Evaluation case {index} latency_ms must be numeric.")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"Evaluation case {index} latency_ms must be finite and nonnegative.")


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Evaluation {field} must be non-empty text.")
    return value


def _materially_distinct(
    result: dict[str, Any], baseline: dict[str, Any]
) -> bool:
    """Require a substantive analytical change, not model-origin metadata."""
    return _material_projection(result) != _material_projection(baseline)


def _material_projection(result: dict[str, Any]) -> dict[str, Any]:
    draft = result.get("reply_draft")
    reply_content = (
        {"subject": draft.get("subject"), "body": draft.get("body")}
        if isinstance(draft, dict)
        else draft
    )
    fields = (
        "summary", "priority", "priority_reason", "category", "decision_brief",
        "conversation_timeline", "risk_flags", "suggested_actions",
        "attachment_insights",
    )
    return {
        **{field: result.get(field) for field in fields},
        "reply_draft": reply_content,
    }


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
        description="Replay synthetic DeepSeek private responses through production offline."
    )
    parser.add_argument(
        "fixture", nargs="?", type=Path, default=DEFAULT_CASES,
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
