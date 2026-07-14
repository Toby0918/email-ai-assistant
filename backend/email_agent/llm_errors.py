"""Internal error types and failure classification for LLM providers."""

from __future__ import annotations

from openai import APIConnectionError, APITimeoutError


class LlmClientError(RuntimeError):
    """Raised when the LLM client cannot produce an analysis."""

    def __init__(
        self, message: str, *, reason_code: str = "provider_request_failed"
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _deepseek_failure_reason(exc: BaseException) -> str:
    status = getattr(exc, "status_code", None)
    if status == 401:
        return "provider_auth"
    if status in {402, 403}:
        return "provider_permission_or_balance"
    if status == 429:
        return "provider_rate_limit"
    if isinstance(status, int) and 500 <= status <= 599:
        return "provider_server_error"
    if isinstance(status, int):
        return "provider_http_error"
    if isinstance(exc, APITimeoutError):
        return "provider_timeout"
    if isinstance(exc, APIConnectionError):
        return "provider_connection_error"
    return "provider_request_failed"
