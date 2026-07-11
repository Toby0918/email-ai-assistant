"""Project parseable model JSON into the deterministic validated schema."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .analysis_schema import CATEGORIES, PRIORITIES


DETERMINISTIC_FIELDS = (
    "decision_brief",
    "conversation_timeline",
    "attachment_insights",
    "risk_flags",
    "suggested_actions",
    "reply_draft",
)


def repair_analysis_result(data: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Keep useful model classification prose while projecting consequential fields from rules."""
    result = deepcopy(fallback)
    result["summary"] = _text(data.get("summary")) or fallback["summary"]
    result["priority"] = _enum(data.get("priority"), PRIORITIES, fallback["priority"])
    result["priority_reason"] = _text(data.get("priority_reason")) or fallback["priority_reason"]
    model_category = _enum(data.get("category"), CATEGORIES, fallback["category"])
    if _should_prefer_fallback_category(model_category, fallback["category"]):
        return deepcopy(fallback)

    result["category"] = model_category
    result["tags"] = _string_list(data.get("tags")) or list(fallback.get("tags", []))
    for field in DETERMINISTIC_FIELDS:
        result[field] = deepcopy(fallback[field])
    return result


def _should_prefer_fallback_category(model_category: str, fallback_category: str) -> bool:
    return fallback_category == "new_product_development" and model_category == "complaint"


def _enum(value: Any, allowed: set[str], fallback: str) -> str:
    text = _text(value)
    return text if text in allowed else fallback


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _text(value: Any) -> str:
    return str(value or "").strip()
