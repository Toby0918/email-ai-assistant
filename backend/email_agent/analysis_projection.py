"""Allowlist projections for analysis results crossing model and SQLite boundaries."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .analysis_schema import (
    ATTACHMENT_STATUSES,
    ATTACHMENT_TYPES,
    REQUIRED_RESULT_FIELDS,
)


ATTACHMENT_INSIGHT_FIELDS = {
    "filename",
    "type",
    "status",
    "summary",
    "key_facts",
    "limitations",
}
STORED_ANALYSIS_FIELDS = {*REQUIRED_RESULT_FIELDS, "analysis_engine"}
MAX_ATTACHMENT_INSIGHTS = 8
MAX_INSIGHT_FACTS = 5
MAX_INSIGHT_LIMITATIONS = 8


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
    """Drop unknown top-level fields and re-project attachment insights before SQLite."""
    projected = {
        key: deepcopy(value)
        for key, value in data.items()
        if key in STORED_ANALYSIS_FIELDS
    }
    if "attachment_insights" in projected:
        projected["attachment_insights"] = project_attachment_insights(
            projected["attachment_insights"]
        )
    return projected


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
