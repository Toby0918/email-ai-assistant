"""Content-free route adapter around the private DeepSeek context gate."""

from __future__ import annotations

from typing import Any, Protocol

from .private_context_gate import (
    MAX_HEADER_CHARACTERS,
    PrivateContextFallbackCode,
    PrivateModelContext,
    PrivateModelRequest,
    build_private_model_context,
    provider_output_contains_placeholder,
    provider_output_contains_private_artifact,
    provider_output_is_private_safe,
)
from .prompt_context import MAX_DEEPSEEK_THREAD_SOURCES
from .thread_timeline import ThreadSource


class _PrivateRouteContext(Protocol):
    sender: str
    recipients: list[str]
    cc: list[str]
    timeline: object
    model_context: object
    fallback: dict[str, Any]
    runtime_cards: tuple[object, ...]
    budget: object


class PrivateAnalysisRouteError(RuntimeError):
    """A fixed refusal that carries no prompt or private data."""

    def __init__(
        self,
        code: str,
        stage: str,
        context_scope: str | None = None,
        context_limited: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage
        self.context_scope = context_scope
        self.context_limited = context_limited


def prepare_private_deepseek_prompt(
    prompt: str,
    context: _PrivateRouteContext,
) -> str:
    headers = _participant_headers(context, context.timeline)
    if headers is None:
        raise PrivateAnalysisRouteError("safety_rejected_all", "safety")
    private = build_private_model_context(
        PrivateModelRequest(
            prompt,
            headers,
        ),
        context.fallback,
        context.runtime_cards,
        context.budget,
    )
    if private is PrivateContextFallbackCode.BUDGET:
        raise PrivateAnalysisRouteError("budget_exhausted", "budget")
    if not isinstance(private, PrivateModelContext):
        raise PrivateAnalysisRouteError("safety_rejected_all", "safety")
    return private.text


def prepare_private_deepseek_request(
    prompt: str,
    current_only_prompt: str,
    context: _PrivateRouteContext,
) -> PrivateModelContext:
    """Preflight selected history, then locally downgrade to current-only."""
    selection = context.model_context
    primary_headers = _participant_headers(context, selection.timeline)
    current_headers = _participant_headers(context, selection.current_timeline)
    if primary_headers is None:
        primary_headers = ("\n",)
    if current_headers is None:
        raise PrivateAnalysisRouteError("privacy_preflight_rejected", "safety")
    private = build_private_model_context(
        PrivateModelRequest(
            prompt=prompt,
            header_values=primary_headers,
            current_only_prompt=current_only_prompt,
            current_only_header_values=current_headers,
            context_scope=selection.context_scope,
            context_limited=selection.context_limited,
        ),
        context.fallback,
        context.runtime_cards,
        context.budget,
    )
    if private is PrivateContextFallbackCode.BUDGET:
        raise PrivateAnalysisRouteError("budget_exhausted", "budget")
    if not isinstance(private, PrivateModelContext):
        raise PrivateAnalysisRouteError("privacy_preflight_rejected", "safety")
    return private


def _participant_headers(
    context: _PrivateRouteContext, timeline: object,
) -> tuple[str, ...] | None:
    if type(context.recipients) is not list or type(context.cc) is not list:
        return None
    try:
        sources = timeline.sources
    except Exception:
        return None
    if type(sources) is not tuple:
        return None
    values: list[object] = [context.sender, *context.recipients, *context.cc]
    for source in sources[:MAX_DEEPSEEK_THREAD_SOURCES]:
        if not isinstance(source, ThreadSource):
            return None
        values.extend((source.sender, source.recipient))
    if any(
        not isinstance(value, str) or len(value) >= MAX_HEADER_CHARACTERS
        for value in values
    ):
        return None
    return tuple(values)


def validate_private_provider_output(raw: object) -> None:
    if not provider_output_is_private_safe(raw):
        code = (
            "provider_output_placeholder_echo"
            if provider_output_contains_placeholder(raw)
            else "safety_rejected_all"
            if provider_output_contains_private_artifact(raw)
            else "provider_output_invalid"
        )
        raise PrivateAnalysisRouteError(code, "safety")
