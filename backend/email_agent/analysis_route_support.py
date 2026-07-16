"""Small routing helpers shared by current-email model execution paths."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, TypeVar

from .analysis_budget import DEEPSEEK_PROVIDER_MAX_SECONDS
from .attachment_model_context import (
    AttachmentAnalysisBundle,
    build_attachment_model_context,
)
from .deepseek_analysis_schema import DeepSeekEnvelopeError
from .llm_client import LlmClientError
from .private_analysis_route import (
    PrivateAnalysisRouteError,
    prepare_private_deepseek_request,
)
from .private_context_gate import PrivateModelContext
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
    ) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage
        self.detail = detail
        self.context_scope = context_scope
        self.context_limited = context_limited


@dataclass(frozen=True, slots=True)
class ModelRun:
    analysis: dict[str, Any]
    context_scope: str = "current_only"
    context_limited: bool = False


def prepare_model_led_request(
    context: Any, build_context: Callable[..., tuple[str, dict[str, Any]]],
) -> tuple[PrivateModelContext, str, dict[str, Any], TimelineBuild]:
    attachment_context = build_attachment_model_context(
        bundle.model_candidate
        for bundle in context.attachment_bundles
        if bundle.model_candidate is not None
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
    return private, private.text, sources, model_timeline


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


def provider_timeout(context: Any) -> float | None:
    if context.config.llm_provider == "deepseek":
        return context.budget.provider_timeout_seconds(
            context.config.deepseek_timeout_seconds,
            maximum_seconds=DEEPSEEK_PROVIDER_MAX_SECONDS,
        )
    return context.budget.provider_timeout_seconds(context.config.ollama_timeout_seconds)


def model_led(config: Any) -> bool:
    return config.llm_provider == "deepseek" and config.deepseek_output_mode == "model_led"


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
