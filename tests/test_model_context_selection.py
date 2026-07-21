"""Task 4B regression tests for current-first private model context."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from backend.email_agent.analyzer import analyze_current_email
from backend.email_agent.analysis_budget import AnalysisBudget
from backend.email_agent.config import load_config
from backend.email_agent.model_context_selection import select_model_context
from backend.email_agent.private_context_gate import (
    PrivateContextFallbackCode,
    PrivateModelContext,
    PrivateModelRequest,
    build_private_model_context,
)
from backend.email_agent.thread_timeline import TimelineBuild
from tests.test_private_knowledge_context import rule_result


def budget_with_remaining(seconds: float) -> AnalysisBudget:
    return AnalysisBudget(deadline=seconds, _clock=lambda: 0.0)


class ModelContextSelectionTests(unittest.TestCase):
    def test_current_dedup_requires_exact_recipient_and_timestamp(self) -> None:
        current = "Please confirm repeatedmarker delivery."
        base_history = {
            "position": 1,
            "from": "buyer@example.test",
            "to": "sales@synthetic.internal",
            "sent_at": "2026-07-15T09:00:00+00:00",
            "subject": "Current delivery request",
            "body_text": current,
        }
        variations = {
            "missing_recipient": {"to": None},
            "missing_timestamp": {"sent_at": None},
            "different_recipient": {"to": "ops@synthetic.internal"},
            "different_timestamp": {"sent_at": "2026-07-15T10:00:00+00:00"},
        }

        for label, changes in variations.items():
            captured = []
            history = {**base_history, **changes}

            def capture(context, *_args, **_kwargs):
                captured.append(context.timeline.sources)
                return context.fallback

            with self.subTest(label=label), patch(
                "backend.email_agent.analyzer.route_analysis", side_effect=capture
            ):
                analyze_current_email(
                    {
                        "subject": "Current delivery request",
                        "from": "buyer@example.test",
                        "to": ["sales@synthetic.internal"],
                        "sent_at": "2026-07-15T09:00:00+00:00",
                        "body_text": current,
                        "thread_segments": [history],
                    },
                    config=self._deepseek_config(),
                )

            self.assertEqual(
                sum(
                    "repeatedmarker" in source.body
                    for source in captured[0]
                ),
                2,
            )

    def test_deterministic_and_model_context_append_exact_current_once(self) -> None:
        current = "Please confirm currentmarker delivery for PO 123456."
        older = {
            "position": 0,
            "from": "older@example.test",
            "to": "sales@synthetic.internal",
            "sent_at": "2026-07-14T09:00:00+00:00",
            "subject": "Earlier delivery request",
            "body_text": "Please review the earlier delivery note.",
        }
        repeated_current = {
            "position": 1,
            "from": "buyer@example.test",
            "to": "sales@synthetic.internal",
            "sent_at": "2026-07-15T09:00:00+00:00",
            "subject": "Current delivery request",
            "body_text": current,
        }
        captured = []

        def capture(context, *_args, **_kwargs):
            captured.append(context.timeline.sources)
            return context.fallback

        with patch("backend.email_agent.analyzer.route_analysis", side_effect=capture):
            for thread_segments in ([older], [older, repeated_current]):
                analyze_current_email(
                    {
                        "subject": "Current delivery request",
                        "from": "buyer@example.test",
                        "to": ["sales@synthetic.internal"],
                        "sent_at": "2026-07-15T09:00:00+00:00",
                        "body_text": current,
                        "thread_segments": thread_segments,
                    },
                    config=self._deepseek_config(),
                )

        self.assertEqual(len(captured), 2)
        for sources in captured:
            containing_current = [
                source for source in sources if "currentmarker" in source.body
            ]
            self.assertEqual(len(containing_current), 1)

    def test_terse_current_reply_retains_two_adjacent_verified_messages(self) -> None:
        prompts: list[str] = []
        email = {
            "subject": "Re: synthetic discussion",
            "from": "newbuyer@example.test",
            "to": ["sales@synthetic.internal"],
            "body_text": "Please proceed.",
            "thread_segments": [
                {
                    "position": index,
                    "from": f"participant{index}@example.test",
                    "to": "ops@synthetic.internal",
                    "subject": f"Synthetic note {index}",
                    "body_text": body,
                }
                for index, body in enumerate(
                    (
                        "archivemarker0 old unrelated note.",
                        "archivemarker1 old unrelated note.",
                        "decisionmarker1 the reviewed quantity was accepted.",
                        "decisionmarker2 the packaging revision was accepted.",
                    )
                )
            ],
        }

        analyze_current_email(
            email,
            llm_generate=lambda prompt: prompts.append(prompt) or "not json",
            config=self._deepseek_config(),
        )

        payload = json.loads(prompts[0])
        combined = "\n".join(item["text"] for item in payload["sources"])
        self.assertIn("decisionmarker1", combined)
        self.assertIn("decisionmarker2", combined)
        self.assertNotIn("archivemarker0", combined)
        self.assertNotIn("archivemarker1", combined)

    def test_current_internal_outcome_resolves_deterministic_history_request(self) -> None:
        result = analyze_current_email(
            {
                "subject": "Re: Synthetic quotation",
                "from": "Sales Team <sales@synthetic.internal>",
                "to": ["buyer@example.test"],
                "body_text": "RFQ-2 quotation completed.",
                "thread_segments": [{
                    "position": 0,
                    "from": "Buyer <buyer@example.test>",
                    "to": "sales@synthetic.internal",
                    "subject": "Synthetic quotation",
                    "body_text": "Please provide quotation RFQ-2.",
                }],
            },
            config=replace(self._deepseek_config(), llm_provider="disabled"),
        )

        self.assertEqual(
            result["conversation_timeline"]["current_status"],
            "resolved",
        )

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

    def test_deterministic_timeline_forces_trusted_current_after_future_history(self) -> None:
        captured = []

        def capture(context, *_args, **_kwargs):
            captured.append(context.timeline)
            return context.fallback

        with patch("backend.email_agent.analyzer.route_analysis", side_effect=capture):
            analyze_current_email(
                {
                    "subject": "Current note",
                    "from": "buyer@example.test",
                    "to": ["sales@synthetic.internal"],
                    "sent_at": "2026-07-15T09:00:00+00:00",
                    "body_text": "current-last-marker",
                    "thread_segments": [{
                        "position": 0,
                        "from": "buyer@example.test",
                        "to": "sales@synthetic.internal",
                        "sent_at": "2099-01-01T00:00:00+00:00",
                        "subject": "History note",
                        "body_text": "future-history-marker",
                        "trusted_current": True,
                    }],
                },
                config=self._deepseek_config(),
            )

        self.assertEqual(
            [source.body for source in captured[0].sources],
            ["future-history-marker", "current-last-marker"],
        )
        self.assertEqual(
            captured[0].current_source_id,
            captured[0].sources[-1].source_id,
        )

    def test_future_history_timestamp_cannot_evict_verified_adjacent_messages(self) -> None:
        captured = []
        history = [
            {
                "position": 0,
                "from": "buyer@example.test",
                "to": "sales@synthetic.internal",
                "sent_at": "2099-01-01T00:00:00+00:00",
                "subject": "Synthetic note",
                "body_text": "stale-future-marker",
            },
            {
                "position": 1,
                "from": "sales@synthetic.internal",
                "to": "buyer@example.test",
                "sent_at": "2026-07-14T09:00:00+00:00",
                "subject": "Synthetic note",
                "body_text": "genuine-adjacent-marker-1",
            },
            {
                "position": 2,
                "from": "buyer@example.test",
                "to": "sales@synthetic.internal",
                "sent_at": "2026-07-15T09:00:00+00:00",
                "subject": "Synthetic note",
                "body_text": "genuine-adjacent-marker-2",
            },
        ]

        def capture(context, *_args, **_kwargs):
            captured.append(context.model_context)
            return context.fallback

        with patch("backend.email_agent.analyzer.route_analysis", side_effect=capture):
            analyze_current_email(
                {
                    "subject": "Re: Synthetic note",
                    "from": "buyer@example.test",
                    "to": ["sales@synthetic.internal"],
                    "sent_at": "2026-07-16T09:00:00+00:00",
                    "body_text": "Thanks.",
                    "thread_segments": history,
                },
                config=self._deepseek_config(),
            )

        self.assertEqual(
            [source.body for source in captured[0].sources],
            ["Thanks.", "genuine-adjacent-marker-1", "genuine-adjacent-marker-2"],
        )
        self.assertIs(captured[0].context_limited, True)

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

    def test_terse_reply_participant_overlap_keeps_only_two_adjacent_messages(self) -> None:
        captured = []
        history = [
            {
                "position": index,
                "from": "buyer@example.test",
                "to": "sales@synthetic.internal",
                "subject": "Note",
                "body_text": f"participant-history-marker-{index}",
            }
            for index in range(8)
        ]

        def capture(context, *_args, **_kwargs):
            captured.append(context.model_context.sources)
            return context.fallback

        with patch("backend.email_agent.analyzer.route_analysis", side_effect=capture):
            analyze_current_email(
                {
                    "subject": "Re: Note",
                    "from": "buyer@example.test",
                    "to": ["sales@synthetic.internal"],
                    "body_text": "Please proceed.",
                    "thread_segments": history,
                },
                config=self._deepseek_config(),
            )

        bodies = [source.body for source in captured[0]]
        self.assertEqual(len(bodies), 3)
        self.assertIn("Please proceed.", bodies[0])
        self.assertEqual(
            bodies[1:],
            ["participant-history-marker-6", "participant-history-marker-7"],
        )

    def test_terse_body_ignores_topical_subject_and_keeps_two_adjacent(self) -> None:
        captured = []
        history = [
            {
                "position": index,
                "from": "buyer@example.test",
                "to": "sales@synthetic.internal",
                "subject": "Delivery update",
                "body_text": f"topical-history-marker-{index} delivery update.",
            }
            for index in range(8)
        ]

        def capture(context, *_args, **_kwargs):
            captured.append(context.model_context.sources)
            return context.fallback

        with patch("backend.email_agent.analyzer.route_analysis", side_effect=capture):
            analyze_current_email(
                {
                    "subject": "Re: Delivery update",
                    "from": "buyer@example.test",
                    "to": ["sales@synthetic.internal"],
                    "body_text": "Thanks.",
                    "thread_segments": history,
                },
                config=self._deepseek_config(),
            )

        bodies = [source.body for source in captured[0]]
        self.assertEqual(
            bodies,
            ["Thanks.", "topical-history-marker-6 delivery update.",
             "topical-history-marker-7 delivery update."],
        )

    def test_upstream_context_limited_is_strict_and_survives_all_selection_paths(self) -> None:
        cases = (
            ("current_only", True, [], True),
            (
                "relevant_history",
                True,
                [{
                    "position": 0,
                    "from": "buyer@example.test",
                    "to": "sales@synthetic.internal",
                    "subject": "Delivery note",
                    "body_text": "Please review historical delivery details.",
                }],
                True,
            ),
            ("integer_is_not_true", 1, [], False),
            ("string_is_not_true", "true", [], False),
        )

        for label, upstream, history, expected in cases:
            captured = []

            def capture(context, *_args, **_kwargs):
                captured.append(context.model_context)
                return context.fallback

            with self.subTest(label=label), patch(
                "backend.email_agent.analyzer.route_analysis", side_effect=capture
            ):
                analyze_current_email(
                    {
                        "subject": "Delivery note",
                        "from": "buyer@example.test",
                        "to": ["sales@synthetic.internal"],
                        "body_text": "Please review current delivery details.",
                        "thread_segments": history,
                        "thread_context_limited": upstream,
                    },
                    config=self._deepseek_config(),
                )

            self.assertIs(captured[0].context_limited, expected)

    def test_backend_timeline_coverage_loss_is_reported_as_context_limited(self) -> None:
        cases = (
            (
                "segment_count_over_limit",
                [{"body_text": 7} for _ in range(51)],
                "current_only",
            ),
            (
                "relevant_history_body_truncated",
                [{
                    "position": 0,
                    "from": "buyer@example.test",
                    "to": "sales@synthetic.internal",
                    "subject": "Delivery history",
                    "body_text": "Historical delivery evidence. " + ("x" * 3_000),
                }],
                "relevant_history",
            ),
        )

        for label, history, expected_scope in cases:
            captured = []

            def capture(context, *_args, **_kwargs):
                captured.append(context.model_context)
                return context.fallback

            with self.subTest(label=label), patch(
                "backend.email_agent.analyzer.route_analysis", side_effect=capture
            ):
                analyze_current_email(
                    {
                        "subject": "Delivery note",
                        "from": "buyer@example.test",
                        "to": ["sales@synthetic.internal"],
                        "body_text": "Please review current delivery details.",
                        "thread_segments": history,
                    },
                    config=self._deepseek_config(),
                )

            self.assertEqual(captured[0].context_scope, expected_scope)
            self.assertIs(captured[0].context_limited, True)

    def test_model_context_rejects_non_boolean_upstream_limit_argument(self) -> None:
        with self.assertRaises(TypeError):
            select_model_context(
                subject="Synthetic note",
                sender="buyer@example.test",
                recipients=["sales@synthetic.internal"],
                cc=[],
                sent_at="",
                clean_body="Please review.",
                full_timeline=TimelineBuild({}, (), ()),
                internal_domains=("synthetic.internal",),
                upstream_context_limited=1,  # type: ignore[arg-type]
            )

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
