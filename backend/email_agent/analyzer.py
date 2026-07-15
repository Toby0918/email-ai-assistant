"""Current email analysis orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .analysis_budget import (
    PARSER_MAX_SECONDS,
    RESPONSE_MARGIN_SECONDS,
    AnalysisBudget,
)
from .analysis_model_routes import (
    AnalysisError,
    AnalysisRouteContext,
    build_analysis_prompt,
    route_analysis,
)
from .analysis_projection import project_attachment_insights
from .attachment_model_context import AttachmentAnalysisBundle
from .attachment_parser import parse_attachment_bundles
from .attachment_storage import StoredAttachment
from .config import AppConfig, load_config
from .email_cleaner import clean_email_body
from .prompt_context import normalize_text_list
from .resource_limitations import resource_limitation_insights
from .rule_analyzer import build_rule_based_analysis
from .thread_timeline import TimelineBuild, build_timeline_skeleton


MAX_ATTACHMENT_METADATA_ITEMS = 8
MAX_STORED_ATTACHMENTS = 5


def analyze_current_email(
    email: dict[str, Any],
    llm_generate: Callable[[str], str] | None = None,
    analysis_engine_label: str | None = None,
    *,
    config: AppConfig | None = None,
    budget: AnalysisBudget | None = None,
    runtime_cards: tuple[object, ...] = (),
) -> dict[str, Any]:
    current_config = config or load_config()
    current_budget = budget or AnalysisBudget.start()
    subject = _required_text(email, "subject")
    sender = _required_text(email, "from")
    clean_body = clean_email_body(email.get("body_text"), email.get("body_html"))
    if not clean_body:
        raise AnalysisError("Email body is empty.")
    timeline = _build_timeline(email.get("thread_segments"), current_config)
    bundles = _parse_bundles(email.get("stored_attachments"), current_budget)
    insights = _attachment_insights(bundles, email.get("resource_limitations"))
    fallback = build_rule_based_analysis(
        subject, sender, clean_body, attachment_insights=insights,
        conversation_timeline=timeline.public_timeline,
    )
    context = _route_context(
        email, subject, sender, clean_body, timeline, bundles, insights,
        fallback, current_config, current_budget, runtime_cards,
    )
    return route_analysis(context, llm_generate, analysis_engine_label)


def _route_context(
    email: dict[str, Any], subject: str, sender: str, clean_body: str,
    timeline: TimelineBuild, bundles: tuple[AttachmentAnalysisBundle, ...],
    insights: list[dict[str, object]], fallback: dict[str, Any],
    config: AppConfig, budget: AnalysisBudget, runtime_cards: tuple[object, ...],
) -> AnalysisRouteContext:
    return AnalysisRouteContext(
        subject=subject, sender=sender, clean_body=clean_body,
        attachments=_normalize_attachments(email.get("attachments")),
        recipients=normalize_text_list(email.get("to")),
        cc=normalize_text_list(email.get("cc")),
        sent_at=_optional_text(email.get("sent_at"), 160), timeline=timeline,
        attachment_insights=insights, attachment_bundles=bundles,
        fallback=fallback, config=config, budget=budget,
        runtime_cards=runtime_cards if type(runtime_cards) is tuple else (),
    )


def _build_timeline(value: Any, config: AppConfig) -> TimelineBuild:
    segments = value if isinstance(value, list) else []
    try:
        return build_timeline_skeleton(segments, config.internal_email_domains)
    except Exception:
        return TimelineBuild(_failed_public_timeline(), (), ())


def _failed_public_timeline() -> dict[str, object]:
    return {
        "previous_context": "未能重建可见会话；仅使用当前邮件正文。",
        "current_status": "unknown",
        "status_reason": "会话时间线处理失败，无法判断历史请求是否解决；当前邮件正文分析继续。",
        "latest_external_request": "",
        "latest_internal_commitment": "",
        "open_items": [{
            "item": "人工核查完整可见会话和未解决请求。",
            "owner_hint": "internal_follow_up", "due_hint": "", "source": "thread",
        }],
        "confidence": "low",
    }


def _parse_bundles(value: Any, budget: AnalysisBudget) -> tuple[AttachmentAnalysisBundle, ...]:
    items = _stored_attachments(value)
    if not items:
        return ()
    deadline = budget.stage_deadline(
        PARSER_MAX_SECONDS, reserve_seconds=RESPONSE_MARGIN_SECONDS
    )
    try:
        return tuple(parse_attachment_bundles(items, deadline=deadline))
    except Exception:
        return tuple(_failed_attachment_bundle(item) for item in items)


def _failed_attachment_bundle(item: StoredAttachment) -> AttachmentAnalysisBundle:
    insight = {
        "filename": item.safe_filename,
        "type": item.type,
        "status": "failed",
        "summary": f"{item.type.upper()} attachment could not be parsed.",
        "key_facts": [],
        "limitations": [
            "Attachment parsing failed unexpectedly; email body and thread analysis continued without attachment content."
        ],
    }
    return AttachmentAnalysisBundle(insight, None)


def _attachment_insights(
    bundles: tuple[AttachmentAnalysisBundle, ...], limitations: Any
) -> list[dict[str, object]]:
    return project_attachment_insights([
        *(bundle.display_insight for bundle in bundles),
        *resource_limitation_insights(limitations),
    ])


def _normalize_attachments(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    attachments: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        filename = _optional_text(item.get("filename") or item.get("name"), 160)
        if filename:
            attachments.append({
                "filename": filename, "size": _optional_text(item.get("size"), 40),
                "type": _optional_text(item.get("type"), 40),
            })
        if len(attachments) >= MAX_ATTACHMENT_METADATA_ITEMS:
            break
    return attachments


def _stored_attachments(value: Any) -> list[StoredAttachment]:
    if not isinstance(value, list):
        return []
    return [
        item for item in value[:MAX_STORED_ATTACHMENTS]
        if isinstance(item, StoredAttachment)
    ]


def _required_text(email: dict[str, Any], key: str) -> str:
    value = str(email.get(key) or "").strip()
    if not value:
        raise AnalysisError(f"Missing required email field: {key}")
    return value


def _optional_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]
