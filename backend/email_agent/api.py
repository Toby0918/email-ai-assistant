"""Local API boundary helpers for current email analysis."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from .analysis_budget import RESPONSE_MARGIN_SECONDS, AnalysisBudget
from .analyzer import AnalysisError, analyze_current_email
from .attachment_storage import (
    AttachmentInputError,
    AttachmentOperationError,
    StoredAttachment,
    cleanup_expired_attachments,
    remove_stored_attachments,
    store_attachment_files,
    validate_attachment_files,
)
from .config import AppConfig, load_config
from .resource_limitations import OPERATIONAL_LIMITATION, project_resource_limitations


_RESERVED_PRIVATE_PAYLOAD_FIELDS = frozenset({
    "runtime_cards",
    "private_context",
    "knowledge_cards",
    "placeholder_mapping",
    "card_id",
    "snapshot_id",
    "vault_id",
    "private_knowledge_enabled",
    "private_knowledge_authority_root",
    "private_knowledge_snapshot_path",
    "protected_roots",
    "project_container",
})


def handle_analyze_current_email(
    payload: dict[str, Any],
    analyzer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    config: AppConfig | None = None,
    *,
    budget: AnalysisBudget | None = None,
    runtime_cards: tuple[object, ...] = (),
) -> dict[str, Any]:
    # First phase requires an explicit user click before any analysis runs.
    if payload.get("user_confirmed") is not True:
        return _error("USER_ACTION_REQUIRED", "User must click the analysis button first.")
    cleanup_attachments: tuple[StoredAttachment, ...] = ()
    try:
        current_config = config or load_config()
        current_budget = budget or AnalysisBudget.start()
        attachment_files = payload.get("attachment_files", [])
        if not isinstance(attachment_files, list):
            raise AttachmentInputError("Attachment files must be a list.")
        validate_attachment_files(attachment_files, current_config)
        stored_attachments, operational_limitations = _store_attachments_or_degrade(
            attachment_files, current_config, current_budget,
        )
        cleanup_attachments = tuple(stored_attachments)
        analysis_payload = _without_reserved_private_fields(payload)
        analysis_payload.pop("attachment_files", None)
        analysis_payload["stored_attachments"] = list(cleanup_attachments)
        frontend_limitations = project_resource_limitations(
            _limitation_items(payload.get("resource_limitations")),
            allow_operational=False,
        )
        analysis_payload["resource_limitations"] = project_resource_limitations(
            [*frontend_limitations, *operational_limitations]
        )
        analysis = _run_analysis(
            analysis_payload, analyzer, current_config, current_budget, runtime_cards
        )
        return {
            "ok": True,
            "request_id": f"local-{uuid4().hex}",
            "analysis": analysis,
        }
    except AttachmentInputError:
        return _error("ATTACHMENT_INPUT_INVALID", "Attachment input is invalid or exceeds configured limits.")
    except AnalysisError as exc:
        return _error("ANALYSIS_FAILED", str(exc))
    finally:
        remove_stored_attachments(cleanup_attachments)


def _run_analysis(
    payload: dict[str, Any],
    analyzer: Callable[[dict[str, Any]], dict[str, Any]] | None,
    config: AppConfig,
    budget: AnalysisBudget,
    runtime_cards: tuple[object, ...],
) -> dict[str, Any]:
    if analyzer is not None:
        return analyzer(payload)
    return analyze_current_email(
        payload,
        config=config,
        budget=budget,
        runtime_cards=runtime_cards if type(runtime_cards) is tuple else (),
    )


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _without_reserved_private_fields(payload: dict[str, Any]) -> dict[str, Any]:
    analysis_payload = dict(payload)
    for field in _RESERVED_PRIVATE_PAYLOAD_FIELDS:
        analysis_payload.pop(field, None)
    return analysis_payload


def _store_attachments_or_degrade(
    files: list[dict[str, object]], config: AppConfig, budget: AnalysisBudget
) -> tuple[list[StoredAttachment], list[dict[str, object]]]:
    if _storage_time_exhausted(budget):
        return [], [_operational_limitation()]
    try:
        cleanup_expired_attachments(config)
    except (AttachmentOperationError, OSError):
        return [], [_operational_limitation()]
    if _storage_time_exhausted(budget):
        return [], [_operational_limitation()]
    try:
        stored = store_attachment_files(files, config)
    except (AttachmentOperationError, OSError):
        return [], [_operational_limitation()]
    if _storage_time_exhausted(budget):
        remove_stored_attachments(tuple(stored))
        return [], [_operational_limitation()]
    return stored, []


def _storage_time_exhausted(budget: AnalysisBudget) -> bool:
    return budget.expired(reserve_seconds=RESPONSE_MARGIN_SECONDS)


def _operational_limitation() -> dict[str, object]:
    return {
        "code": "operational_failure",
        "filename": "resource",
        "type": "unsupported",
        "size": 0,
        "limitation": OPERATIONAL_LIMITATION,
    }


def _limitation_items(value: Any) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
