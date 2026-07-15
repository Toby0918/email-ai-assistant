"""Conservative and DeepSeek-led model routing for current-email analysis."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from .analysis_budget import AnalysisBudget
from .analysis_diagnostics import log_analysis_fallback
from .analysis_schema import validate_analysis_result
from .attachment_model_context import (
    AttachmentAnalysisBundle,
    build_attachment_model_context,
)
from .config import AppConfig
from .deepseek_analysis_schema import (
    DeepSeekEnvelopeError,
    parse_deepseek_analysis_v1,
    validate_envelope_evidence,
)
from .legacy_model_analysis import (
    AnalysisError,
    build_analysis_prompt,
    parse_legacy_result,
    validate_conservative_language,
)
from .llm_client import (
    LlmClientError,
    configured_analysis_engine_label,
    generate_analysis,
)
from .model_result_safety import merge_deepseek_analysis_v1
from .model_text_safety import validate_public_language
from .prompt_context import (
    DEEPSEEK_SYSTEM_PROMPT,
    build_deepseek_untrusted_context,
)
from .private_analysis_route import PrivateAnalysisRouteError, prepare_private_deepseek_prompt
from .private_analysis_route import validate_private_provider_output
from .thread_timeline import TimelineBuild


MODEL_AUGMENTATION_FIELDS = ("summary", "priority", "priority_reason", "category", "tags")
SUPPORTED_PRODUCTION_PROVIDERS = frozenset({"deepseek", "ollama", "openai"})
_RESPONSE_FAILURE_REASONS = frozenset({"response_incomplete", "response_empty"})
_T = TypeVar("_T")


class _AnalysisFallback(RuntimeError):
    def __init__(
        self,
        code: str,
        stage: str,
        detail: str = "not_applicable",
    ) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage
        self.detail = detail


@dataclass(frozen=True, slots=True)
class AnalysisRouteContext:
    subject: str
    sender: str
    clean_body: str
    attachments: list[dict[str, str]]
    recipients: list[str]
    cc: list[str]
    sent_at: str
    timeline: TimelineBuild
    attachment_insights: list[dict[str, object]]
    attachment_bundles: tuple[AttachmentAnalysisBundle, ...]
    fallback: dict[str, Any]
    config: AppConfig
    budget: AnalysisBudget
    runtime_cards: tuple[object, ...] = ()


def route_analysis(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str], str] | None,
    analysis_engine_label: str | None,
) -> dict[str, Any]:
    """Return one validated public model result or the complete rule fallback."""
    started_at = time.monotonic()
    try:
        if (
            llm_generate is None
            and context.config.llm_provider not in SUPPORTED_PRODUCTION_PROVIDERS
        ):
            raise _AnalysisFallback("provider_not_enabled", "routing")
        if _provider_timeout(context) is None:
            raise _AnalysisFallback("budget_exhausted", "budget")
        result = (
            _run_model_led(context, llm_generate)
            if _model_led(context.config)
            else _run_conservative(context, llm_generate)
        )
        engine_label = (
            analysis_engine_label or configured_analysis_engine_label(context.config)
        )
        result = _with_engine(result, "ai_model", engine_label)
    except LlmClientError as exc:
        failure = _AnalysisFallback(
            exc.reason_code, _llm_client_failure_stage(exc.reason_code)
        )
    except PrivateAnalysisRouteError as exc:
        failure = _AnalysisFallback(exc.code, exc.stage)
    except _AnalysisFallback as exc:
        failure = exc
    except Exception:
        failure = _AnalysisFallback("unexpected_analysis_error", "analysis")
    else:
        return result
    return _diagnosed_fallback(
        context, started_at, code=failure.code, stage=failure.stage,
        detail=failure.detail,
    )


def _run_model_led(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str], str] | None,
) -> dict[str, Any]:
    attachment_context = build_attachment_model_context(
        bundle.model_candidate
        for bundle in context.attachment_bundles
        if bundle.model_candidate is not None
    )
    mapping = _attachment_public_sources(context.attachment_bundles, attachment_context)
    prompt, sources = build_deepseek_untrusted_context(
        subject=context.subject, sender=context.sender, recipients=context.recipients,
        cc=context.cc, sent_at=context.sent_at, clean_body=context.clean_body,
        timeline=context.timeline, attachment_context=attachment_context,
        attachment_public_sources=mapping,
    )
    prompt = prepare_private_deepseek_prompt(prompt, context)
    timeout = _provider_timeout(context)
    if timeout is None:
        raise _AnalysisFallback("budget_exhausted", "budget")
    raw = _generate(prompt, context, llm_generate, timeout, DEEPSEEK_SYSTEM_PROMPT)
    validate_private_provider_output(raw)
    envelope = _run_envelope_stage(lambda: parse_deepseek_analysis_v1(raw))
    evidence = _run_stage(
        "evidence_invalid", "evidence",
        lambda: validate_envelope_evidence(envelope, sources),
    )
    merged = _run_stage(
        "safety_rejected_all", "safety",
        lambda: merge_deepseek_analysis_v1(
            envelope, fallback=context.fallback, sources=sources,
            timeline=context.timeline, evidence=evidence,
        ),
    )
    if not merged.used_model:
        raise _AnalysisFallback("safety_rejected_all", "safety")
    _run_stage(
        "public_schema_invalid", "schema",
        lambda: validate_analysis_result(merged.analysis),
    )
    _run_stage(
        "public_language_invalid", "language",
        lambda: validate_public_language(merged.analysis),
    )
    return merged.analysis


def _run_conservative(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str], str] | None,
) -> dict[str, Any]:
    prompt = build_analysis_prompt(
        context.subject, context.sender, context.clean_body,
        attachments=context.attachments, recipients=context.recipients, cc=context.cc,
        sent_at=context.sent_at, conversation_timeline=context.timeline.public_timeline,
        attachment_insights=context.attachment_insights,
    )
    if context.config.llm_provider == "deepseek":
        prompt = prepare_private_deepseek_prompt(prompt, context)
    timeout = _provider_timeout(context)
    if timeout is None:
        raise _AnalysisFallback("budget_exhausted", "budget")
    raw = _generate(prompt, context, llm_generate, timeout)
    if context.config.llm_provider == "deepseek":
        validate_private_provider_output(raw)
    result = _run_stage(
        "public_schema_invalid", "schema",
        lambda: parse_legacy_result(raw, fallback=context.fallback),
    )
    _run_stage(
        "public_language_invalid", "language",
        lambda: validate_conservative_language(result),
    )
    if not _has_model_augmentation(result, context.fallback):
        raise _AnalysisFallback("safety_rejected_all", "safety")
    return result


def _run_stage(code: str, stage: str, action: Callable[[], Any]) -> Any:
    try:
        return action()
    except Exception as exc:
        raise _AnalysisFallback(code, stage) from exc


def _run_envelope_stage(action: Callable[[], _T]) -> _T:
    try:
        return action()
    except DeepSeekEnvelopeError as exc:
        raise _AnalysisFallback(
            "envelope_invalid",
            "envelope",
            exc.detail,
        ) from exc
    except Exception as exc:
        raise _AnalysisFallback(
            "envelope_invalid",
            "envelope",
        ) from exc


def _generate(
    prompt: str,
    context: AnalysisRouteContext,
    injected: Callable[[str], str] | None,
    timeout: float,
    system_prompt: str = "",
) -> str:
    if injected is not None:
        return injected(prompt)
    return generate_analysis(
        prompt, system_prompt=system_prompt, config=context.config,
        timeout_seconds=timeout,
    )


def _attachment_public_sources(
    bundles: Sequence[AttachmentAnalysisBundle], accepted: Sequence[object]
) -> dict[str, str]:
    filenames = {
        bundle.model_candidate.source_id: str(bundle.display_insight.get("filename") or "attachment")
        for bundle in bundles if bundle.model_candidate is not None
    }
    return {
        item.source_id: f"attachment:{filenames[item.source_id]}"
        for item in accepted if item.source_id in filenames
    }


def _provider_timeout(context: AnalysisRouteContext) -> float | None:
    configured = (
        context.config.deepseek_timeout_seconds
        if context.config.llm_provider == "deepseek"
        else context.config.ollama_timeout_seconds
    )
    return context.budget.provider_timeout_seconds(configured)


def _model_led(config: AppConfig) -> bool:
    return config.llm_provider == "deepseek" and config.deepseek_output_mode == "model_led"


def _llm_client_failure_stage(reason_code: object) -> str:
    if type(reason_code) is str and reason_code in _RESPONSE_FAILURE_REASONS:
        return "response"
    return "provider"


def _rule_fallback(fallback: dict[str, Any]) -> dict[str, Any]:
    return _with_engine(fallback, "rule_fallback", "Rule fallback")


def _diagnosed_fallback(
    context: AnalysisRouteContext, started_at: float, *, code: str, stage: str,
    detail: str = "not_applicable",
) -> dict[str, Any]:
    provider = context.config.llm_provider
    model = (
        context.config.deepseek_model if provider == "deepseek"
        else "local-model" if provider == "ollama" else "none"
    )
    log_analysis_fallback(
        code=code, stage=stage, provider=provider, model=model,
        output_mode=context.config.deepseek_output_mode,
        detail=detail,
        elapsed_ms=max(0, int((time.monotonic() - started_at) * 1000)),
    )
    return _rule_fallback(context.fallback)


def _with_engine(data: dict[str, Any], source: str, label: str) -> dict[str, Any]:
    return {**data, "analysis_engine": {"source": source, "label": label}}


def _has_model_augmentation(result: dict[str, Any], fallback: dict[str, Any]) -> bool:
    return any(result.get(field) != fallback.get(field) for field in MODEL_AUGMENTATION_FIELDS)
