"""LLM client boundary for the backend."""

from __future__ import annotations

from .config import load_config


class LlmClientError(RuntimeError):
    """Raised when the LLM client cannot produce an analysis."""


def generate_analysis(prompt: str) -> str:
    # Live LLM calls remain disabled until the integration is explicitly confirmed.
    config = load_config()
    if not config.openai_api_key:
        raise LlmClientError("OpenAI API key is not configured for backend analysis.")

    raise LlmClientError("OpenAI integration is not enabled in the first skeleton.")
