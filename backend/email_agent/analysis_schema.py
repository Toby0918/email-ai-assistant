"""Analysis result schema validation for the assistant window."""

from __future__ import annotations

from typing import Any


REQUIRED_RESULT_FIELDS = {
    "summary",
    "priority",
    "priority_reason",
    "category",
    "tags",
    "decision_brief",
    "conversation_timeline",
    "attachment_insights",
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
DECISION_REPLY_TYPES = {
    "acknowledge",
    "ask_clarification",
    "provide_info",
    "escalate_first",
    "no_reply",
}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
CONVERSATION_STATUSES = {"resolved", "partially_resolved", "unresolved", "unknown"}
TIMELINE_SOURCES = {"thread", "attachment"}
ATTACHMENT_TYPES = {"image", "pdf", "xlsx", "docx", "unsupported"}
ATTACHMENT_STATUSES = {"parsed", "metadata_only", "unavailable", "failed"}


class AnalysisValidationError(ValueError):
    """Raised when analysis JSON does not match the first-version schema."""


def validate_analysis_result(data: dict[str, Any]) -> dict[str, Any]:
    # Validate before storage or rendering so UI never relies on free-form text.
    if not isinstance(data, dict):
        raise AnalysisValidationError("Analysis result must be a JSON object.")
    _require_fields(data, REQUIRED_RESULT_FIELDS, "analysis")
    _require_enum(data["priority"], PRIORITIES, "priority")
    _require_enum(data["category"], CATEGORIES, "category")
    _validate_string_list(data["tags"], "tags")
    _validate_decision_brief(data["decision_brief"])
    _validate_conversation_timeline(data["conversation_timeline"])
    _validate_attachment_insights(data["attachment_insights"])
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
        for field in ("evidence", "recommendation"):
            _require_string(item[field], f"risk_flag.{field}")


def _validate_decision_brief(value: Any) -> None:
    if not isinstance(value, dict):
        raise AnalysisValidationError("decision_brief must be an object.")
    _require_fields(
        value,
        {
            "one_line_conclusion",
            "requested_outcome",
            "next_steps",
            "key_facts",
            "must_check",
            "missing_info",
            "reply_recommendation",
            "confidence",
        },
        "decision_brief",
    )
    _require_string(value["one_line_conclusion"], "decision_brief.one_line_conclusion")
    _require_string(value["requested_outcome"], "decision_brief.requested_outcome")
    _validate_next_steps(value["next_steps"])
    _validate_key_facts(value["key_facts"])
    _validate_string_list(value["must_check"], "decision_brief.must_check")
    _validate_string_list(value["missing_info"], "decision_brief.missing_info")
    _validate_reply_recommendation(value["reply_recommendation"])
    _require_enum(value["confidence"], CONFIDENCE_LEVELS, "decision_brief.confidence")


def _validate_next_steps(items: Any) -> None:
    _require_list(items, "decision_brief.next_steps")
    if not 1 <= len(items) <= 4:
        raise AnalysisValidationError("decision_brief.next_steps must contain 1 to 4 items.")
    for item in items:
        if not isinstance(item, dict):
            raise AnalysisValidationError("decision_brief.next_steps items must be objects.")
        _require_fields(item, {"step", "owner_hint", "due_hint", "source"}, "decision_brief.next_step")
        for field in ("step", "owner_hint", "due_hint", "source"):
            _require_string(item[field], f"decision_brief.next_step.{field}")


def _validate_key_facts(items: Any) -> None:
    _require_list(items, "decision_brief.key_facts")
    for item in items:
        if not isinstance(item, dict):
            raise AnalysisValidationError("decision_brief.key_facts items must be objects.")
        _require_fields(item, {"label", "value", "source"}, "decision_brief.key_fact")
        for field in ("label", "value", "source"):
            _require_string(item[field], f"decision_brief.key_fact.{field}")


def _validate_string_list(items: Any, label: str) -> None:
    _require_list(items, label)
    if not all(isinstance(item, str) for item in items):
        raise AnalysisValidationError(f"{label} items must be strings.")


def _validate_reply_recommendation(value: Any) -> None:
    if not isinstance(value, dict):
        raise AnalysisValidationError("decision_brief.reply_recommendation must be an object.")
    _require_fields(
        value,
        {"should_reply", "reply_type", "reason"},
        "decision_brief.reply_recommendation",
    )
    if not isinstance(value["should_reply"], bool):
        raise AnalysisValidationError("decision_brief.reply_recommendation.should_reply must be a boolean.")
    _require_enum(
        value["reply_type"],
        DECISION_REPLY_TYPES,
        "decision_brief.reply_recommendation.reply_type",
    )
    _require_string(value["reason"], "decision_brief.reply_recommendation.reason")


def _validate_conversation_timeline(value: Any) -> None:
    if not isinstance(value, dict):
        raise AnalysisValidationError("conversation_timeline must be an object.")
    fields = {
        "previous_context",
        "current_status",
        "status_reason",
        "latest_external_request",
        "latest_internal_commitment",
        "open_items",
        "confidence",
    }
    _require_fields(value, fields, "conversation_timeline")
    for field in (
        "previous_context",
        "status_reason",
        "latest_external_request",
        "latest_internal_commitment",
    ):
        _require_string(value[field], f"conversation_timeline.{field}")
    _require_enum(value["current_status"], CONVERSATION_STATUSES, "conversation_timeline.current_status")
    _require_enum(value["confidence"], CONFIDENCE_LEVELS, "conversation_timeline.confidence")
    _validate_timeline_items(value["open_items"])


def _validate_timeline_items(items: Any) -> None:
    _require_list(items, "conversation_timeline.open_items")
    for item in items:
        if not isinstance(item, dict):
            raise AnalysisValidationError("conversation_timeline.open_items items must be objects.")
        _require_fields(item, {"item", "owner_hint", "due_hint", "source"}, "conversation_timeline.open_item")
        for field in ("item", "owner_hint", "due_hint"):
            _require_string(item[field], f"conversation_timeline.open_item.{field}")
        _require_enum(item["source"], TIMELINE_SOURCES, "conversation_timeline.open_item.source")


def _validate_attachment_insights(items: Any) -> None:
    _require_list(items, "attachment_insights")
    for item in items:
        if not isinstance(item, dict):
            raise AnalysisValidationError("attachment_insights items must be objects.")
        fields = {"filename", "type", "status", "summary", "key_facts", "limitations"}
        _require_fields(item, fields, "attachment_insight")
        _require_string(item["filename"], "attachment_insight.filename")
        _require_string(item["summary"], "attachment_insight.summary")
        _require_enum(item["type"], ATTACHMENT_TYPES, "attachment_insight.type")
        _require_enum(item["status"], ATTACHMENT_STATUSES, "attachment_insight.status")
        _validate_string_list(item["key_facts"], "attachment_insight.key_facts")
        _validate_string_list(item["limitations"], "attachment_insight.limitations")


def _require_string(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise AnalysisValidationError(f"{label} must be a string.")


def _validate_actions(items: Any) -> None:
    _require_list(items, "suggested_actions")
    for item in items:
        if not isinstance(item, dict):
            raise AnalysisValidationError("suggested_actions items must be objects.")
        _require_fields(item, {"type", "description", "owner_hint", "due_hint"}, "suggested_action")
        _require_enum(item["type"], ACTION_TYPES, "suggested_action.type")
        for field in ("description", "owner_hint", "due_hint"):
            _require_string(item[field], f"suggested_action.{field}")


def _validate_reply_draft(value: Any) -> None:
    if not isinstance(value, dict):
        raise AnalysisValidationError("reply_draft must be an object.")
    _require_fields(value, {"subject", "body", "needs_human_review", "review_reasons"}, "reply_draft")
    for field in ("subject", "body"):
        _require_string(value[field], f"reply_draft.{field}")
    if value["needs_human_review"] is not True:
        raise AnalysisValidationError("reply_draft.needs_human_review must be true.")
    _validate_string_list(value["review_reasons"], "reply_draft.review_reasons")
