"""Tests for backend-only LLM provider integration."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from backend.email_agent.config import AppConfig
from backend.email_agent.llm_client import (
    LlmClientError,
    configured_analysis_engine_label,
    generate_analysis,
)


class FakeHttpResponse:
    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self._payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


class LlmClientTests(unittest.TestCase):
    def test_configured_engine_label_identifies_gemma(self) -> None:
        config = AppConfig(
            openai_api_key=None,
            sqlite_path="outputs/test.sqlite3",
            log_level="INFO",
            llm_provider="ollama",
            ollama_base_url="http://127.0.0.1:11434",
            ollama_model="gemma4:latest",
            ollama_timeout_seconds=30,
            attachment_temp_dir="outputs/attachment_temp",
            attachment_retention_hours=24,
            attachment_max_files=5,
            attachment_max_file_bytes=10 * 1024 * 1024,
            attachment_max_total_bytes=25 * 1024 * 1024,
            internal_email_domains=("cndlf.com",),
        )

        self.assertEqual(configured_analysis_engine_label(config), "Local Gemma")

    def test_configured_engine_label_identifies_rule_fallback(self) -> None:
        config = AppConfig(
            openai_api_key=None,
            sqlite_path="outputs/test.sqlite3",
            log_level="INFO",
            llm_provider="disabled",
            ollama_base_url="http://127.0.0.1:11434",
            ollama_model="qwen3.6:latest",
            ollama_timeout_seconds=30,
            attachment_temp_dir="outputs/attachment_temp",
            attachment_retention_hours=24,
            attachment_max_files=5,
            attachment_max_file_bytes=10 * 1024 * 1024,
            attachment_max_total_bytes=25 * 1024 * 1024,
            internal_email_domains=("cndlf.com",),
        )

        self.assertEqual(configured_analysis_engine_label(config), "Rule fallback")

    def test_disabled_provider_raises_without_calling_network(self) -> None:
        with patch.dict(os.environ, {"EMAIL_AGENT_LLM_PROVIDER": "disabled"}, clear=True):
            with patch("urllib.request.urlopen") as urlopen:
                with self.assertRaisesRegex(LlmClientError, "disabled"):
                    generate_analysis("prompt")

        urlopen.assert_not_called()

    def test_ollama_provider_posts_json_mode_generate_request(self) -> None:
        response_body = json.dumps({"response": "{\"summary\":\"客户询问。\"}"}).encode("utf-8")
        env = {
            "EMAIL_AGENT_LLM_PROVIDER": "ollama",
            "EMAIL_AGENT_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            "EMAIL_AGENT_OLLAMA_MODEL": "qwen3.6:latest",
            "EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS": "9",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("urllib.request.urlopen", return_value=FakeHttpResponse(200, response_body)) as urlopen:
                result = generate_analysis("analyze this email")

        request = urlopen.call_args.args[0]
        timeout = urlopen.call_args.kwargs["timeout"]
        payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(result, "{\"summary\":\"客户询问。\"}")
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertEqual(timeout, 9)
        self.assertEqual(payload["model"], "qwen3.6:latest")
        self.assertEqual(payload["prompt"], "analyze this email")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"], "json")
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertEqual(payload["options"]["num_predict"], 1200)

    def test_ollama_errors_are_sanitized(self) -> None:
        env = {"EMAIL_AGENT_LLM_PROVIDER": "ollama"}
        prompt = "SECRET_BODY should not appear in error"

        with patch.dict(os.environ, env, clear=True):
            with patch("urllib.request.urlopen", side_effect=TimeoutError(prompt)):
                with self.assertRaises(LlmClientError) as caught:
                    generate_analysis(prompt)

        self.assertNotIn("SECRET_BODY", str(caught.exception))
        self.assertIn("Ollama analysis request failed", str(caught.exception))

    def test_invalid_ollama_base_url_becomes_sanitized_client_error(self) -> None:
        env = {
            "EMAIL_AGENT_LLM_PROVIDER": "ollama",
            "EMAIL_AGENT_OLLAMA_BASE_URL": "http://[PRIVATE_INVALID_HOST",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("urllib.request.urlopen") as urlopen:
                with self.assertRaises(LlmClientError) as caught:
                    generate_analysis("synthetic prompt")

        urlopen.assert_not_called()
        self.assertEqual(str(caught.exception), "Ollama analysis request failed.")
        self.assertNotIn("PRIVATE_INVALID_HOST", str(caught.exception))

    def test_ollama_empty_response_is_an_error(self) -> None:
        env = {"EMAIL_AGENT_LLM_PROVIDER": "ollama"}
        response_body = json.dumps({"response": ""}).encode("utf-8")

        with patch.dict(os.environ, env, clear=True):
            with patch("urllib.request.urlopen", return_value=FakeHttpResponse(200, response_body)):
                with self.assertRaisesRegex(LlmClientError, "empty"):
                    generate_analysis("prompt")


if __name__ == "__main__":
    unittest.main()
