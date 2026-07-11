"""Local API boundary helpers for current email analysis."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from .analyzer import AnalysisError, analyze_current_email
from .attachment_storage import (
    AttachmentInputError,
    AttachmentOperationError,
    StoredAttachment,
    cleanup_expired_attachments,
    store_attachment_files,
    validate_attachment_files,
)
from .config import AppConfig, load_config
from .resource_limitations import OPERATIONAL_LIMITATION, project_resource_limitations


def handle_analyze_current_email(
    payload: dict[str, Any],
    analyzer: Callable[[dict[str, Any]], dict[str, Any]] = analyze_current_email,
    config: AppConfig | None = None,
) -> dict[str, Any]:
    # First phase requires an explicit user click before any analysis runs.
    if payload.get("user_confirmed") is not True:
        return _error("USER_ACTION_REQUIRED", "User must click the analysis button first.")
    try:
        storage_config = config or load_config()
        attachment_files = payload.get("attachment_files", [])
        if not isinstance(attachment_files, list):
            raise AttachmentInputError("Attachment files must be a list.")
        validate_attachment_files(attachment_files, storage_config)
        stored_attachments, operational_limitations = _store_attachments_or_degrade(
            attachment_files,
            storage_config,
        )
        analysis_payload = dict(payload)
        analysis_payload.pop("attachment_files", None)
        analysis_payload["stored_attachments"] = stored_attachments
        analysis_payload["resource_limitations"] = project_resource_limitations(
            [*_limitation_items(payload.get("resource_limitations")), *operational_limitations]
        )
        return {
            "ok": True,
            "request_id": f"local-{uuid4().hex}",
            "analysis": analyzer(analysis_payload),
        }
    except AttachmentInputError:
        return _error("ATTACHMENT_INPUT_INVALID", "Attachment input is invalid or exceeds configured limits.")
    except AnalysisError as exc:
        return _error("ANALYSIS_FAILED", str(exc))


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _store_attachments_or_degrade(
    files: list[dict[str, object]], config: AppConfig
) -> tuple[list[StoredAttachment], list[dict[str, object]]]:
    try:
        cleanup_expired_attachments(config)
    except (AttachmentOperationError, OSError):
        return [], [_operational_limitation()]
    try:
        return store_attachment_files(files, config), []
    except (AttachmentOperationError, OSError):
        return [], [_operational_limitation()]


def _operational_limitation() -> dict[str, object]:
    return {
        "filename": "resource",
        "type": "unsupported",
        "size": 0,
        "limitation": OPERATIONAL_LIMITATION,
    }


def _limitation_items(value: Any) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
