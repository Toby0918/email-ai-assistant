"""Repair parseable model JSON into the validated first-version schema."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .analysis_schema import (
    ACTION_TYPES,
    CATEGORIES,
    CONFIDENCE_LEVELS,
    DECISION_REPLY_TYPES,
    PRIORITIES,
    RISK_LEVELS,
    RISK_TYPES,
)


def repair_analysis_result(data: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Merge partial model output with deterministic fallback schema fields."""
    result = dict(fallback)
    result["conversation_timeline"] = deepcopy(fallback.get("conversation_timeline", {}))
    result["attachment_insights"] = deepcopy(fallback.get("attachment_insights", []))
    result["summary"] = _text(data.get("summary")) or fallback["summary"]
    result["priority"] = _enum(data.get("priority"), PRIORITIES, fallback["priority"])
    result["priority_reason"] = _text(data.get("priority_reason")) or fallback["priority_reason"]
    model_category = _enum(data.get("category"), CATEGORIES, fallback["category"])
    if _should_prefer_fallback_category(model_category, fallback["category"]):
        result.update({
            "summary": fallback["summary"],
            "priority": fallback["priority"],
            "priority_reason": fallback["priority_reason"],
            "category": fallback["category"],
            "tags": list(fallback.get("tags", [])),
            "risk_flags": list(fallback.get("risk_flags", [])),
            "suggested_actions": list(fallback.get("suggested_actions", [])),
            "reply_draft": dict(fallback.get("reply_draft", {})),
        })
        return result
    result["category"] = model_category
    result["tags"] = _string_list(data.get("tags")) or list(fallback.get("tags", []))
    result["decision_brief"] = _repair_decision_brief(
        data.get("decision_brief"),
        fallback.get("decision_brief", {}),
        result["attachment_insights"],
    )
    result["risk_flags"] = _repair_risks(data.get("risk_flags"), fallback.get("risk_flags", []))
    result["suggested_actions"] = _repair_actions(
        data.get("suggested_actions"),
        fallback.get("suggested_actions", []),
    )
    result["reply_draft"] = _repair_reply_draft(
        data.get("reply_draft"),
        data.get("review_reasons"),
        fallback.get("reply_draft", {}),
    )
    return result


def _repair_risks(items: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        return list(fallback)
    repaired = []
    fallback_item = fallback[0] if fallback else {}
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence = _text(item.get("evidence")) or _text(fallback_item.get("evidence"))
        repaired.append({
            "type": _risk_type(item.get("type"), evidence, _text(fallback_item.get("type"))),
            "level": _enum(item.get("level"), RISK_LEVELS, _text(fallback_item.get("level")) or "medium"),
            "evidence": evidence,
            "recommendation": _text(item.get("recommendation")) or _text(fallback_item.get("recommendation")),
        })
    return repaired or list(fallback)


def _should_prefer_fallback_category(model_category: str, fallback_category: str) -> bool:
    return fallback_category == "new_product_development" and model_category == "complaint"


def _repair_actions(items: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        return list(fallback)
    repaired = []
    fallback_item = fallback[0] if fallback else {}
    for item in items:
        if not isinstance(item, dict):
            continue
        description = _text(item.get("description")) or _text(fallback_item.get("description"))
        repaired.append({
            "type": _action_type(item.get("type"), description, _text(fallback_item.get("type"))),
            "description": description,
            "owner_hint": _text(item.get("owner_hint")) or _text(fallback_item.get("owner_hint")) or "responsible_owner",
            "due_hint": _text(item.get("due_hint")) or _text(fallback_item.get("due_hint")) or "today",
        })
    return repaired or list(fallback)


def _repair_decision_brief(
    value: Any,
    fallback: dict[str, Any],
    attachment_insights: list[dict[str, Any]],
) -> dict[str, Any]:
    brief = value if isinstance(value, dict) else {}
    fallback_recommendation = fallback.get("reply_recommendation", {})
    recommendation = brief.get("reply_recommendation")
    recommendation = recommendation if isinstance(recommendation, dict) else {}
    return {
        "one_line_conclusion": _text(brief.get("one_line_conclusion")) or _text(fallback.get("one_line_conclusion")),
        "requested_outcome": _text(brief.get("requested_outcome")) or _text(fallback.get("requested_outcome")),
        "next_steps": _repair_next_steps(brief.get("next_steps"), fallback.get("next_steps", [])),
        "key_facts": _repair_key_facts(
            brief.get("key_facts"),
            fallback.get("key_facts", []),
            attachment_insights,
        ),
        "must_check": _string_list(brief.get("must_check")) or list(fallback.get("must_check", [])),
        "missing_info": _string_list(brief.get("missing_info")) or list(fallback.get("missing_info", [])),
        "reply_recommendation": {
            "should_reply": _bool(
                recommendation.get("should_reply"),
                bool(fallback_recommendation.get("should_reply", True)),
            ),
            "reply_type": _enum(
                recommendation.get("reply_type"),
                DECISION_REPLY_TYPES,
                _text(fallback_recommendation.get("reply_type")) or "acknowledge",
            ),
            "reason": _text(recommendation.get("reason")) or _text(fallback_recommendation.get("reason")),
        },
        "confidence": _enum(
            brief.get("confidence"),
            CONFIDENCE_LEVELS,
            _text(fallback.get("confidence")) or "low",
        ),
    }


def _repair_next_steps(items: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        return list(fallback)
    repaired = []
    fallback_item = fallback[0] if fallback else {}
    for item in items:
        if not isinstance(item, dict):
            continue
        step = _text(item.get("step")) or _text(fallback_item.get("step"))
        if not step:
            continue
        repaired.append({
            "step": step,
            "owner_hint": _text(item.get("owner_hint")) or _text(fallback_item.get("owner_hint")) or "responsible_owner",
            "due_hint": _text(item.get("due_hint")) or _text(fallback_item.get("due_hint")) or "today",
            "source": _text(item.get("source")) or _text(fallback_item.get("source")) or "latest_message",
        })
    return repaired or list(fallback)


def _repair_key_facts(
    items: Any,
    fallback: list[dict[str, Any]],
    attachment_insights: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    candidates = items if isinstance(items, list) else []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        value = _text(item.get("value"))
        if not value:
            continue
        source = _text(item.get("source")) or "latest_message"
        if _is_model_attachment_fact(value, source, attachment_insights):
            continue
        repaired.append({
            "label": _text(item.get("label")) or "事实",
            "value": value,
            "source": source,
        })
    for item in fallback:
        if isinstance(item, dict) and _text(item.get("value")):
            repaired.append(dict(item))
    return _unique_key_facts(repaired)[:10]


def _is_model_attachment_fact(
    value: str,
    source: str,
    attachment_insights: list[dict[str, Any]],
) -> bool:
    lower_source = source.lower()
    if "attachment" in lower_source or lower_source.startswith("file"):
        return True
    lower_value = value.lower()
    return any(
        _text(insight.get("filename")).lower() in lower_value
        for insight in attachment_insights
        if _text(insight.get("filename"))
    )


def _unique_key_facts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = _text(item.get("value")).lower()
        if key and key not in seen:
            values.append(item)
            seen.add(key)
    return values


def _repair_reply_draft(value: Any, top_level_reasons: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    draft = value if isinstance(value, dict) else {}
    reasons = _string_list(draft.get("review_reasons")) or _string_list(top_level_reasons)
    return {
        "subject": _text(draft.get("subject")) or _text(fallback.get("subject")),
        "body": _text(draft.get("body")) or _text(fallback.get("body")),
        "needs_human_review": True,
        "review_reasons": reasons or list(fallback.get("review_reasons", [])),
    }


def _risk_type(value: Any, evidence: str, fallback: str) -> str:
    exact = _enum(value, RISK_TYPES, "")
    if exact:
        return exact
    text = f"{value} {evidence}".lower()
    mappings = [
        ("quality_risk", ("quality", "complaint", "defect", "reject", "damage", "iqc")),
        ("payment_risk", ("payment", "invoice", "remittance")),
        ("contract_risk", ("contract", "term", "legal")),
        ("prompt_injection_risk", ("prompt", "instruction", "system")),
        ("delivery_risk", ("delivery", "shipment", "logistics", "tracking", "eta")),
        ("commitment_risk", ("commit", "quote", "price", "lead time")),
        ("security_risk", ("security", "password", "token")),
    ]
    for risk_type, markers in mappings:
        if any(marker in text for marker in markers):
            return risk_type
    return _enum(fallback, RISK_TYPES, "commitment_risk")


def _action_type(value: Any, description: str, fallback: str) -> str:
    exact = _enum(value, ACTION_TYPES, "")
    if exact:
        return exact
    fallback_exact = _enum(fallback, ACTION_TYPES, "")
    if fallback_exact and fallback_exact != "reply":
        return fallback_exact
    text = f"{value} {description}".lower()
    mappings = [
        ("check_delivery", ("delivery", "shipment", "logistics", "tracking", "eta")),
        ("prepare_quote", ("quote", "price", "rfq")),
        ("check_inventory", ("inventory", "stock")),
        ("escalate", ("escalate", "complaint", "quality", "reject", "defect", "iqc")),
        ("confirm", ("verify", "confirm", "check")),
        ("reply", ("reply", "respond")),
        ("wait", ("wait",)),
        ("ignore", ("ignore",)),
    ]
    for action_type, markers in mappings:
        if any(marker in text for marker in markers):
            return action_type
    return _enum(fallback, ACTION_TYPES, "reply")


def _enum(value: Any, allowed: set[str], fallback: str) -> str:
    text = _text(value)
    return text if text in allowed else fallback


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback
