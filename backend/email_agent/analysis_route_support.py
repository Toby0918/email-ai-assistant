"""Small routing helpers shared by current-email model execution paths."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, TypeVar

from .attachment_model_context import (
    AttachmentAnalysisBundle,
    build_attachment_model_context,
)
from .attachment_media_context import (
    provider_attachment_candidate,
)
from .deepseek_analysis_schema import DeepSeekEnvelopeError
from .llm_client import LlmClientError
from .model_request import ModelAnalysisRequest
from .private_analysis_route import (
    PrivateAnalysisRouteError,
    prepare_private_deepseek_request,
)
from .private_context_gate import PrivateModelContext
from .prompt_context import EvidenceSource
from .thread_timeline import TimelineBuild


MODEL_AUGMENTATION_FIELDS = (
    "summary", "priority", "priority_reason", "category", "tags",
)
RESPONSE_FAILURE_REASONS = frozenset({"response_incomplete", "response_empty"})
_T = TypeVar("_T")


class AnalysisFallback(RuntimeError):
    def __init__(
        self, code: str, stage: str, detail: str = "not_applicable",
        context_scope: str | None = None, context_limited: bool = False,
        fallback_blocked: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage
        self.detail = detail
        self.context_scope = context_scope
        self.context_limited = context_limited
        self.provider: str | None = None
        self.model: str | None = None
        self.fallback_blocked = fallback_blocked


@dataclass(frozen=True, slots=True)
class ModelRun:
    analysis: dict[str, Any]
    context_scope: str = "current_only"
    context_limited: bool = False
    engine_source: str = "ai_model"
    engine_label: str = ""


def prepare_model_led_request(
    context: Any, build_context: Callable[..., tuple[str, dict[str, Any]]],
    *, provider: str | None = None,
) -> tuple[
    PrivateModelContext, str | ModelAnalysisRequest, dict[str, Any], TimelineBuild,
]:
    selected_provider = provider or context.config.llm_provider
    candidates = tuple(
        candidate
        for bundle in context.attachment_bundles
        if (candidate := provider_attachment_candidate(
            bundle.model_candidate, selected_provider,
        )) is not None
    )
    attachment_context = build_attachment_model_context(
        candidates
    )
    mapping = attachment_public_sources(context.attachment_bundles, attachment_context)
    prompt, sources = _deepseek_context(
        context, attachment_context, mapping, build_context, current_only=False,
    )
    current_prompt, current_sources = _deepseek_context(
        context, attachment_context, mapping, build_context, current_only=True,
    )
    private = prepare_private_deepseek_request(prompt, current_prompt, context)
    model_timeline = context.model_context.timeline
    if private.context_scope == "current_only":
        sources = current_sources
        model_timeline = context.model_context.current_timeline
    request: str | ModelAnalysisRequest = private.text
    if selected_provider == "openai":
        private = _with_openai_media(private, context.prepared_media_assets)
        request = private.model_request
        sources = _with_visual_sources(context, sources, context.prepared_media_assets)
    return private, request, sources, model_timeline


def _with_openai_media(private: PrivateModelContext, assets: object) -> PrivateModelContext:
    return PrivateModelContext(
        ModelAnalysisRequest(private.text, assets),
        private.selected_card_count,
        private.context_scope,
        private.context_limited,
    )


def _with_visual_sources(
    context: Any, sources: Mapping[str, Any], assets: Sequence[object],
) -> dict[str, Any]:
    visual_ids = {
        asset.source_id for asset in assets
        if isinstance(getattr(asset, "source_id", None), str)
    }
    visual_only_ids = {
        bundle.model_candidate.source_id
        for bundle in context.attachment_bundles
        if bundle.model_candidate is not None
        and bundle.model_candidate.visual_only
    }
    result = {
        source_id: replace(
            source,
            grounding_mode=(
                "visual"
                if source_id in visual_only_ids
                else "hybrid" if source.grounding_text.strip() else "visual"
            ),
        )
        if source_id in visual_ids else source
        for source_id, source in sources.items()
    }
    for source_id in visual_ids - set(result):
        source = _visual_source(context.attachment_bundles, source_id)
        if source is not None:
            result[source_id] = source
    return result


def _visual_source(
    bundles: Sequence[AttachmentAnalysisBundle], source_id: str,
) -> EvidenceSource | None:
    try:
        index = int(source_id.split(":", 1)[1])
        filename = str(bundles[index].display_insight.get("filename") or "attachment")
    except (IndexError, ValueError):
        return None
    return EvidenceSource(
        source_id, "attachment", "", f"attachment:{filename}",
        attachment_index=index, parsed=True, grounding_mode="visual",
    )


def prepare_conservative_request(
    context: Any, build_prompt: Callable[..., str],
) -> tuple[str, PrivateModelContext | None]:
    timeline = (
        context.model_context.timeline.public_timeline
        if context.config.llm_provider == "deepseek"
        else context.timeline.public_timeline
    )
    prompt = build_prompt(
        context.subject, context.sender, context.clean_body,
        attachments=context.attachments, recipients=context.recipients, cc=context.cc,
        sent_at=context.sent_at, conversation_timeline=timeline,
        attachment_insights=context.attachment_insights,
    )
    if context.config.llm_provider != "deepseek":
        return prompt, None
    current_prompt = build_prompt(
        context.subject, context.sender, context.clean_body,
        attachments=context.attachments, recipients=context.recipients, cc=context.cc,
        sent_at=context.sent_at,
        conversation_timeline=context.model_context.current_timeline.public_timeline,
        attachment_insights=context.attachment_insights,
    )
    private = prepare_private_deepseek_request(prompt, current_prompt, context)
    return private.text, private


def _deepseek_context(
    context: Any, attachment_context: Sequence[object], mapping: Mapping[str, str],
    build_context: Callable[..., tuple[str, dict[str, Any]]], *, current_only: bool,
) -> tuple[str, dict[str, Any]]:
    selected = context.model_context
    timeline = selected.current_timeline if current_only else selected.timeline
    thread_sources = selected.current_sources if current_only else selected.sources
    return build_context(
        subject=context.subject, sender=context.sender, recipients=context.recipients,
        cc=context.cc, sent_at=context.sent_at, clean_body=context.clean_body,
        timeline=timeline, attachment_context=attachment_context,
        attachment_public_sources=mapping, thread_sources=thread_sources,
    )


def attachment_public_sources(
    bundles: Sequence[AttachmentAnalysisBundle], accepted: Sequence[object],
) -> dict[str, str]:
    filenames = {
        bundle.model_candidate.source_id:
        str(bundle.display_insight.get("filename") or "attachment")
        for bundle in bundles if bundle.model_candidate is not None
    }
    return {
        item.source_id: f"attachment:{filenames[item.source_id]}"
        for item in accepted if item.source_id in filenames
    }


@contextmanager
def private_failure_context(private: object):
    """Keep the locally selected context scope on any later fixed failure."""
    try:
        yield
    except LlmClientError as exc:
        if not isinstance(private, PrivateModelContext):
            raise
        raise AnalysisFallback(
            exc.reason_code, llm_client_failure_stage(exc.reason_code),
            context_scope=private.context_scope,
            context_limited=private.context_limited,
            fallback_blocked=exc.fallback_blocked,
        ) from exc
    except PrivateAnalysisRouteError as exc:
        if not isinstance(private, PrivateModelContext) or exc.context_scope is not None:
            raise
        raise PrivateAnalysisRouteError(
            exc.code, exc.stage, private.context_scope, private.context_limited,
        ) from exc
    except AnalysisFallback as exc:
        if isinstance(private, PrivateModelContext) and exc.context_scope is None:
            exc.context_scope = private.context_scope
            exc.context_limited = private.context_limited
        raise


def run_stage(code: str, stage: str, action: Callable[[], Any]) -> Any:
    try:
        return action()
    except Exception as exc:
        raise AnalysisFallback(code, stage) from exc


def run_envelope_stage(action: Callable[[], _T]) -> _T:
    try:
        return action()
    except DeepSeekEnvelopeError as exc:
        raise AnalysisFallback(
            "provider_output_invalid", "envelope", exc.detail,
        ) from exc
    except Exception as exc:
        raise AnalysisFallback("provider_output_invalid", "envelope") from exc


def llm_client_failure_stage(reason_code: object) -> str:
    if type(reason_code) is str and reason_code in RESPONSE_FAILURE_REASONS:
        return "response"
    return "provider"


def rule_fallback(
    context: Any, context_scope: str | None = None,
    context_limited: bool = False,
) -> dict[str, Any]:
    selected = context.model_context
    scope = context_scope or selected.context_scope
    limited = context_limited if context_scope is not None else selected.context_limited
    return with_engine(context.fallback, "rule_fallback", "Rule fallback", scope, limited)


def with_engine(
    data: dict[str, Any], source: str, label: str,
    context_scope: str = "current_only", context_limited: bool = False,
) -> dict[str, Any]:
    engine: dict[str, Any] = {"source": source, "label": label}
    if context_scope == "relevant_history" or context_limited:
        engine.update({
            "context_scope": context_scope,
            "context_limited": bool(context_limited),
        })
    return {**data, "analysis_engine": engine}


def has_model_augmentation(result: dict[str, Any], fallback: dict[str, Any]) -> bool:
    return any(
        result.get(field) != fallback.get(field)
        for field in MODEL_AUGMENTATION_FIELDS
    )
