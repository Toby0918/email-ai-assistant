"""Conservative and DeepSeek-led model routing for current-email analysis."""

from __future__ import annotations

import copy
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from .analysis_budget import AnalysisBudget
from .analysis_route_support import (
    AnalysisFallback as _AnalysisFallback,
    ModelRun as _ModelRun,
    has_model_augmentation as _has_model_augmentation,
    prepare_conservative_request as _prepare_conservative_request,
    prepare_model_led_request as _prepare_model_led_request,
    private_failure_context as _private_failure_context,
    rule_fallback as _rule_fallback,
    run_envelope_stage as _run_envelope_stage,
    run_stage as _run_stage,
    with_engine as _with_engine,
)
from .analysis_provider_policy import (
    model_led as _model_led,
    provider_engine_label as _provider_engine_label,
    provider_failure as _provider_failure,
    provider_model as _provider_model,
    provider_timeout as _provider_timeout,
    text_fallback_allowed as _text_fallback_allowed,
    text_fallback_budget_available as _text_fallback_budget_available,
    text_fallback_timeout as _text_fallback_timeout,
)
from .analysis_diagnostics import log_analysis_fallback
from .analysis_schema import validate_analysis_result
from .attachment_model_context import AttachmentAnalysisBundle
from .config import AppConfig
from .deepseek_analysis_schema import parse_deepseek_analysis_v1, validate_envelope_evidence
from .legacy_model_analysis import (
    AnalysisError,
    build_analysis_prompt,
    parse_legacy_result,
    validate_conservative_language,
)
from .llm_client import configured_analysis_engine_label, generate_analysis
from .model_context_selection import ModelContextSelection
from .model_exact_fact_safety import (
    DEEPSEEK_CONSERVATIVE_SYSTEM_PROMPT,
    retain_conservative_backend_exact_facts,
)
from .model_result_safety import has_model_contribution, merge_deepseek_analysis_v1
from .model_request import ModelAnalysisRequest
from .model_text_safety import validate_public_language
from .multimodal_media import PreparedMediaAsset
from .prompt_context import DEEPSEEK_SYSTEM_PROMPT, OPENAI_MULTIMODAL_SYSTEM_PROMPT
from .prompt_context import build_deepseek_untrusted_context
from .private_analysis_route import validate_private_provider_output
from .thread_timeline import TimelineBuild


SUPPORTED_PRODUCTION_PROVIDERS = frozenset({"deepseek", "ollama", "openai"})


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
    model_context: ModelContextSelection
    attachment_insights: list[dict[str, object]]
    attachment_bundles: tuple[AttachmentAnalysisBundle, ...]
    fallback: dict[str, Any]
    config: AppConfig
    budget: AnalysisBudget
    runtime_cards: tuple[object, ...] = ()
    prepared_media_assets: tuple[PreparedMediaAsset, ...] = field(default=(), repr=False)


def route_analysis(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str | ModelAnalysisRequest], str] | None,
    analysis_engine_label: str | None,
) -> dict[str, Any]:
    """Return one validated public model result or the complete rule fallback."""
    started_at = time.monotonic()
    try:
        provider_enabled = context.config.llm_provider in SUPPORTED_PRODUCTION_PROVIDERS
        if llm_generate is None and not provider_enabled:
            raise _AnalysisFallback("provider_not_enabled", "routing")
        if _provider_timeout(context) is None:
            raise _AnalysisFallback("budget_exhausted", "budget")
        model_run = (
            _run_primary_model_led(context, llm_generate)
            if _model_led(context.config)
            else _run_conservative(context, llm_generate)
        )
        engine_label = (
            model_run.engine_label or analysis_engine_label
            or configured_analysis_engine_label(context.config)
        )
        result = _with_engine(
            model_run.analysis,
            model_run.engine_source,
            engine_label,
            model_run.context_scope,
            model_run.context_limited,
        )
    except Exception as exc:
        failure = _provider_failure(exc, context, context.config.llm_provider)
    else:
        return result
    return _diagnosed_fallback(
        context, started_at, code=failure.code, stage=failure.stage,
        detail=failure.detail, context_scope=failure.context_scope,
        context_limited=failure.context_limited, provider=failure.provider,
        model=failure.model,
    )


def _run_primary_model_led(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str | ModelAnalysisRequest], str] | None,
) -> _ModelRun:
    primary = context.config.llm_provider
    try:
        return _attempt_model_led(context, llm_generate, provider=primary)
    except _AnalysisFallback as failure:
        if not _text_fallback_allowed(context, failure):
            raise
        if not _text_fallback_budget_available(context):
            raise
        return _attempt_model_led(
            context, llm_generate, provider="deepseek", text_fallback=True,
        )


def _attempt_model_led(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str | ModelAnalysisRequest], str] | None,
    *, provider: str, text_fallback: bool = False,
) -> _ModelRun:
    try:
        return _run_model_led(
            context, llm_generate, provider=provider,
            text_fallback=text_fallback,
        )
    except Exception as exc:
        raise _provider_failure(exc, context, provider)


def _run_model_led(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str | ModelAnalysisRequest], str] | None,
    *, provider: str, text_fallback: bool = False,
) -> _ModelRun:
    private, request, sources, model_timeline = _prepare_model_led_request(
        context, build_deepseek_untrusted_context, provider=provider,
    )
    with _private_failure_context(private):
        timeout = (
            _text_fallback_timeout(context)
            if text_fallback else _provider_timeout(context, provider)
        )
        if timeout is None:
            raise _AnalysisFallback("budget_exhausted", "budget")
        system_prompt = (
            OPENAI_MULTIMODAL_SYSTEM_PROMPT
            if provider == "openai" else DEEPSEEK_SYSTEM_PROMPT
        )
        raw = _generate(
            request, context, llm_generate, timeout, system_prompt, provider,
        )
        analysis = _accepted_model_analysis(
            raw, context, sources, model_timeline,
        )
        return _ModelRun(
            analysis,
            private.context_scope,
            private.context_limited,
            "ai_model",
            _provider_engine_label(
                context.config, provider, fallback=text_fallback,
            ),
        )


def _accepted_model_analysis(
    raw: str, context: AnalysisRouteContext, sources: dict[str, Any],
    model_timeline: TimelineBuild,
) -> dict[str, Any]:
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
            timeline=model_timeline, evidence=evidence,
        ),
    )
    analysis = copy.deepcopy(merged.analysis)
    analysis["conversation_timeline"] = copy.deepcopy(
        context.fallback["conversation_timeline"]
    )
    if not merged.used_model or not has_model_contribution(
        analysis, context.fallback
    ):
        raise _AnalysisFallback("safety_rejected_all", "safety")
    _run_stage(
        "public_schema_invalid", "schema",
        lambda: validate_analysis_result(analysis),
    )
    _run_stage(
        "public_language_invalid", "language",
        lambda: validate_public_language(analysis),
    )
    return analysis


def _run_conservative(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str | ModelAnalysisRequest], str] | None,
) -> _ModelRun:
    prompt, private = _prepare_conservative_request(context, build_analysis_prompt)
    with _private_failure_context(private):
        timeout = _provider_timeout(context)
        if timeout is None:
            raise _AnalysisFallback("budget_exhausted", "budget")
        system_prompt = (
            DEEPSEEK_CONSERVATIVE_SYSTEM_PROMPT
            if context.config.llm_provider == "deepseek" else ""
        )
        raw = _generate(
            prompt, context, llm_generate, timeout, system_prompt,
            context.config.llm_provider,
        )
        if context.config.llm_provider == "deepseek":
            validate_private_provider_output(raw)
        result = _run_stage(
            "provider_output_invalid", "schema",
            lambda: parse_legacy_result(raw, fallback=context.fallback),
        )
        if context.config.llm_provider == "deepseek":
            result = retain_conservative_backend_exact_facts(result, context.fallback)
        _run_stage(
            "public_language_invalid", "language",
            lambda: validate_conservative_language(result),
        )
        if not _has_model_augmentation(result, context.fallback):
            raise _AnalysisFallback("safety_rejected_all", "safety")
        return _ModelRun(
            result,
            private.context_scope if private is not None else "current_only",
            private.context_limited if private is not None else False,
        )


def _generate(
    request: str | ModelAnalysisRequest,
    context: AnalysisRouteContext,
    injected: Callable[[str | ModelAnalysisRequest], str] | None,
    timeout: float,
    system_prompt: str = "",
    provider: str | None = None,
) -> str:
    if injected is not None:
        return injected(request)
    selected = provider or context.config.llm_provider
    config = (
        context.config if selected == context.config.llm_provider
        else replace(context.config, llm_provider=selected)
    )
    return generate_analysis(
        request, system_prompt=system_prompt, config=config,
        timeout_seconds=timeout,
    )


def _diagnosed_fallback(
    context: AnalysisRouteContext, started_at: float, *, code: str, stage: str,
    detail: str = "not_applicable", context_scope: str | None = None,
    context_limited: bool = False, provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    selected_provider = provider or context.config.llm_provider
    selected_model = model or _provider_model(context, selected_provider)
    log_analysis_fallback(
        code=code, stage=stage, provider=selected_provider, model=selected_model,
        output_mode=context.config.deepseek_output_mode, detail=detail,
        elapsed_ms=max(0, int((time.monotonic() - started_at) * 1000)),
    )
    return _rule_fallback(context, context_scope, context_limited)
