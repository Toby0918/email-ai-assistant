"""Factories for deterministic synthetic DeepSeek evaluation tests."""

from __future__ import annotations

from typing import Any


def _decision_brief(fact: str) -> dict[str, Any]:
    return {
        "one_line_conclusion": f"Review synthetic fact {fact}.",
        "requested_outcome": "Confirm the synthetic request.",
        "next_steps": [
            {
                "step": "Review the synthetic evidence.",
                "owner_hint": "Human reviewer",
                "due_hint": "No synthetic deadline supplied",
                "source": "Synthetic visible thread",
            }
        ],
        "key_facts": [
            {
                "label": "Synthetic fact",
                "value": fact,
                "source": "Synthetic visible thread",
            }
        ],
        "must_check": ["Verify the synthetic fact before acting."],
        "missing_info": [],
        "reply_recommendation": {
            "should_reply": True,
            "reply_type": "acknowledge",
            "reason": "A human-reviewed acknowledgement is appropriate.",
        },
        "confidence": "high",
    }


def _timeline(fact: str) -> dict[str, Any]:
    return {
        "previous_context": "Synthetic evaluation context only.",
        "current_status": "unresolved",
        "status_reason": f"The synthetic fact {fact} awaits review.",
        "latest_external_request": f"Review {fact}.",
        "latest_internal_commitment": "No commitment has been made.",
        "open_items": [
            {
                "item": f"Confirm {fact}.",
                "owner_hint": "Human reviewer",
                "due_hint": "No synthetic deadline supplied",
                "source": "thread",
            }
        ],
        "confidence": "high",
    }


def _risk_flags(fact: str, risk_types: list[str]) -> list[dict[str, str]]:
    return [
        {
            "type": risk_type,
            "level": "medium",
            "evidence": f"Synthetic evidence for {risk_type} and {fact}.",
            "recommendation": "Require human review before acting.",
        }
        for risk_type in risk_types
    ]


def _actions(fact: str, action_types: list[str]) -> list[dict[str, str]]:
    return [
        {
            "type": action_type,
            "description": f"Human-review {fact} before {action_type}.",
            "owner_hint": "Human reviewer",
            "due_hint": "No synthetic deadline supplied",
        }
        for action_type in action_types
    ]


def public_result(
    source: str,
    *,
    fact: str = "SYNTHETIC-FACT-001",
    risk_types: list[str] | None = None,
    action_types: list[str] | None = None,
) -> dict[str, Any]:
    risks = risk_types or []
    actions = action_types or ["confirm"]
    return {
        "summary": f"Synthetic analysis records {fact} for review.",
        "priority": "normal",
        "priority_reason": "Synthetic evidence requires a human check.",
        "category": "internal",
        "tags": ["synthetic", "offline-evaluation"],
        "decision_brief": _decision_brief(fact),
        "conversation_timeline": _timeline(fact),
        "attachment_insights": [],
        "risk_flags": _risk_flags(fact, risks),
        "suggested_actions": _actions(fact, actions),
        "reply_draft": {
            "subject": "Synthetic request acknowledgement",
            "body": f"We received the synthetic reference {fact}. Please review it.",
            "needs_human_review": True,
            "review_reasons": ["Synthetic evaluation draft; human approval is required."],
        },
        "analysis_engine": {
            "source": source,
            "label": "Rule fallback" if source == "rule_fallback" else "DeepSeek",
        },
    }


def _expectations(
    case_id: str,
    fact: str,
    selected_result: str,
    risks: list[str],
    actions: list[str],
) -> dict[str, Any]:
    return {
        "selected_result": selected_result,
        "mandatory_risk_types": risks,
        "critical_facts": [
            {"value": fact, "source_id": f"synthetic:{case_id}:thread:0"}
        ],
        "required_action_types": actions,
        "forbidden_action_types": ["ignore"],
        "forbidden_commitment_terms": ["we guarantee delivery"],
    }


def evaluation_case(
    case_id: str = "synthetic-001",
    *,
    selected_result: str = "model_public_result",
    mandatory_risks: list[str] | None = None,
    required_actions: list[str] | None = None,
    **labels: bool,
) -> dict[str, Any]:
    fact = f"SYNTHETIC-FACT-{case_id.upper()}"
    risks = mandatory_risks or []
    actions = required_actions or ["confirm"]
    review_labels = {
        "mandatory_risks_retained": True,
        "critical_facts_grounded": True,
        "commitment_action_safe": True,
        "used_fallback": selected_result == "rule_public_result",
        **labels,
    }
    recorded = {
        "rule_public_result": public_result(
            "rule_fallback", fact=fact, risk_types=risks, action_types=actions
        ),
        "model_public_result": public_result(
            "ai_model", fact=fact, risk_types=risks, action_types=actions
        ),
    }
    return {
        "case_id": case_id,
        "provenance": "synthetic generated offline fixture",
        "scenario": "internal",
        "recorded_results": recorded,
        "evidence_sources": [
            {
                "source_id": f"synthetic:{case_id}:thread:0",
                "text": f"Synthetic source contains critical fact {fact}.",
            }
        ],
        "expected": _expectations(case_id, fact, selected_result, risks, actions),
        "review_labels": review_labels,
    }
