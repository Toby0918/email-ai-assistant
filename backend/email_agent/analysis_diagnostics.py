"""Sanitized local diagnostics for model-to-rule fallback events."""

from __future__ import annotations

import logging


FALLBACK_REASON_CODES = frozenset({
    "provider_not_enabled", "budget_exhausted", "missing_key",
    "unsupported_model", "provider_timeout", "provider_auth",
    "provider_permission_or_balance", "provider_rate_limit",
    "provider_connection_error", "provider_server_error",
    "provider_http_error", "provider_request_failed",
    "response_incomplete", "response_empty", "envelope_invalid",
    "evidence_invalid", "safety_rejected_all", "public_schema_invalid",
    "public_language_invalid", "unexpected_analysis_error",
})
FALLBACK_STAGES = frozenset({
    "routing", "budget", "provider", "response", "envelope",
    "evidence", "safety", "schema", "language", "analysis",
})
SAFE_PROVIDERS = frozenset({"deepseek", "ollama", "openai", "disabled"})
SAFE_MODELS = frozenset({"deepseek-v4-flash", "deepseek-v4-pro", "local-model", "none"})
SAFE_OUTPUT_MODES = frozenset({"model_led", "conservative"})

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def log_analysis_fallback(
    *, code: str, stage: str, provider: str, model: str,
    output_mode: str, elapsed_ms: int,
) -> None:
    safe_code = code if code in FALLBACK_REASON_CODES else "unexpected_analysis_error"
    safe_stage = stage if stage in FALLBACK_STAGES else "analysis"
    safe_provider = provider if provider in SAFE_PROVIDERS else "unknown"
    safe_model = model if model in SAFE_MODELS else "unknown"
    safe_mode = output_mode if output_mode in SAFE_OUTPUT_MODES else "unknown"
    safe_elapsed = elapsed_ms if type(elapsed_ms) is int and elapsed_ms >= 0 else 0
    logger.warning(
        "event=analysis_fallback code=%s stage=%s provider=%s model=%s "
        "output_mode=%s elapsed_ms=%d",
        safe_code, safe_stage, safe_provider, safe_model, safe_mode, safe_elapsed,
    )
