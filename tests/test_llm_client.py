"""Tests for backend-only LLM provider integration."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from openai import APIConnectionError, APITimeoutError

from backend.email_agent.config import AppConfig, load_config
from backend.email_agent.llm_client import (
    LlmClientError,
    _deepseek_failure_reason,
    configured_analysis_engine_label,
    generate_analysis,
)
from backend.email_agent.model_request import ModelAnalysisRequest
from backend.email_agent.multimodal_media import PreparedMediaAsset


DEEPSEEK_BASE_URL = "https://api.deepseek.com"


async def _never_finishes(*args: object, **kwargs: object) -> object:
    await asyncio.Future()
    return object()


def _deepseek_config(**changes: object) -> AppConfig:
    config = replace(
        load_config(dotenv_path=None),
        llm_provider="deepseek",
        deepseek_api_key="synthetic-deepseek-key",
        deepseek_model="deepseek-v4-flash",
        deepseek_timeout_seconds=10,
    )
    return replace(config, **changes)


def _ollama_config(**changes: object) -> AppConfig:
    config = replace(
        load_config(dotenv_path=None),
        llm_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="qwen3.6:latest",
        ollama_timeout_seconds=30,
    )
    return replace(config, **changes)


def _deepseek_response(
    *,
    content: object = '{"summary":"synthetic"}',
    finish_reason: object = "stop",
    extra_choices: tuple[object, ...] = (),
) -> object:
    first_choice = SimpleNamespace(
        finish_reason=finish_reason,
        message=SimpleNamespace(content=content),
    )
    return SimpleNamespace(choices=[first_choice, *extra_choices])


def _async_client(response: object) -> tuple[MagicMock, AsyncMock]:
    create = AsyncMock(return_value=response)
    active_client = MagicMock()
    active_client.chat.completions.create = create
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=active_client)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    return context_manager, create


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


class _TrickleHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        payload = json.dumps({"response": "{}"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            for value in payload:
                self.wfile.write(bytes((value,)))
                self.wfile.flush()
                time.sleep(0.04)
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, format: str, *args: object) -> None:
        return


class LlmClientTests(unittest.TestCase):
    def test_configured_engine_label_identifies_deepseek_flash_and_pro(self) -> None:
        expected_labels = {
            "deepseek-v4-flash": "DeepSeek V4 Flash",
            "deepseek-v4-pro": "DeepSeek V4 Pro",
        }

        for model, expected in expected_labels.items():
            with self.subTest(model=model):
                self.assertEqual(
                    configured_analysis_engine_label(_deepseek_config(deepseek_model=model)),
                    expected,
                )

    def test_deepseek_sends_exact_fixed_json_request(self) -> None:
        config = _deepseek_config(deepseek_timeout_seconds=11)
        client, create = _async_client(_deepseek_response())

        with patch(
            "backend.email_agent.llm_client.AsyncOpenAI",
            return_value=client,
        ) as client_constructor:
            result = generate_analysis(
                "UNTRUSTED_SYNTHETIC_JSON",
                system_prompt="RETURN JSON",
                config=config,
                timeout_seconds=7,
            )

        self.assertEqual(result, '{"summary":"synthetic"}')
        client_constructor.assert_called_once_with(
            api_key="synthetic-deepseek-key",
            base_url=DEEPSEEK_BASE_URL,
            max_retries=0,
            timeout=7,
        )
        create.assert_awaited_once_with(
            model="deepseek-v4-flash",
            messages=[
                {"role": "system", "content": "RETURN JSON"},
                {"role": "user", "content": "UNTRUSTED_SYNTHETIC_JSON"},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            stream=False,
            max_tokens=2400,
            extra_body={"thinking": {"type": "disabled"}},
        )

    def test_deepseek_model_request_remains_exactly_text_only(self) -> None:
        media = PreparedMediaAsset(
            source_id="attachment:0",
            provider_filename="image_0.png",
            mime_type="image/png",
            kind="image",
            detail="high",
            buffer=bytearray(b"BINARY_CANARY"),
        )
        client, create = _async_client(_deepseek_response())

        with patch(
            "backend.email_agent.llm_client.AsyncOpenAI",
            return_value=client,
        ):
            generate_analysis(
                ModelAnalysisRequest("DEIDENTIFIED_TEXT", (media,)),
                system_prompt="RETURN JSON",
                config=_deepseek_config(),
                timeout_seconds=7,
            )

        payload = create.call_args.kwargs
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "RETURN JSON"},
                {"role": "user", "content": "DEIDENTIFIED_TEXT"},
            ],
        )
        self.assertNotIn("BINARY_CANARY", repr(payload))
        self.assertNotIn("input_image", repr(payload))
        self.assertNotIn("input_file", repr(payload))

    def test_deepseek_timeout_uses_minimum_of_caller_config_and_hard_cap(self) -> None:
        cases = (
            (3.0, 19, 3.0),
            (19.0, 4, 4.0),
            (40.0, 30, 10.0),
        )

        for caller_timeout, config_timeout, expected in cases:
            with self.subTest(
                caller_timeout=caller_timeout,
                config_timeout=config_timeout,
            ):
                client, _create = _async_client(_deepseek_response())
                config = _deepseek_config(deepseek_timeout_seconds=config_timeout)
                with patch(
                    "backend.email_agent.llm_client.AsyncOpenAI",
                    return_value=client,
                ) as client_constructor:
                    generate_analysis(
                        "{}",
                        system_prompt="json",
                        config=config,
                        timeout_seconds=caller_timeout,
                    )

                self.assertEqual(client_constructor.call_args.kwargs["timeout"], expected)

    def test_deepseek_zero_caller_timeout_is_not_replaced_by_config(self) -> None:
        client, _create = _async_client(_deepseek_response())

        with patch(
            "backend.email_agent.llm_client.AsyncOpenAI",
            return_value=client,
        ) as client_constructor:
            result = generate_analysis(
                "{}",
                system_prompt="json",
                config=_deepseek_config(deepseek_timeout_seconds=20),
                timeout_seconds=0,
            )

        self.assertEqual(result, '{"summary":"synthetic"}')
        self.assertEqual(client_constructor.call_args.kwargs["timeout"], 0)

    def test_deepseek_outer_timeout_cancels_never_finishing_sdk_call(self) -> None:
        client, create = _async_client(_deepseek_response())
        create.side_effect = _never_finishes
        config = _deepseek_config(deepseek_timeout_seconds=20)

        started = time.monotonic()
        with patch(
            "backend.email_agent.llm_client.AsyncOpenAI",
            return_value=client,
        ):
            with self.assertRaises(LlmClientError) as caught:
                generate_analysis(
                    "{}",
                    system_prompt="json",
                    config=config,
                    timeout_seconds=0.05,
                )
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.0)
        self.assertEqual(str(caught.exception), "DeepSeek analysis request timed out.")
        self.assertEqual(caught.exception.reason_code, "provider_timeout")
        self.assertIsNone(caught.exception.__cause__)

    def test_deepseek_rejects_unapproved_model_before_client_construction(self) -> None:
        config = _deepseek_config(deepseek_model="unapproved-model")

        with patch(
            "backend.email_agent.llm_client.AsyncOpenAI",
        ) as client_constructor:
            with self.assertRaises(LlmClientError) as caught:
                generate_analysis(
                    "{}",
                    system_prompt="json",
                    config=config,
                    timeout_seconds=5,
                )

        client_constructor.assert_not_called()
        self.assertEqual(str(caught.exception), "DeepSeek model is unsupported.")
        self.assertEqual(caught.exception.reason_code, "unsupported_model")
        self.assertIsNone(caught.exception.__cause__)

    def test_deepseek_requires_dedicated_key_before_client_construction(self) -> None:
        config = _deepseek_config(
            deepseek_api_key=None,
            openai_api_key="synthetic-openai-key",
        )

        with patch(
            "backend.email_agent.llm_client.AsyncOpenAI",
        ) as client_constructor:
            with self.assertRaises(LlmClientError) as caught:
                generate_analysis(
                    "{}",
                    system_prompt="json",
                    config=config,
                    timeout_seconds=5,
                )

        client_constructor.assert_not_called()
        self.assertEqual(
            str(caught.exception),
            "DeepSeek API key is not configured for backend analysis.",
        )
        self.assertEqual(caught.exception.reason_code, "missing_key")
        self.assertIsNone(caught.exception.__cause__)

    def test_deepseek_accepts_only_stop_from_first_choice(self) -> None:
        accepted_second_choice = SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content='{"ignored":true}'),
        )
        rejected_reasons = ("length", "content_filter", "insufficient_system_resource", None)

        for finish_reason in rejected_reasons:
            with self.subTest(finish_reason=finish_reason):
                response = _deepseek_response(
                    finish_reason=finish_reason,
                    extra_choices=(accepted_second_choice,),
                )
                client, _create = _async_client(response)
                with patch(
                    "backend.email_agent.llm_client.AsyncOpenAI",
                    return_value=client,
                ):
                    with self.assertRaises(LlmClientError) as caught:
                        generate_analysis(
                            "{}",
                            system_prompt="json",
                            config=_deepseek_config(),
                            timeout_seconds=5,
                        )

                self.assertEqual(
                    str(caught.exception),
                    "DeepSeek analysis response was incomplete.",
                )
                self.assertEqual(caught.exception.reason_code, "response_incomplete")
                self.assertNotIn(str(finish_reason), str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)

    def test_deepseek_rejects_empty_or_non_string_content(self) -> None:
        for content in ("", "   ", None, {"summary": "not-text"}):
            with self.subTest(content=content):
                client, _create = _async_client(_deepseek_response(content=content))
                with patch(
                    "backend.email_agent.llm_client.AsyncOpenAI",
                    return_value=client,
                ):
                    with self.assertRaises(LlmClientError) as caught:
                        generate_analysis(
                            "{}",
                            system_prompt="json",
                            config=_deepseek_config(),
                            timeout_seconds=5,
                        )

                self.assertEqual(
                    str(caught.exception),
                    "DeepSeek analysis response was empty.",
                )
                self.assertEqual(caught.exception.reason_code, "response_empty")
                self.assertIsNone(caught.exception.__cause__)

    def test_deepseek_rejects_malformed_response_without_exposing_it(self) -> None:
        response = SimpleNamespace(
            choices=[],
            private_detail="PRIVATE_RAW_PROVIDER_RESPONSE",
        )
        client, _create = _async_client(response)

        with patch(
            "backend.email_agent.llm_client.AsyncOpenAI",
            return_value=client,
        ):
            with self.assertRaises(LlmClientError) as caught:
                generate_analysis(
                    "{}",
                    system_prompt="json",
                    config=_deepseek_config(),
                    timeout_seconds=5,
                )

        self.assertEqual(
            str(caught.exception),
            "DeepSeek analysis response was incomplete.",
        )
        self.assertEqual(caught.exception.reason_code, "response_incomplete")
        self.assertNotIn("PRIVATE_RAW_PROVIDER_RESPONSE", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_deepseek_sdk_errors_are_fixed_and_suppress_cause(self) -> None:
        client, create = _async_client(_deepseek_response())
        create.side_effect = RuntimeError(
            "PRIVATE_EXCEPTION SECRET_PROMPT SECRET_KEY PRIVATE_URL finish_reason=length"
        )

        with patch(
            "backend.email_agent.llm_client.AsyncOpenAI",
            return_value=client,
        ):
            with self.assertRaises(LlmClientError) as caught:
                generate_analysis(
                    "SECRET_PROMPT",
                    system_prompt="json",
                    config=_deepseek_config(deepseek_api_key="SECRET_KEY"),
                    timeout_seconds=5,
                )

        self.assertEqual(str(caught.exception), "DeepSeek analysis request failed.")
        self.assertEqual(caught.exception.reason_code, "provider_request_failed")
        self.assertIsNone(caught.exception.__cause__)
        for forbidden in (
            "PRIVATE_EXCEPTION",
            "SECRET_PROMPT",
            "SECRET_KEY",
            "PRIVATE_URL",
            "length",
        ):
            self.assertNotIn(forbidden, str(caught.exception))

    def test_deepseek_status_errors_map_without_using_private_text(self) -> None:
        cases = {
            401: "provider_auth",
            402: "provider_permission_or_balance",
            403: "provider_permission_or_balance",
            429: "provider_rate_limit",
            500: "provider_server_error",
            503: "provider_server_error",
            418: "provider_http_error",
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                error = RuntimeError("PRIVATE_PROVIDER_BODY")
                error.status_code = status
                self.assertEqual(_deepseek_failure_reason(error), expected)

    def test_deepseek_sdk_timeout_maps_before_connection_error(self) -> None:
        request = httpx.Request("POST", "https://synthetic-provider.invalid/v1")
        cases = (
            (APITimeoutError(request), "provider_timeout"),
            (
                APIConnectionError(request=request),
                "provider_connection_error",
            ),
        )

        for error, expected in cases:
            with self.subTest(error_type=type(error).__name__):
                self.assertEqual(_deepseek_failure_reason(error), expected)

    def test_deepseek_failure_never_calls_ollama(self) -> None:
        config = _deepseek_config()

        with patch(
            "backend.email_agent.llm_client._generate_with_deepseek",
            side_effect=LlmClientError("DeepSeek analysis request failed."),
        ) as deepseek:
            with patch("backend.email_agent.llm_client._generate_with_ollama") as ollama:
                with self.assertRaises(LlmClientError):
                    generate_analysis(
                        "{}",
                        system_prompt="json",
                        config=config,
                        timeout_seconds=5,
                    )

        deepseek.assert_called_once()
        ollama.assert_not_called()

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

    def test_openai_provider_dispatches_provider_neutral_request(self) -> None:
        config = _deepseek_config(
            llm_provider="openai",
            openai_api_key="synthetic-openai-key",
        )

        with patch(
            "backend.email_agent.llm_client.generate_openai_multimodal_analysis",
            new=AsyncMock(return_value='{"summary":"synthetic"}'),
        ) as generate_openai:
            result = generate_analysis(
                ModelAnalysisRequest("DEIDENTIFIED_TEXT", ()),
                config=config,
                timeout_seconds=9,
            )

        self.assertEqual(result, '{"summary":"synthetic"}')
        generate_openai.assert_awaited_once()
        self.assertEqual(generate_openai.call_args.args[0].text, "DEIDENTIFIED_TEXT")
        self.assertEqual(generate_openai.call_args.kwargs["api_key"], "synthetic-openai-key")
        self.assertEqual(generate_openai.call_args.kwargs["model"], "gpt-5.6-sol")
        self.assertEqual(generate_openai.call_args.kwargs["timeout_seconds"], 9)

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

    def test_ollama_uses_minimum_of_routed_and_configured_timeout(self) -> None:
        response_body = json.dumps({"response": "{}"}).encode("utf-8")
        cases = ((30, 6, 6), (4, 6, 4))
        for configured, routed, expected in cases:
            with self.subTest(configured=configured, routed=routed), patch(
                "urllib.request.urlopen",
                return_value=FakeHttpResponse(200, response_body),
            ) as urlopen:
                result = generate_analysis(
                    "synthetic prompt",
                    config=_ollama_config(ollama_timeout_seconds=configured),
                    timeout_seconds=routed,
                )

            self.assertEqual(result, "{}")
            self.assertEqual(urlopen.call_args.kwargs["timeout"], expected)

    def test_ollama_without_routed_timeout_keeps_configured_timeout(self) -> None:
        response_body = json.dumps({"response": "{}"}).encode("utf-8")
        with patch(
            "urllib.request.urlopen",
            return_value=FakeHttpResponse(200, response_body),
        ) as urlopen:
            result = generate_analysis(
                "synthetic prompt",
                config=_ollama_config(ollama_timeout_seconds=9),
            )

        self.assertEqual(result, "{}")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 9)

    def test_ollama_timeout_is_absolute_across_trickled_response_body(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _TrickleHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started = time.monotonic()
        try:
            with self.assertRaises(LlmClientError) as caught:
                generate_analysis(
                    "synthetic prompt",
                    config=_ollama_config(
                        ollama_base_url=f"http://127.0.0.1:{server.server_port}"
                    ),
                    timeout_seconds=0.1,
                )
        finally:
            elapsed = time.monotonic() - started
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

        self.assertLess(elapsed, 0.35)
        self.assertEqual(str(caught.exception), "Ollama analysis request failed.")

    def test_ollama_nonpositive_routed_timeout_fails_before_network(self) -> None:
        for timeout in (0, -1):
            with self.subTest(timeout=timeout), patch("urllib.request.urlopen") as urlopen:
                with self.assertRaises(LlmClientError) as caught:
                    generate_analysis(
                        "synthetic prompt",
                        config=_ollama_config(),
                        timeout_seconds=timeout,
                    )

            urlopen.assert_not_called()
            self.assertEqual(
                str(caught.exception), "Ollama analysis timeout must be positive."
            )

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

    def test_ollama_rejects_remote_and_userinfo_hosts_before_network(self) -> None:
        rejected_urls = (
            "http://192.0.2.10:11434",
            "https://PRIVATE_REMOTE_HOST.example:11434",
            "http://[2001:db8::10]:11434",
            "http://user@127.0.0.1:11434",
        )
        for base_url in rejected_urls:
            with self.subTest(base_url=base_url):
                env = {
                    "EMAIL_AGENT_LLM_PROVIDER": "ollama",
                    "EMAIL_AGENT_OLLAMA_BASE_URL": base_url,
                }
                with patch.dict(os.environ, env, clear=True):
                    with patch(
                        "urllib.request.urlopen",
                        side_effect=OSError("PRIVATE_NETWORK_DETAIL"),
                    ) as urlopen:
                        with self.assertRaises(LlmClientError) as caught:
                            generate_analysis("synthetic prompt")

                urlopen.assert_not_called()
                self.assertEqual(str(caught.exception), "Ollama analysis request failed.")
                self.assertNotIn("PRIVATE_REMOTE_HOST", str(caught.exception))

    def test_ollama_accepts_localhost_and_literal_loopback_addresses(self) -> None:
        response_body = json.dumps({"response": "{}"}).encode("utf-8")
        accepted_urls = (
            "http://localhost:11434",
            "http://127.0.0.2:11434",
            "http://[::1]:11434",
        )
        for base_url in accepted_urls:
            with self.subTest(base_url=base_url):
                env = {
                    "EMAIL_AGENT_LLM_PROVIDER": "ollama",
                    "EMAIL_AGENT_OLLAMA_BASE_URL": base_url,
                }
                with patch.dict(os.environ, env, clear=True):
                    with patch(
                        "urllib.request.urlopen",
                        return_value=FakeHttpResponse(200, response_body),
                    ) as urlopen:
                        self.assertEqual(generate_analysis("synthetic prompt"), "{}")

                self.assertEqual(
                    urlopen.call_args.args[0].full_url,
                    f"{base_url}/api/generate",
                )

    def test_ollama_empty_response_is_an_error(self) -> None:
        env = {"EMAIL_AGENT_LLM_PROVIDER": "ollama"}
        response_body = json.dumps({"response": ""}).encode("utf-8")

        with patch.dict(os.environ, env, clear=True):
            with patch("urllib.request.urlopen", return_value=FakeHttpResponse(200, response_body)):
                with self.assertRaisesRegex(LlmClientError, "empty"):
                    generate_analysis("prompt")


if __name__ == "__main__":
    unittest.main()
