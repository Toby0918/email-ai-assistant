"""Safe projections for frontend resource-collection limitations."""

from __future__ import annotations

from typing import Any

from .analysis_schema import ATTACHMENT_TYPES


MAX_RESOURCE_LIMITATIONS = 8
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
OPERATIONAL_LIMITATION = (
    "Attachment resources are temporarily unavailable; body analysis continued."
)


def project_resource_limitations(value: Any) -> list[dict[str, object]]:
    """Return an exact, bounded, canonical frontend-limitation allowlist."""
    if not isinstance(value, list):
        return []
    projected: list[dict[str, object]] = []
    for raw in value[:MAX_RESOURCE_LIMITATIONS]:
        if not isinstance(raw, dict):
            continue
        resource_type = _resource_type(raw.get("type"))
        projected.append({
            "filename": _safe_filename(raw.get("filename")),
            "type": resource_type,
            "size": _safe_size(raw.get("size")),
            "limitation": _canonical_limitation(raw.get("limitation"), resource_type),
        })
    return projected


def resource_limitation_insights(value: Any) -> list[dict[str, object]]:
    """Convert safe collection limitations into deterministic non-parsed insights."""
    insights: list[dict[str, object]] = []
    for item in project_resource_limitations(value):
        limitation = str(item["limitation"])
        status = "failed" if limitation == FAILED_LIMITATION else "unavailable"
        insights.append({
            "filename": item["filename"],
            "type": item["type"],
            "status": status,
            "summary": _generic_summary(str(item["type"]), status, limitation),
            "key_facts": [],
            "limitations": [limitation],
        })
    return insights


def _canonical_limitation(value: Any, resource_type: str) -> str:
    text = " ".join(str(value or "").split()).lower()
    if "temporarily unavailable" in text:
        return OPERATIONAL_LIMITATION
    if resource_type == "unsupported":
        return UNSUPPORTED_LIMITATION
    if any(marker in text for marker in ("exceed", "limit", "omitted")):
        return BOUNDED_LIMITATION
    if any(marker in text for marker in ("could not be read", "read failed", "fetch failed")):
        return FAILED_LIMITATION
    return UNAVAILABLE_LIMITATION


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


def _generic_summary(resource_type: str, status: str, limitation: str) -> str:
    if limitation == OPERATIONAL_LIMITATION:
        return "Attachment resources were unavailable; body analysis continued."
    if resource_type == "unsupported":
        return "Attachment type is unsupported; body analysis continued."
    if status == "failed":
        return "Attachment could not be read; body analysis continued."
    return "Attachment was unavailable; body analysis continued."
