"""Factories for deterministic synthetic DeepSeek replay tests."""

from __future__ import annotations

from typing import Any


def evaluation_case(
    case_id: str = "synthetic-001",
    *,
    scenario: str = "internal",
    provider_case: str = "accepted",
    analysis_source: str | None = None,
    fact: str | None = None,
    mandatory_risks: list[str] | None = None,
    required_actions: list[str] | None = None,
) -> dict[str, Any]:
    """Return one compact case descriptor, never a preselected public result."""
    source = analysis_source or (
        "ai_model" if provider_case == "accepted" else "rule_fallback"
    )
    value = fact or f"SYNTHETIC-FACT-{case_id.upper()}"
    return {
        "case_id": case_id,
        "provenance": "synthetic generated offline replay",
        "scenario": scenario,
        "provider_case": provider_case,
        "fact": value,
        "expected": {
            "analysis_source": source,
            "mandatory_risk_types": mandatory_risks or [],
            "critical_facts": [
                {"value": value, "source_id": "thread:0"}
            ],
            "required_action_types": required_actions or ["confirm"],
            "forbidden_action_types": ["ignore"],
            "forbidden_commitment_terms": ["we guarantee delivery"],
        },
    }
