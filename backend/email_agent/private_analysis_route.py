"""Content-free route adapter around the private DeepSeek context gate."""

from __future__ import annotations

from typing import Any, Protocol

from .private_context_gate import (
    PrivateContextFallbackCode,
    PrivateModelContext,
    PrivateModelRequest,
    build_private_model_context,
    provider_output_is_private_safe,
)


class _PrivateRouteContext(Protocol):
    sender: str
    recipients: list[str]
    cc: list[str]
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
    private = build_private_model_context(
        PrivateModelRequest(
            prompt,
            (context.sender, *context.recipients, *context.cc),
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


def validate_private_provider_output(raw: object) -> None:
    if not provider_output_is_private_safe(raw):
        raise PrivateAnalysisRouteError("safety_rejected_all", "safety")
