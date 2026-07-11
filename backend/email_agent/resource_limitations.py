"""Reason-coded safe projections for frontend resource-collection limitations."""

from __future__ import annotations

from typing import Any

from .analysis_schema import ATTACHMENT_TYPES


MAX_FRONTEND_RESOURCE_LIMITATIONS = 8
MAX_RESOURCE_LIMITATIONS = 9
MAX_RESOURCE_LIMITATION_INPUTS = 32

UNSUPPORTED_LIMITATION = "Resource type is not supported."
BOUNDED_LIMITATION = "Resource exceeded a configured frontend limit."
UNAVAILABLE_LIMITATION = (
    "Resource was unavailable from verified current-message controls; "
    "body analysis continued."
)
FAILED_LIMITATION = (
    "Resource could not be read from the current Tencent Exmail session; "
    "body analysis continued."
)
TIMEOUT_LIMITATION = (
    "Resource collection timed out; body analysis continued without this resource."
)
OMISSION_LIMITATION = (
    "Additional current-message resource candidates were omitted by bounded collection."
)
OPERATIONAL_LIMITATION = (
    "Attachment resources are temporarily unavailable; body analysis continued."
)

RESOURCE_LIMITATION_CODES = {
    "unsupported_type",
    "frontend_limit",
    "resource_unavailable",
    "resource_read_failed",
    "collection_timeout",
    "candidate_omission",
    "operational_failure",
}

_CANONICAL_LIMITATIONS = {
    "unsupported_type": UNSUPPORTED_LIMITATION,
    "frontend_limit": BOUNDED_LIMITATION,
    "resource_unavailable": UNAVAILABLE_LIMITATION,
    "resource_read_failed": FAILED_LIMITATION,
    "collection_timeout": TIMEOUT_LIMITATION,
    "candidate_omission": OMISSION_LIMITATION,
    "operational_failure": OPERATIONAL_LIMITATION,
}
_FAILED_CODES = {"resource_read_failed", "collection_timeout", "operational_failure"}
_UNSUPPORTED_TYPE_CODES = {"unsupported_type", "candidate_omission", "operational_failure"}


def project_resource_limitations(
    value: Any,
    *,
    allow_operational: bool = True,
) -> list[dict[str, object]]:
    """Project codes and reserve aggregate/operational slots without text inference."""
    if not isinstance(value, list):
        return []
    frontend: list[dict[str, object]] = []
    aggregate: dict[str, object] | None = None
    operational: dict[str, object] | None = None
    for raw in value[:MAX_RESOURCE_LIMITATION_INPUTS]:
        if not isinstance(raw, dict):
            continue
        code = _limitation_code(raw.get("code"), allow_operational)
        if code is None:
            continue
        projected = _project_one(raw, code)
        if code == "operational_failure":
            operational = projected
        elif code == "candidate_omission":
            aggregate = projected
        elif len(frontend) < MAX_FRONTEND_RESOURCE_LIMITATIONS:
            frontend.append(projected)

    if aggregate is not None:
        if len(frontend) >= MAX_FRONTEND_RESOURCE_LIMITATIONS:
            frontend[-1] = aggregate
        else:
            frontend.append(aggregate)
    projected_items = frontend[:MAX_FRONTEND_RESOURCE_LIMITATIONS]
    if operational is not None:
        projected_items.append(operational)
    return projected_items[:MAX_RESOURCE_LIMITATIONS]


def resource_limitation_insights(value: Any) -> list[dict[str, object]]:
    """Convert safe reason codes into deterministic non-parsed insights."""
    insights: list[dict[str, object]] = []
    for item in project_resource_limitations(value):
        code = str(item["code"])
        status = "failed" if code in _FAILED_CODES else "unavailable"
        resource_type = str(item["type"])
        insights.append({
            "filename": item["filename"],
            "type": resource_type,
            "status": status,
            "summary": _generic_summary(resource_type, status, code),
            "key_facts": [],
            "limitations": [item["limitation"]],
        })
    return insights


def _project_one(raw: dict[str, Any], code: str) -> dict[str, object]:
    resource_type = (
        "unsupported"
        if code in _UNSUPPORTED_TYPE_CODES
        else _resource_type(raw.get("type"))
    )
    return {
        "code": code,
        "filename": _safe_filename(raw.get("filename")),
        "type": resource_type,
        "size": _safe_size(raw.get("size")),
        "limitation": _CANONICAL_LIMITATIONS[code],
    }


def _limitation_code(value: Any, allow_operational: bool) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized not in RESOURCE_LIMITATION_CODES:
        return None
    if normalized == "operational_failure" and not allow_operational:
        return None
    return normalized


def _resource_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ATTACHMENT_TYPES else "unsupported"


def _safe_size(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    parsed = int(value)
    return parsed if 0 <= parsed <= 2**31 - 1 else 0


def _safe_filename(value: Any) -> str:
    normalized = " ".join(str(value or "").replace("\x00", " ").split())
    basename = normalized.replace("\\", "/").split("/")[-1]
    safe = "".join("_" if char in '<>:"|?*' else char for char in basename)
    return safe.lstrip(".").strip()[:160] or "resource"


def _generic_summary(resource_type: str, status: str, code: str) -> str:
    if code == "operational_failure":
        return "Attachment resources were unavailable; body analysis continued."
    if code == "candidate_omission":
        return "Additional attachment candidates were omitted by bounded collection."
    if resource_type == "unsupported":
        return "Attachment type is unsupported; body analysis continued."
    if status == "failed":
        return "Attachment could not be read; body analysis continued."
    return "Attachment was unavailable; body analysis continued."
