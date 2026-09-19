"""Run production client serialization through the new SDK with no network."""
import asyncio
import json
import unittest

import httpx2
from openai import AsyncOpenAI

from backend.email_agent.openai_multimodal_client import _request_response


class SdkCompatibilityTests(unittest.TestCase):
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
