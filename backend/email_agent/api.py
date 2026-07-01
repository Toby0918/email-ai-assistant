"""Local API boundary helpers for current email analysis."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from .analyzer import AnalysisError, analyze_current_email


def handle_analyze_current_email(
    payload: dict[str, Any],
    analyzer: Callable[[dict[str, Any]], dict[str, Any]] = analyze_current_email,
) -> dict[str, Any]:
    # First phase requires an explicit user click before any analysis runs.
    if payload.get("user_confirmed") is not True:
        return _error("USER_ACTION_REQUIRED", "User must click the analysis button first.")
    try:
        return {
            "ok": True,
            "request_id": f"local-{uuid4().hex}",
            "analysis": analyzer(payload),
        }
    except AnalysisError as exc:
        return _error("ANALYSIS_FAILED", str(exc))


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}
