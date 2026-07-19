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
    "privacy_preflight_rejected", "provider_output_invalid",
    "evidence_invalid", "safety_rejected_all", "provider_output_placeholder_echo",
    "public_schema_invalid",
    "public_language_invalid", "unexpected_analysis_error",
})
FALLBACK_STAGES = frozenset({
    "routing", "budget", "provider", "response", "envelope",
    "evidence", "safety", "schema", "language", "analysis",
})
SAFE_PROVIDERS = frozenset({"deepseek", "ollama", "openai", "disabled"})
SAFE_MODELS = frozenset({
    "deepseek-v4-flash", "deepseek-v4-pro", "gpt-5.6-sol", "local-model", "none",
})
SAFE_OUTPUT_MODES = frozenset({"model_led", "conservative"})
FALLBACK_DETAILS = frozenset({
    "not_applicable",
    "json_syntax",
    "top_level_shape",
    "schema_version",
    "analysis_shape",
    "attachment_shape",
    "field_evidence_shape",
})
FALLBACK_EVENT_TEMPLATE = (
    "event=analysis_fallback code=%s stage=%s provider=%s model=%s "
    "output_mode=%s detail=%s elapsed_ms=%d"
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
logger.propagate = False
logger.addHandler(logging.NullHandler())


def _allowlisted_value(
    value: object,
    allowed: frozenset[str],
    fallback: str,
) -> str:
    if type(value) is not str or value not in allowed:
        return fallback
    return value


def log_analysis_fallback(
    *, code: str, stage: str, provider: str, model: str,
    output_mode: str, detail: str, elapsed_ms: int,
) -> None:
    safe_code = _allowlisted_value(
        code, FALLBACK_REASON_CODES, "unexpected_analysis_error"
    )
    safe_stage = _allowlisted_value(stage, FALLBACK_STAGES, "analysis")
    safe_provider = _allowlisted_value(provider, SAFE_PROVIDERS, "unknown")
    safe_model = _allowlisted_value(model, SAFE_MODELS, "unknown")
    safe_mode = _allowlisted_value(output_mode, SAFE_OUTPUT_MODES, "unknown")
    safe_detail = _allowlisted_value(
        detail,
        FALLBACK_DETAILS,
        "not_applicable",
    )
    if safe_code != "envelope_invalid":
        safe_detail = "not_applicable"
    safe_elapsed = elapsed_ms if type(elapsed_ms) is int and elapsed_ms >= 0 else 0
    logger.warning(
        FALLBACK_EVENT_TEMPLATE,
        safe_code, safe_stage, safe_provider, safe_model, safe_mode, safe_detail,
        safe_elapsed,
    )
