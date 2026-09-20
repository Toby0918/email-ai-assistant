"""Run production client serialization through the new SDK with no network."""
import asyncio
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx2
from openai import AsyncOpenAI

from backend.email_agent.openai_multimodal_client import _request_response
from backend.email_agent.config import build_standalone_verification_config
from backend.email_agent.llm_client import generate_analysis, configured_analysis_engine_label


class SdkCompatibilityTests(unittest.TestCase):
    def test_deepseek_default_uses_current_official_model_and_bounded_json_request(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx2.Response(200, json={
                "id": "synthetic", "object": "chat.completion", "created": 0,
                "model": "deepseek-flash",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant", "content": '{"summary":"synthetic"}',
                }}],
            })

        def factory(**kwargs):
            self.assertEqual(kwargs["max_retries"], 0)
            self.assertLessEqual(kwargs["timeout"], 10)
            return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))

        config = replace(build_standalone_verification_config(
            sqlite_path=Path.cwd() / "unused.sqlite3", attachment_temp_dir=Path.cwd() / "unused-temp",
        ), llm_provider="deepseek", deepseek_api_key="synthetic-not-a-live-key")
        with patch("backend.email_agent.llm_client.AsyncOpenAI", side_effect=factory):
            result = generate_analysis("Synthetic quantity: 1200 pcs.", system_prompt="Return JSON.", config=config)
        self.assertEqual(json.loads(result), {"summary": "synthetic"})
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), "https://api.deepseek.com/chat/completions")
        body = json.loads(requests[0].content)
        self.assertEqual(body["model"], "deepseek-flash")
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["max_tokens"], 2400)
        self.assertIs(body["stream"], False)
        self.assertNotIn("tools", body)
        self.assertEqual(configured_analysis_engine_label(config), "DeepSeek Flash")

    def test_latest_sdk_preserves_official_endpoint_and_no_store_no_tools(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx2.Response(200, json={
                "id": "resp_synthetic", "object": "response", "created_at": 0,
                "status": "completed", "model": "gpt-5.6-sol", "output": [],
            })
        def factory(**kwargs):
            self.assertEqual(kwargs["max_retries"], 0)
            return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))
        result = asyncio.run(_request_response(
            [{"type": "input_text", "text": "Synthetic material specification."}],
            "synthetic-not-a-live-key", 5, factory,
        ))
        self.assertEqual(result.id, "resp_synthetic")
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), "https://api.openai.com/v1/responses")
        body = json.loads(requests[0].content)
        self.assertIs(body["store"], False)
        self.assertEqual(body["tools"], [])
        self.assertIs(body["stream"], False)
        self.assertEqual(body["max_output_tokens"], 2400)
