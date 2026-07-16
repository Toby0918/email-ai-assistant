"""Conservative and DeepSeek-led model routing for current-email analysis."""

from __future__ import annotations

import copy
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .analysis_budget import AnalysisBudget
from .analysis_route_support import (
    AnalysisFallback as _AnalysisFallback,
    ModelRun as _ModelRun,
    has_model_augmentation as _has_model_augmentation,
    llm_client_failure_stage as _llm_client_failure_stage,
    model_led as _model_led,
    prepare_conservative_request as _prepare_conservative_request,
    prepare_model_led_request as _prepare_model_led_request,
    private_failure_context as _private_failure_context,
    provider_timeout as _provider_timeout,
    rule_fallback as _rule_fallback,
    run_envelope_stage as _run_envelope_stage,
    run_stage as _run_stage,
    with_engine as _with_engine,
)
from .analysis_diagnostics import log_analysis_fallback
from .analysis_schema import validate_analysis_result
from .attachment_model_context import AttachmentAnalysisBundle
from .config import AppConfig
from .deepseek_analysis_schema import (
    parse_deepseek_analysis_v1,
    validate_envelope_evidence,
)
from .legacy_model_analysis import (
    AnalysisError,
    build_analysis_prompt,
    parse_legacy_result,
    validate_conservative_language,
)
from .llm_client import LlmClientError, configured_analysis_engine_label, generate_analysis
from .model_context_selection import ModelContextSelection
from .model_exact_fact_safety import (
    DEEPSEEK_CONSERVATIVE_SYSTEM_PROMPT,
    retain_conservative_backend_exact_facts,
)
from .model_result_safety import has_model_contribution, merge_deepseek_analysis_v1
from .model_text_safety import validate_public_language
from .prompt_context import DEEPSEEK_SYSTEM_PROMPT, build_deepseek_untrusted_context
from .private_analysis_route import PrivateAnalysisRouteError
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


def route_analysis(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str], str] | None,
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
            _run_model_led(context, llm_generate)
            if _model_led(context.config)
            else _run_conservative(context, llm_generate)
        )
        engine_label = (
            analysis_engine_label or configured_analysis_engine_label(context.config)
        )
        result = _with_engine(
            model_run.analysis,
            "ai_model",
            engine_label,
            model_run.context_scope,
            model_run.context_limited,
        )
    except LlmClientError as exc:
        failure = _AnalysisFallback(
            exc.reason_code, _llm_client_failure_stage(exc.reason_code)
        )
    except PrivateAnalysisRouteError as exc:
        failure = _AnalysisFallback(
            exc.code,
            exc.stage,
            context_scope=exc.context_scope,
            context_limited=exc.context_limited,
        )
    except _AnalysisFallback as exc:
        failure = exc
    except Exception:
        failure = _AnalysisFallback("unexpected_analysis_error", "analysis")
    else:
        return result
    return _diagnosed_fallback(
        context, started_at, code=failure.code, stage=failure.stage,
        detail=failure.detail, context_scope=failure.context_scope,
        context_limited=failure.context_limited,
    )


def _run_model_led(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str], str] | None,
) -> _ModelRun:
    private, prompt, sources, model_timeline = _prepare_model_led_request(
        context, build_deepseek_untrusted_context,
    )
    with _private_failure_context(private):
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
        return _ModelRun(
            analysis,
            private.context_scope,
            private.context_limited,
        )
def _run_conservative(
    context: AnalysisRouteContext,
    llm_generate: Callable[[str], str] | None,
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
        raw = _generate(prompt, context, llm_generate, timeout, system_prompt)
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


def _diagnosed_fallback(
    context: AnalysisRouteContext, started_at: float, *, code: str, stage: str,
    detail: str = "not_applicable", context_scope: str | None = None,
    context_limited: bool = False,
) -> dict[str, Any]:
    provider = context.config.llm_provider
    model = (
        context.config.deepseek_model if provider == "deepseek"
        else "local-model" if provider == "ollama" else "none"
    )
    log_analysis_fallback(
        code=code, stage=stage, provider=provider, model=model,
        output_mode=context.config.deepseek_output_mode, detail=detail,
        elapsed_ms=max(0, int((time.monotonic() - started_at) * 1000)),
    )
    return _rule_fallback(context, context_scope, context_limited)
