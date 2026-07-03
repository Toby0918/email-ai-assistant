"""Repair parseable model JSON into the validated first-version schema."""

from __future__ import annotations

from typing import Any

from .analysis_schema import ACTION_TYPES, CATEGORIES, PRIORITIES, RISK_LEVELS, RISK_TYPES


def repair_analysis_result(data: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Merge partial model output with deterministic fallback schema fields."""
    result = dict(fallback)
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
