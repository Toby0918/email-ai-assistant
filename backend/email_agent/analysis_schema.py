"""Analysis result schema validation for the assistant window."""

from __future__ import annotations

from typing import Any


REQUIRED_RESULT_FIELDS = {
    "summary",
    "priority",
    "priority_reason",
    "category",
    "tags",
    "risk_flags",
    "suggested_actions",
    "reply_draft",
}

PRIORITIES = {"urgent", "high", "normal", "low"}
CATEGORIES = {
    "customer_inquiry",
    "order_followup",
    "payment",
    "contract",
    "complaint",
    "new_product_development",
    "internal",
    "marketing",
    "unknown",
}
RISK_TYPES = {
    "payment_risk",
    "delivery_risk",
    "contract_risk",
    "quality_risk",
    "security_risk",
    "commitment_risk",
    "prompt_injection_risk",
}
RISK_LEVELS = {"high", "medium", "low"}
ACTION_TYPES = {
    "reply",
    "confirm",
    "prepare_quote",
    "check_inventory",
    "check_delivery",
    "escalate",
    "wait",
    "ignore",
}


class AnalysisValidationError(ValueError):
    """Raised when analysis JSON does not match the first-version schema."""


def validate_analysis_result(data: dict[str, Any]) -> dict[str, Any]:
    # Validate before storage or rendering so UI never relies on free-form text.
    if not isinstance(data, dict):
        raise AnalysisValidationError("Analysis result must be a JSON object.")
    _require_fields(data, REQUIRED_RESULT_FIELDS, "analysis")
    _require_enum(data["priority"], PRIORITIES, "priority")
    _require_enum(data["category"], CATEGORIES, "category")
    _require_list(data["tags"], "tags")
    _validate_risk_flags(data["risk_flags"])
    _validate_actions(data["suggested_actions"])
    _validate_reply_draft(data["reply_draft"])
    return data


def _require_fields(data: dict[str, Any], fields: set[str], label: str) -> None:
    missing = sorted(fields.difference(data))
    if missing:
        raise AnalysisValidationError(f"{label} missing fields: {', '.join(missing)}")


def _require_enum(value: Any, allowed: set[str], label: str) -> None:
    if value not in allowed:
        raise AnalysisValidationError(f"{label} has invalid value: {value}")


def _require_list(value: Any, label: str) -> None:
    if not isinstance(value, list):
        raise AnalysisValidationError(f"{label} must be a list.")


def _validate_risk_flags(items: Any) -> None:
    _require_list(items, "risk_flags")
    for item in items:
        if not isinstance(item, dict):
            raise AnalysisValidationError("risk_flags items must be objects.")
        _require_fields(item, {"type", "level", "evidence", "recommendation"}, "risk_flag")
        _require_enum(item["type"], RISK_TYPES, "risk_flag.type")
        _require_enum(item["level"], RISK_LEVELS, "risk_flag.level")


def _validate_actions(items: Any) -> None:
    _require_list(items, "suggested_actions")
    for item in items:
        if not isinstance(item, dict):
            raise AnalysisValidationError("suggested_actions items must be objects.")
        _require_fields(item, {"type", "description", "owner_hint", "due_hint"}, "suggested_action")
        _require_enum(item["type"], ACTION_TYPES, "suggested_action.type")


def _validate_reply_draft(value: Any) -> None:
    if not isinstance(value, dict):
        raise AnalysisValidationError("reply_draft must be an object.")
    _require_fields(value, {"subject", "body", "needs_human_review", "review_reasons"}, "reply_draft")
    if value["needs_human_review"] is not True:
        raise AnalysisValidationError("reply_draft.needs_human_review must be true.")
    _require_list(value["review_reasons"], "reply_draft.review_reasons")
