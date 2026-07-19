"""Offline routing matrix for OpenAI, text fallback, and deterministic rules."""

from __future__ import annotations

import copy
import unittest
from contextlib import ExitStack
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.email_agent.analysis_budget import AnalysisBudget
from backend.email_agent.analyzer import analyze_current_email
from backend.email_agent.attachment_model_context import (
    AttachmentAnalysisBundle,
    attachment_model_candidate,
)
from backend.email_agent.attachment_media_context import UNTRUSTED_MEDIA_EVIDENCE
from backend.email_agent.attachment_storage import StoredAttachment
from backend.email_agent.config import load_config
from backend.email_agent.llm_client import LlmClientError
from backend.email_agent.model_request import ModelAnalysisRequest
from backend.email_agent.model_result_safety import SafeMergeResult
from backend.email_agent.multimodal_media import PreparedMediaAsset
from backend.email_agent.openai_multimodal_client import _validated_output
from backend.email_agent.private_analysis_route import PrivateAnalysisRouteError


class MultimodalRouteTests(unittest.TestCase):
    def test_openai_success_uses_private_multimodal_request_and_openai_label(self) -> None:
        calls: list[object] = []
        assets = (
            self._asset("attachment:0", 0),
            self._asset("attachment:0", 1),
        )

        def generate(request: object) -> str:
            calls.append(request)
            self.assertIs(type(request), ModelAnalysisRequest)
            self.assertEqual(request.media_assets, assets)
            self.assertNotIn("buyer@example.test", request.text)
            return "{}"

        with self.assertNoLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ):
            result, source_views = self._analyze(
                generate,
                config=self._openai_config(text_fallback_provider="deepseek"),
                bundles=(self._bundle("visual.png"),),
                assets=assets,
            )

        self.assertEqual(len(calls), 1)
        request = calls[0]
        self.assertIs(type(request), ModelAnalysisRequest)
        self.assertIn('"source_id":"attachment:0"', request.text)
        self.assertIn(
            "sanitized current-message visual media is supplied and has no "
            "locally extracted text.",
            request.text,
        )
        self.assertNotIn(UNTRUSTED_MEDIA_EVIDENCE, request.text)
        self.assertEqual(result["analysis_engine"], {
            "source": "ai_model", "label": "OpenAI GPT-5.6 Sol",
        })
        self.assertTrue(result["reply_draft"]["needs_human_review"])
        self.assertEqual(len(source_views), 1)
        self.assertEqual(source_views[0]["attachment:0"].grounding_mode, "visual")

    def test_early_openai_failure_uses_one_text_only_deepseek_fallback(self) -> None:
        calls: list[object] = []
        assets = (self._asset("attachment:0", 0), self._asset("attachment:1", 1))
        bundles = (
            self._bundle("visual-only.png"),
            self._bundle(
                "office.docx",
                candidate_text="Visible packaging note from the office document.",
                source_id="attachment:1",
            ),
        )

        def generate(request: object) -> str:
            calls.append(request)
            if len(calls) == 1:
                self.assertIs(type(request), ModelAnalysisRequest)
                self.assertEqual(request.media_assets, assets)
                raise LlmClientError(
                    "synthetic openai failure", reason_code="provider_timeout"
                )
            self.assertIs(type(request), str)
            self.assertNotIn("UNTRUSTED_MEDIA", request)
            self.assertIn("Visible packaging note", request)
            return "{}"

        with self.assertNoLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ):
            result, source_views = self._analyze(
                generate,
                config=self._openai_config(text_fallback_provider="deepseek"),
                bundles=bundles,
                assets=assets,
            )

        self.assertEqual(tuple(type(item) for item in calls), (ModelAnalysisRequest, str))
        self.assertEqual(result["analysis_engine"], {
            "source": "ai_model",
            "label": "DeepSeek V4 Flash text fallback",
        })
        self.assertEqual(len(source_views), 1)
        fallback_sources = source_views[0]
        self.assertNotIn("attachment:0", fallback_sources)
        self.assertEqual(fallback_sources["attachment:1"].grounding_mode, "text")

    def test_late_openai_failure_makes_zero_deepseek_calls(self) -> None:
        now = [100.0]
        budget = AnalysisBudget.start(clock=lambda: now[0])
        calls: list[object] = []

        def generate(request: object) -> str:
            calls.append(request)
            self.assertIs(type(request), ModelAnalysisRequest)
            now[0] = budget.deadline - 11.0
            raise LlmClientError("late", reason_code="provider_timeout")

        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            result, _views = self._analyze(
                generate,
                config=self._openai_config(text_fallback_provider="deepseek"),
                budget=budget,
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
        self.assertEqual(len(captured.output), 1)
        self.assertIn("provider=openai model=gpt-5.6-sol", captured.output[0])

    def test_fallback_disabled_stops_after_openai_failure(self) -> None:
        calls: list[object] = []

        def generate(request: object) -> str:
            calls.append(request)
            self.assertIs(type(request), ModelAnalysisRequest)
            raise LlmClientError("disabled", reason_code="provider_connection_error")

        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            result, _views = self._analyze(
                generate,
                config=self._openai_config(text_fallback_provider="disabled"),
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
        self.assertIn(
            "code=provider_connection_error stage=provider provider=openai "
            "model=gpt-5.6-sol",
            captured.output[0],
        )

    def test_both_provider_failures_log_only_terminal_deepseek_failure(self) -> None:
        calls: list[object] = []

        def generate(request: object) -> str:
            calls.append(request)
            if len(calls) == 1:
                self.assertIs(type(request), ModelAnalysisRequest)
                raise LlmClientError("openai", reason_code="provider_timeout")
            self.assertIs(type(request), str)
            raise LlmClientError("deepseek", reason_code="provider_server_error")

        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            result, _views = self._analyze(
                generate,
                config=self._openai_config(text_fallback_provider="deepseek"),
            )

        self.assertEqual(tuple(type(item) for item in calls), (ModelAnalysisRequest, str))
        self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
        self.assertEqual(len(captured.output), 1)
        self.assertIn(
            "code=provider_server_error stage=provider provider=deepseek "
            "model=deepseek-v4-flash",
            captured.output[0],
        )

    def test_privacy_preflight_failure_never_enters_text_fallback(self) -> None:
        calls: list[object] = []
        with patch(
            "backend.email_agent.analysis_model_routes._prepare_model_led_request",
            side_effect=PrivateAnalysisRouteError(
                "privacy_preflight_rejected", "safety"
            ),
        ), self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            result, _views = self._analyze(
                lambda request: calls.append(request) or "{}",
                config=self._openai_config(text_fallback_provider="deepseek"),
            )

        self.assertEqual(calls, [])
        self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
        self.assertIn("provider=openai model=gpt-5.6-sol", captured.output[0])

    def test_mapped_openai_privacy_output_never_enters_text_fallback(self) -> None:
        calls: list[object] = []

        def generate(request: object) -> str:
            calls.append(request)
            if type(request) is ModelAnalysisRequest:
                return _validated_output(SimpleNamespace(
                    status="completed",
                    output_text='{"private_context":"forbidden"}',
                ))
            return "{}"

        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            result, _views = self._analyze(
                generate,
                config=self._openai_config(text_fallback_provider="deepseek"),
            )

        self.assertEqual(tuple(type(item) for item in calls), (ModelAnalysisRequest,))
        self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
        self.assertIn("code=safety_rejected_all", captured.output[0])
        self.assertNotIn("private_context", "\n".join(captured.output))
        self.assertNotIn("forbidden", "\n".join(captured.output))

    def test_mapped_openai_invalid_output_still_allows_text_fallback(self) -> None:
        calls: list[object] = []

        def generate(request: object) -> str:
            calls.append(request)
            if type(request) is ModelAnalysisRequest:
                return _validated_output(SimpleNamespace(
                    status="completed", output_text="not-json",
                ))
            return "{}"

        result, _views = self._analyze(
            generate,
            config=self._openai_config(text_fallback_provider="deepseek"),
        )

        self.assertEqual(
            tuple(type(item) for item in calls),
            (ModelAnalysisRequest, str),
        )
        self.assertEqual(
            result["analysis_engine"]["label"],
            "DeepSeek V4 Flash text fallback",
        )

    def test_fallback_final_budget_sample_blocks_12_to_11_9_drop(self) -> None:
        for final_remaining in (11.9, 11.999):
            with self.subTest(final_remaining=final_remaining):
                budget = AnalysisBudget(
                    deadline=100.0,
                    _clock=lambda value=final_remaining: 100.0 - value,
                )
                calls: list[object] = []

                def generate(request: object) -> str:
                    calls.append(request)
                    if type(request) is ModelAnalysisRequest:
                        raise LlmClientError("late", reason_code="provider_timeout")
                    return "{}"

                with patch(
                    "backend.email_agent.analysis_model_routes."
                    "_text_fallback_budget_available",
                    return_value=True,
                ):
                    result, _views = self._analyze(
                        generate,
                        config=self._openai_config(
                            text_fallback_provider="deepseek"
                        ),
                        budget=budget,
                    )

                self.assertEqual(
                    tuple(type(item) for item in calls),
                    (ModelAnalysisRequest,),
                )
                self.assertEqual(
                    result["analysis_engine"]["source"], "rule_fallback"
                )

    def test_openai_mixed_office_source_keeps_text_and_visual_capabilities(self) -> None:
        bundles = (
            self._bundle("visual.png"),
            self._bundle(
                "office.docx",
                candidate_text="Visible packaging note from the office document.",
                source_id="attachment:1",
            ),
        )
        assets = (self._asset("attachment:1", 0),)

        result, source_views = self._analyze(
            lambda _request: "{}",
            config=self._openai_config(),
            bundles=bundles,
            assets=assets,
        )

        source = source_views[0]["attachment:1"]
        self.assertEqual(result["analysis_engine"]["source"], "ai_model")
        self.assertEqual(source.grounding_mode, "hybrid")
        self.assertIn("Visible packaging note", source.grounding_text)

    def test_openai_extracted_text_equal_to_visual_descriptor_stays_hybrid(self) -> None:
        descriptor = (
            "sanitized current-message visual media is supplied and has no "
            "locally extracted text."
        )
        bundles = (
            self._bundle("office.docx", candidate_text=descriptor),
        )
        assets = (self._asset("attachment:0", 0),)

        result, source_views = self._analyze(
            lambda _request: "{}",
            config=self._openai_config(),
            bundles=bundles,
            assets=assets,
        )

        source = source_views[0]["attachment:0"]
        self.assertEqual(result["analysis_engine"]["source"], "ai_model")
        self.assertEqual(source.grounding_mode, "hybrid")
        self.assertEqual(source.grounding_text, descriptor)

    def _analyze(
        self,
        generator,
        *,
        config,
        bundles: tuple[AttachmentAnalysisBundle, ...] = (),
        assets: tuple[PreparedMediaAsset, ...] = (),
        budget: AnalysisBudget | None = None,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        source_views: list[dict[str, object]] = []

        def merge(_envelope, *, fallback, sources, **_kwargs):
            source_views.append(dict(sources))
            analysis = copy.deepcopy(fallback)
            analysis["summary"] = "\u9700\u8981\u4eba\u5de5\u6838\u67e5\u5f53\u524d\u8bf7\u6c42\u3002"
            return SafeMergeResult(analysis, True, ())

        with ExitStack() as stack:
            stack.enter_context(patch(
                "backend.email_agent.analyzer._parse_bundles", return_value=bundles
            ))
            stack.enter_context(patch(
                "backend.email_agent.analyzer.prepare_attachment_media",
                return_value=assets,
            ))
            stack.enter_context(patch(
                "backend.email_agent.analysis_model_routes.parse_deepseek_analysis_v1",
                return_value={},
            ))
            stack.enter_context(patch(
                "backend.email_agent.analysis_model_routes.validate_envelope_evidence",
                return_value={},
            ))
            stack.enter_context(patch(
                "backend.email_agent.analysis_model_routes.merge_deepseek_analysis_v1",
                side_effect=merge,
            ))
            result = analyze_current_email(
                self._email(len(bundles)),
                llm_generate=generator,
                analysis_engine_label="Spoofed engine",
                config=config,
                budget=budget,
            )
        return result, source_views

    @staticmethod
    def _openai_config(**changes):
        values = {
            "llm_provider": "openai",
            "openai_api_key": "synthetic-openai-key",
            "deepseek_api_key": "synthetic-deepseek-key",
            "deepseek_model": "deepseek-v4-flash",
            "deepseek_output_mode": "model_led",
        }
        values.update(changes)
        return replace(load_config(dotenv_path=None), **values)

    @staticmethod
    def _asset(source_id: str, index: int) -> PreparedMediaAsset:
        return PreparedMediaAsset(
            source_id=source_id,
            provider_filename=f"image_{index}.png",
            mime_type="image/png",
            kind="image",
            detail="high",
            buffer=bytearray(b"SYNTHETIC_MEDIA"),
        )

    @staticmethod
    def _bundle(
        filename: str, *, candidate_text: str | None = None,
        source_id: str = "attachment:0",
    ) -> AttachmentAnalysisBundle:
        display = {
            "filename": filename,
            "type": "docx" if filename.endswith(".docx") else "image",
            "status": "parsed" if candidate_text is not None else "metadata_only",
            "summary": "Synthetic attachment status.",
            "key_facts": [],
            "limitations": [],
        }
        candidate = (
            attachment_model_candidate(source_id, candidate_text)
            if candidate_text is not None
            else None
        )
        return AttachmentAnalysisBundle(display, candidate)

    @staticmethod
    def _email(attachment_count: int) -> dict[str, object]:
        stored = [
            StoredAttachment(
                safe_filename=f"synthetic-{index}.png",
                type="image",
                path=Path(f"synthetic-{index}.png"),
                byte_size=1,
                expires_at=datetime.now(UTC),
            )
            for index in range(attachment_count)
        ]
        return {
            "subject": "Synthetic packaging review",
            "from": "buyer@example.test",
            "body_text": "Please review the current packaging condition.",
            "stored_attachments": stored,
        }


if __name__ == "__main__":
    unittest.main()
