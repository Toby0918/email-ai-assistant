"""Allowlist projections for analysis results crossing model and SQLite boundaries."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .analysis_schema import (
    ATTACHMENT_STATUSES,
    ATTACHMENT_TYPES,
)


ATTACHMENT_INSIGHT_FIELDS = {
    "filename",
    "type",
    "status",
    "summary",
    "key_facts",
    "limitations",
}
MAX_ATTACHMENT_INSIGHTS = 14
MAX_INSIGHT_FACTS = 5
MAX_INSIGHT_LIMITATIONS = 8
MAX_STORED_ITEMS = 20
MAX_STORED_TEXT = 4_000


def project_attachment_insights(value: Any) -> list[dict[str, object]]:
    """Return only bounded documented attachment-insight fields."""
    if not isinstance(value, list):
        return []
    projected: list[dict[str, object]] = []
    for raw in value[:MAX_ATTACHMENT_INSIGHTS]:
        if not isinstance(raw, dict):
            continue
        raw_status = raw.get("status")
        status_valid = isinstance(raw_status, str) and raw_status in ATTACHMENT_STATUSES
        status = raw_status if status_valid else "failed"
        limitations = _string_list(raw.get("limitations"), MAX_INSIGHT_LIMITATIONS)
        if not status_valid:
            limitations.append("Attachment insight status was invalid; content was not used.")
        if status != "parsed" and not limitations:
            limitations.append("Attachment was not parsed; manual review is required.")
        projected.append({
            "filename": _single_line(raw.get("filename"), 160) or "attachment",
            "type": _enum(raw.get("type"), ATTACHMENT_TYPES, "unsupported"),
            "status": status,
            "summary": _bounded_text(raw.get("summary"), 600),
            "key_facts": (
                _string_list(raw.get("key_facts"), MAX_INSIGHT_FACTS)
                if status == "parsed"
                else []
            ),
            "limitations": limitations[:MAX_INSIGHT_LIMITATIONS],
        })
    return projected


def project_analysis_for_storage(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively rebuild only documented schema fields before SQLite."""
    projected = _string_object(data, ("summary", "priority", "priority_reason", "category"))
    _project_if_present(projected, data, "tags", lambda value: _string_list(value, MAX_STORED_ITEMS))
    _project_if_present(projected, data, "decision_brief", _project_decision_brief)
    _project_if_present(projected, data, "conversation_timeline", _project_timeline)
    _project_if_present(projected, data, "attachment_insights", project_attachment_insights)
    _project_if_present(projected, data, "risk_flags", _project_risks)
    _project_if_present(projected, data, "suggested_actions", _project_actions)
    _project_if_present(projected, data, "reply_draft", _project_reply_draft)
    _project_if_present(projected, data, "analysis_engine", _project_engine)
    return projected


def _project_decision_brief(value: Any) -> dict[str, Any]:
    projected = _string_object(value, ("one_line_conclusion", "requested_outcome", "confidence"))
    if not isinstance(value, dict):
        return projected
    _project_if_present(
        projected, value, "next_steps",
        lambda items: _object_list(items, lambda item: _string_object(
            item, ("step", "owner_hint", "due_hint", "source")
        ), 4),
    )
    _project_if_present(
        projected, value, "key_facts",
        lambda items: _object_list(
            items, lambda item: _string_object(item, ("label", "value", "source"))
        ),
    )
    _project_if_present(projected, value, "must_check", lambda items: _string_list(items, MAX_STORED_ITEMS))
    _project_if_present(projected, value, "missing_info", lambda items: _string_list(items, MAX_STORED_ITEMS))
    _project_if_present(projected, value, "reply_recommendation", _project_reply_recommendation)
    return projected


def _project_reply_recommendation(value: Any) -> dict[str, Any]:
    projected = _string_object(value, ("reply_type", "reason"))
    if isinstance(value, dict) and isinstance(value.get("should_reply"), bool):
        projected["should_reply"] = value["should_reply"]
    return projected


def _project_timeline(value: Any) -> dict[str, Any]:
    projected = _string_object(value, (
        "previous_context", "current_status", "status_reason", "latest_external_request",
        "latest_internal_commitment", "confidence",
    ))
    if isinstance(value, dict):
        _project_if_present(
            projected, value, "open_items",
            lambda items: _object_list(
                items, lambda item: _string_object(item, ("item", "owner_hint", "due_hint", "source"))
            ),
        )
    return projected


def _project_risks(value: Any) -> list[dict[str, Any]]:
    return _object_list(
        value,
        lambda item: _string_object(item, ("type", "level", "evidence", "recommendation")),
    )


def _project_actions(value: Any) -> list[dict[str, Any]]:
    return _object_list(
        value,
        lambda item: _string_object(item, ("type", "description", "owner_hint", "due_hint")),
    )


def _project_reply_draft(value: Any) -> dict[str, Any]:
    projected = _string_object(value, ("subject", "body"))
    if not isinstance(value, dict):
        return projected
    if isinstance(value.get("needs_human_review"), bool):
        projected["needs_human_review"] = value["needs_human_review"]
    _project_if_present(
        projected, value, "review_reasons", lambda items: _string_list(items, MAX_STORED_ITEMS)
    )
    return projected


def _project_engine(value: Any) -> dict[str, Any]:
    return _string_object(value, ("source", "label"))


def _string_object(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        field: _bounded_text(value.get(field), MAX_STORED_TEXT)
        for field in fields
        if field in value
    }


def _object_list(
    value: Any,
    projector: Callable[[Any], dict[str, Any]],
    limit: int = MAX_STORED_ITEMS,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [projector(item) for item in value[:limit] if isinstance(item, dict)]


def _project_if_present(
    target: dict[str, Any],
    source: dict[str, Any],
    field: str,
    projector: Callable[[Any], Any],
) -> None:
    if field in source:
        target[field] = projector(source[field])


def _enum(value: Any, allowed: set[str], fallback: str) -> str:
    return value if isinstance(value, str) and value in allowed else fallback


def _string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        text
        for item in value[:limit]
        if isinstance(item, str) and (text := _bounded_text(item, 240))
    ]


def _bounded_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\x00", " ").strip()[:limit]


def _single_line(value: Any, limit: int) -> str:
    return " ".join(_bounded_text(value, limit).split())[:limit]
