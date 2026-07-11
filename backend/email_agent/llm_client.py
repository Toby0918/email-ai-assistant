"""LLM client boundary for the backend."""

from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.parse
import urllib.request

from .config import AppConfig
from .config import load_config


class LlmClientError(RuntimeError):
    """Raised when the LLM client cannot produce an analysis."""


def generate_analysis(prompt: str) -> str:
    config = load_config()
    if config.llm_provider in {"", "disabled", "none"}:
        raise LlmClientError("LLM provider is disabled.")
    if config.llm_provider == "ollama":
        return _generate_with_ollama(prompt, config)
    if config.llm_provider == "openai":
        if not config.openai_api_key:
            raise LlmClientError("OpenAI API key is not configured for backend analysis.")
        raise LlmClientError("OpenAI integration is not enabled in the first skeleton.")
    raise LlmClientError("Unsupported LLM provider configured.")


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
    return "Rule fallback"


def _generate_with_ollama(prompt: str, config: AppConfig) -> str:
    try:
        request = _ollama_request(prompt, config)
        with urllib.request.urlopen(request, timeout=config.ollama_timeout_seconds) as response:
            status = int(getattr(response, "status", 200))
            payload = response.read()
    except (OSError, TimeoutError, TypeError, ValueError, urllib.error.URLError) as exc:
        raise LlmClientError("Ollama analysis request failed.") from exc
    if status != 200:
        raise LlmClientError("Ollama analysis request failed.")
    return _parse_ollama_response(payload)


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
