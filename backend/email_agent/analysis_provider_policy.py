"""Provider selection, timeout, fallback, and safe diagnostic metadata."""

from __future__ import annotations

from typing import Any

from .analysis_budget import (
    DEEPSEEK_PROVIDER_MAX_SECONDS,
    PROVIDER_MAX_SECONDS,
    TEXT_FALLBACK_MIN_REMAINING_SECONDS,
)
from .analysis_route_support import AnalysisFallback, llm_client_failure_stage
from .llm_client import LlmClientError
from .private_analysis_route import PrivateAnalysisRouteError


def provider_timeout(context: Any, provider: str | None = None) -> float | None:
    selected = provider or context.config.llm_provider
    if selected == "deepseek":
        return context.budget.provider_timeout_seconds(
            context.config.deepseek_timeout_seconds,
            maximum_seconds=DEEPSEEK_PROVIDER_MAX_SECONDS,
        )
    if selected == "openai":
        return context.budget.provider_timeout_seconds(
            context.config.openai_timeout_seconds,
            maximum_seconds=PROVIDER_MAX_SECONDS,
        )
    return context.budget.provider_timeout_seconds(context.config.ollama_timeout_seconds)


def model_led(config: Any) -> bool:
    return config.llm_provider == "openai" or (
        config.llm_provider == "deepseek"
        and config.deepseek_output_mode == "model_led"
    )


def text_fallback_allowed(context: Any, failure: AnalysisFallback) -> bool:
    return (
        context.config.llm_provider == "openai"
        and context.config.text_fallback_provider == "deepseek"
        and not failure.fallback_blocked
        and failure.stage not in {"routing", "budget"}
        and failure.code not in {
            "privacy_preflight_rejected", "provider_output_placeholder_echo",
        }
    )


def text_fallback_budget_available(context: Any) -> bool:
    return context.budget.remaining_seconds() >= TEXT_FALLBACK_MIN_REMAINING_SECONDS


def text_fallback_timeout(context: Any) -> float | None:
    return context.budget.text_fallback_timeout_seconds(
        context.config.deepseek_timeout_seconds
    )


def provider_engine_label(config: Any, provider: str, *, fallback: bool = False) -> str:
    if provider == "openai":
        return "OpenAI GPT-5.6 Sol"
    if provider == "deepseek":
        name = (
            "DeepSeek V4 Pro"
            if config.deepseek_model == "deepseek-v4-pro"
            else "DeepSeek V4 Flash"
        )
        return name + (" text fallback" if fallback else "")
    return ""


def provider_failure(exc: Exception, context: Any, provider: str) -> AnalysisFallback:
    if isinstance(exc, AnalysisFallback):
        failure = exc
    elif isinstance(exc, LlmClientError):
        failure = AnalysisFallback(
            exc.reason_code, llm_client_failure_stage(exc.reason_code),
            fallback_blocked=exc.fallback_blocked,
        )
    elif isinstance(exc, PrivateAnalysisRouteError):
        failure = AnalysisFallback(
            exc.code, exc.stage, context_scope=exc.context_scope,
            context_limited=exc.context_limited,
        )
        failure.fallback_blocked = True
    else:
        failure = AnalysisFallback("unexpected_analysis_error", "analysis")
    if failure.provider is None:
        failure.provider = provider
        failure.model = provider_model(context, provider)
    return failure


def provider_model(context: Any, provider: str) -> str:
    if provider == "openai":
        return context.config.openai_model
    if provider == "deepseek":
        return context.config.deepseek_model
    if provider == "ollama":
        return "local-model"
    return "none"
