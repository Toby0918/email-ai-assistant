"""LLM client boundary for the backend."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import queue
import threading
import time
import urllib.parse
import urllib.request

from openai import AsyncOpenAI

from .config import AppConfig, load_config
from .llm_errors import LlmClientError, _deepseek_failure_reason
from .model_request import ModelAnalysisRequest
from .openai_multimodal_client import generate_openai_multimodal_analysis


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODELS = frozenset({"deepseek-v4-flash", "deepseek-v4-pro"})


def generate_analysis(
    user_prompt: str | ModelAnalysisRequest,
    *,
    system_prompt: str = "",
    config: AppConfig | None = None,
    timeout_seconds: float | None = None,
) -> str:
    current = config or load_config()
    if current.llm_provider in {"", "disabled", "none"}:
        raise LlmClientError("LLM provider is disabled.")
    if current.llm_provider == "ollama":
        return _generate_with_ollama(
            _request_text(user_prompt),
            current,
            _ollama_timeout_seconds(current, timeout_seconds),
        )
    if current.llm_provider == "deepseek":
        if not current.deepseek_api_key:
            raise LlmClientError(
                "DeepSeek API key is not configured for backend analysis.",
                reason_code="missing_key",
            )
        requested_timeout = (
            current.deepseek_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        return asyncio.run(
            _generate_with_deepseek(
                system_prompt,
                _request_text(user_prompt),
                current,
                float(requested_timeout),
            )
        )
    if current.llm_provider == "openai":
        requested_timeout = current.openai_timeout_seconds if timeout_seconds is None else timeout_seconds
        return asyncio.run(
            generate_openai_multimodal_analysis(
                user_prompt,
                api_key=current.openai_api_key,
                model=current.openai_model,
                timeout_seconds=requested_timeout,
            )
        )
    raise LlmClientError("Unsupported LLM provider configured.")


def _request_text(request: str | ModelAnalysisRequest) -> str:
    if isinstance(request, ModelAnalysisRequest):
        return request.text
    if type(request) is str:
        return request
    raise LlmClientError("LLM analysis request is invalid.", reason_code="invalid_request")


def configured_analysis_engine_label(config: AppConfig | None = None) -> str:
    """Return a non-sensitive display label for the configured backend model path."""
    current = config or load_config()
    if current.llm_provider == "ollama":
        model = current.ollama_model.lower()
        if "qwen" in model:
            return "Local Qwen"
        if "gemma" in model:
            return "Local Gemma"
        return "Local AI model"
    if current.llm_provider == "openai":
        return "OpenAI"
    if current.llm_provider == "deepseek":
        if current.deepseek_model == "deepseek-v4-flash":
            return "DeepSeek V4 Flash"
        if current.deepseek_model == "deepseek-v4-pro":
            return "DeepSeek V4 Pro"
        return "DeepSeek"
    return "Rule fallback"


async def _generate_with_deepseek(
    system_prompt: str,
    user_prompt: str,
    config: AppConfig,
    timeout_seconds: float,
) -> str:
    if config.deepseek_model not in DEEPSEEK_MODELS:
        raise LlmClientError(
            "DeepSeek model is unsupported.", reason_code="unsupported_model"
        )
    effective_timeout = min(
        timeout_seconds,
        float(config.deepseek_timeout_seconds),
        10.0,
    )
    try:
        async with asyncio.timeout(effective_timeout):
            async with AsyncOpenAI(
                api_key=config.deepseek_api_key,
                base_url=DEEPSEEK_BASE_URL,
                max_retries=0,
                timeout=effective_timeout,
            ) as client:
                response = await client.chat.completions.create(
                    model=config.deepseek_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    stream=False,
                    max_tokens=2400,
                    extra_body={"thinking": {"type": "disabled"}},
                )
    except TimeoutError:
        raise LlmClientError(
            "DeepSeek analysis request timed out.", reason_code="provider_timeout"
        ) from None
    except Exception as exc:
        raise LlmClientError(
            "DeepSeek analysis request failed.",
            reason_code=_deepseek_failure_reason(exc),
        ) from None
    return _parse_deepseek_response(response)


def _parse_deepseek_response(response: object) -> str:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, (list, tuple)) or not choices:
        raise LlmClientError(
            "DeepSeek analysis response was incomplete.",
            reason_code="response_incomplete",
        ) from None
    choice = choices[0]
    if getattr(choice, "finish_reason", None) != "stop":
        raise LlmClientError(
            "DeepSeek analysis response was incomplete.",
            reason_code="response_incomplete",
        ) from None
    message = getattr(choice, "message", None)
    content = getattr(message, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise LlmClientError(
            "DeepSeek analysis response was empty.",
            reason_code="response_empty",
        ) from None
    return content.strip()


def _ollama_timeout_seconds(
    config: AppConfig, timeout_seconds: float | None
) -> float:
    requested = config.ollama_timeout_seconds if timeout_seconds is None else timeout_seconds
    try:
        routed = float(requested)
    except (TypeError, ValueError):
        raise LlmClientError("Ollama analysis timeout must be positive.") from None
    if not math.isfinite(routed) or routed <= 0:
        raise LlmClientError("Ollama analysis timeout must be positive.")
    return min(float(config.ollama_timeout_seconds), routed)


def _generate_with_ollama(
    prompt: str, config: AppConfig, timeout_seconds: float
) -> str:
    deadline = time.monotonic() + timeout_seconds
    result: queue.Queue[object] = queue.Queue()
    state: dict[str, object] = {}
    worker = threading.Thread(
        target=_ollama_exchange,
        args=(prompt, config, timeout_seconds, deadline, state, result),
        daemon=True,
    )
    worker.start()
    try:
        outcome = result.get(timeout=max(0.0, deadline - time.monotonic()))
    except queue.Empty:
        _cancel_ollama_exchange(state)
        raise LlmClientError("Ollama analysis request failed.") from None
    if time.monotonic() > deadline or isinstance(outcome, BaseException):
        _cancel_ollama_exchange(state)
        raise LlmClientError("Ollama analysis request failed.") from None
    status, payload = outcome
    if status != 200:
        raise LlmClientError("Ollama analysis request failed.")
    return _parse_ollama_response(payload)


def _ollama_exchange(
    prompt: str,
    config: AppConfig,
    timeout_seconds: float,
    deadline: float,
    state: dict[str, object],
    result: queue.Queue[object],
) -> None:
    try:
        request = _ollama_request(prompt, config)
        if time.monotonic() >= deadline:
            raise TimeoutError
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            state["response"] = response
            status = int(getattr(response, "status", 200))
            payload = response.read()
        if time.monotonic() > deadline:
            raise TimeoutError
        result.put((status, payload))
    except BaseException as exc:
        result.put(exc)


def _cancel_ollama_exchange(state: dict[str, object]) -> None:
    response = state.get("response")
    close = getattr(response, "close", None)
    if callable(close):
        threading.Thread(target=_ignore_close_error, args=(close,), daemon=True).start()


def _ignore_close_error(close: object) -> None:
    try:
        close()
    except Exception:
        return


def _ollama_request(prompt: str, config: AppConfig) -> urllib.request.Request:
    payload = {
        "model": config.ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "think": False,
        "options": {"temperature": 0, "num_predict": 1200},
    }
    endpoint = _ollama_endpoint(config.ollama_base_url)
    return urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def _ollama_endpoint(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or not _is_loopback_host(parsed.hostname)
    ):
        raise ValueError("Invalid Ollama base URL.")
    return f"{base_url}/api/generate"


def _is_loopback_host(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _parse_ollama_response(payload: bytes) -> str:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LlmClientError("Ollama analysis response was not valid JSON.") from exc
    text = str(data.get("response") or "").strip() if isinstance(data, dict) else ""
    if not text:
        raise LlmClientError("Ollama analysis response was empty.")
    return text
