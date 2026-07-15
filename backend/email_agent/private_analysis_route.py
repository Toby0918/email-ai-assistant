"""Content-free route adapter around the private DeepSeek context gate."""

from __future__ import annotations

from typing import Any, Protocol

from .private_context_gate import (
    MAX_HEADER_CHARACTERS,
    PrivateContextFallbackCode,
    PrivateModelContext,
    PrivateModelRequest,
    build_private_model_context,
    provider_output_is_private_safe,
)
from .prompt_context import MAX_DEEPSEEK_THREAD_SOURCES
from .thread_timeline import ThreadSource


class _PrivateRouteContext(Protocol):
    sender: str
    recipients: list[str]
    cc: list[str]
    timeline: object
    fallback: dict[str, Any]
    runtime_cards: tuple[object, ...]
    budget: object


class PrivateAnalysisRouteError(RuntimeError):
    """A fixed refusal that carries no prompt or private data."""

    def __init__(self, code: str, stage: str) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage


def prepare_private_deepseek_prompt(
    prompt: str,
    context: _PrivateRouteContext,
) -> str:
    headers = _participant_headers(context)
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


def _participant_headers(context: _PrivateRouteContext) -> tuple[str, ...] | None:
    if type(context.recipients) is not list or type(context.cc) is not list:
        return None
    try:
        sources = context.timeline.sources
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
        raise PrivateAnalysisRouteError("safety_rejected_all", "safety")
