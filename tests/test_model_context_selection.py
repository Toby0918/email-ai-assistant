"""Task 4B regression tests for current-first private model context."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from backend.email_agent.analyzer import analyze_current_email
from backend.email_agent.analysis_budget import AnalysisBudget
from backend.email_agent.config import load_config
from backend.email_agent.private_context_gate import (
    PrivateContextFallbackCode,
    PrivateModelContext,
    PrivateModelRequest,
    build_private_model_context,
)
from tests.test_private_knowledge_context import rule_result


def budget_with_remaining(seconds: float) -> AnalysisBudget:
    return AnalysisBudget(deadline=seconds, _clock=lambda: 0.0)


class ModelContextSelectionTests(unittest.TestCase):
    def test_current_message_is_first_and_long_history_cannot_evict_it(self) -> None:
        prompts: list[str] = []
        segments = [
            {
                "position": index,
                "from": "prior@example.test",
                "to": "sales@example.test",
                "subject": "delivery history",
                "body_text": f"please review delivery archive item {index}.",
            }
            for index in range(20)
        ]
        email = {
            "subject": "current delivery request",
            "from": "buyer@example.test",
            "to": ["sales@example.test"],
            "body_text": "please confirm currentwidget delivery.",
            "thread_segments": segments,
        }

        analyze_current_email(
            email,
            llm_generate=lambda prompt: prompts.append(prompt) or "not json",
            config=self._deepseek_config(),
        )

        self.assertEqual(len(prompts), 1)
        payload = json.loads(prompts[0])
        self.assertIn("currentwidget", payload["sources"][0]["text"])
        self.assertIn("currentwidget", json.dumps(payload, ensure_ascii=False))

    def test_later_history_timestamp_cannot_replace_explicit_current_source(self) -> None:
        prompts: list[str] = []
        email = {
            "subject": "current delivery request",
            "from": "buyer@example.test",
            "to": ["sales@synthetic.internal"],
            "sent_at": "2026-07-15T09:00:00+00:00",
            "body_text": "please confirm currentmarker delivery.",
            "thread_segments": [{
                "position": 0,
                "from": "buyer@example.test",
                "to": "sales@synthetic.internal",
                "sent_at": "2099-01-01T00:00:00+00:00",
                "subject": "historical delivery request",
                "body_text": "please confirm historymarker delivery.",
            }],
        }

        analyze_current_email(
            email,
            llm_generate=lambda prompt: prompts.append(prompt) or "not json",
            config=self._deepseek_config(),
        )

        payload = json.loads(prompts[0])
        source_text = [item["text"] for item in payload["sources"]]
        self.assertIn("currentmarker", source_text[0])
        self.assertIn("historymarker", "\n".join(source_text[1:]))

    def test_only_relevant_history_is_selected_and_keeps_oldest_first_order(self) -> None:
        prompts: list[str] = []
        email = {
            "subject": "delivery confirmation",
            "from": "buyer@example.test",
            "to": ["sales@synthetic.internal"],
            "body_text": "please confirm delivery for the current request.",
            "thread_segments": [
                {
                    "position": 0,
                    "from": "other@example.test",
                    "to": "sales@synthetic.internal",
                    "subject": "invoice note",
                    "body_text": "unrelatedinvoice payment archive.",
                },
                {
                    "position": 1,
                    "from": "buyer@example.test",
                    "to": "sales@synthetic.internal",
                    "subject": "delivery request",
                    "body_text": "relevanthistoryold delivery request.",
                },
                {
                    "position": 2,
                    "from": "sales@example.test",
                    "to": "buyer@example.test",
                    "subject": "delivery update",
                    "body_text": "relevanthistorynew delivery update.",
                },
            ],
        }

        analyze_current_email(
            email,
            llm_generate=lambda prompt: prompts.append(prompt) or "not json",
            config=self._deepseek_config(),
        )

        payload = json.loads(prompts[0])
        source_text = [item["text"] for item in payload["sources"]]
        self.assertIn("current request", source_text[0])
        combined = "\n".join(source_text)
        self.assertNotIn("unrelatedinvoice", combined)
        self.assertLess(combined.index("relevanthistoryold"), combined.index("relevanthistorynew"))

    def test_unsafe_history_downgrades_to_current_only_before_one_provider_call(self) -> None:
        prompts: list[str] = []
        email = {
            "subject": "delivery confirmation",
            "from": "buyer@example.test",
            "to": ["sales@example.test"],
            "body_text": "please confirm safe current delivery request.",
            "thread_segments": [{
                "position": 0,
                "from": "x" * 513,
                "to": "sales@example.test",
                "subject": "delivery history",
                "body_text": "please confirm historical delivery request.",
            }],
        }

        result = analyze_current_email(
            email,
            llm_generate=lambda prompt: prompts.append(prompt) or "not json",
            config=self._deepseek_config(),
        )

        self.assertEqual(len(prompts), 1)
        self.assertIn("safe current delivery request", prompts[0])
        self.assertNotIn("historical delivery request", prompts[0])
        self.assertEqual(result["analysis_engine"]["context_scope"], "current_only")
        self.assertIs(result["analysis_engine"]["context_limited"], True)

    def test_current_privacy_failure_makes_zero_calls_and_uses_fixed_code(self) -> None:
        calls: list[str] = []
        marker = "UNMAPPED-PRIVATE-ENTITY"
        email = {
            "subject": "synthetic request",
            "from": "buyer@example.test",
            "body_text": f"please review {marker}.",
        }

        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            result = analyze_current_email(
                email,
                llm_generate=lambda prompt: calls.append(prompt) or "{}",
                config=self._deepseek_config(),
            )

        self.assertEqual(calls, [])
        self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
        self.assertIn("code=privacy_preflight_rejected", captured.output[0])
        self.assertNotIn(marker, captured.output[0])

    def test_json_keys_are_not_deidentified_when_display_name_matches(self) -> None:
        result = build_private_model_context(
            PrivateModelRequest(
                json.dumps({"Alice": "Alice asks for review"}),
                ("Alice <alice@example.test>",),
            ),
            rule_result(),
            (),
            budget_with_remaining(10.0),
        )

        self.assertIsInstance(result, PrivateModelContext)
        assert isinstance(result, PrivateModelContext)
        payload = json.loads(result.text)
        self.assertEqual(set(payload), {"Alice"})
        self.assertNotIn("Alice", payload["Alice"])

    def test_escaped_newline_identity_is_scanned_after_json_decode(self) -> None:
        result = build_private_model_context(
            PrivateModelRequest('{"body":"Alice\\nSmith asks for review"}', ()),
            rule_result(),
            (),
            budget_with_remaining(10.0),
        )

        self.assertIs(result, PrivateContextFallbackCode.SAFETY)

    def test_provider_invalid_json_has_fixed_output_code(self) -> None:
        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            analyze_current_email(
                {
                    "subject": "synthetic request",
                    "from": "buyer@example.test",
                    "body_text": "please review the current request.",
                },
                llm_generate=lambda _prompt: "not json",
                config=self._deepseek_config(),
            )

        self.assertIn("code=provider_output_invalid", captured.output[0])

    @staticmethod
    def _deepseek_config():
        return replace(
            load_config(dotenv_path=None),
            llm_provider="deepseek",
            deepseek_api_key="synthetic-test-key",
            deepseek_model="deepseek-v4-flash",
            deepseek_output_mode="model_led",
            internal_email_domains=("synthetic.internal",),
        )


if __name__ == "__main__":
    unittest.main()
