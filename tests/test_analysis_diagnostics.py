from __future__ import annotations

import inspect
import unittest

from backend.email_agent import analysis_diagnostics
from backend.email_agent.analysis_diagnostics import log_analysis_fallback


class AnalysisDiagnosticsTests(unittest.TestCase):
    def test_event_contains_only_allowlisted_values(self) -> None:
        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            log_analysis_fallback(
                code="provider_auth",
                stage="provider",
                provider="deepseek",
                model="deepseek-v4-flash",
                output_mode="model_led",
                detail="analysis_shape",
                elapsed_ms=123,
            )

        self.assertEqual(len(captured.output), 1)
        self.assertIn(
            "event=analysis_fallback code=provider_auth stage=provider "
            "provider=deepseek model=deepseek-v4-flash "
            "output_mode=model_led detail=not_applicable elapsed_ms=123",
            captured.output[0],
        )

    def test_fixed_envelope_details_appear_unchanged(self) -> None:
        envelope_details = (
            "json_syntax",
            "top_level_shape",
            "schema_version",
            "analysis_shape",
            "attachment_shape",
            "field_evidence_shape",
        )
        self.assertEqual(
            analysis_diagnostics.FALLBACK_DETAILS,
            frozenset({"not_applicable", *envelope_details}),
        )
        self.assertIn(
            "provider_output_placeholder_echo",
            analysis_diagnostics.FALLBACK_REASON_CODES,
        )

        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            for detail in envelope_details:
                log_analysis_fallback(
                    code="envelope_invalid",
                    stage="envelope",
                    provider="deepseek",
                    model="deepseek-v4-flash",
                    output_mode="model_led",
                    detail=detail,
                    elapsed_ms=123,
                )

        self.assertEqual(len(captured.output), len(envelope_details))
        for detail, event in zip(envelope_details, captured.output, strict=True):
            with self.subTest(detail=detail):
                self.assertIn(f"detail={detail}", event)

    def test_placeholder_echo_has_one_fixed_content_free_reason_code(self) -> None:
        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            log_analysis_fallback(
                code="provider_output_placeholder_echo",
                stage="safety",
                provider="deepseek",
                model="deepseek-v4-flash",
                output_mode="model_led",
                detail="not_applicable",
                elapsed_ms=123,
            )

        self.assertIn(
            "code=provider_output_placeholder_echo stage=safety",
            captured.output[0],
        )
        self.assertIn("detail=not_applicable", captured.output[0])

    def test_invalid_detail_fails_closed_without_logging_private_text(self) -> None:
        private = "PRIVATE_DETAIL_MARKER\nPRIVATE_URL"

        class AllowlistedEvilString(str):
            def __str__(self) -> str:
                return private

        for detail in (private, AllowlistedEvilString("analysis_shape")):
            with self.subTest(detail=type(detail).__name__), self.assertLogs(
                "backend.email_agent.analysis_diagnostics", level="WARNING"
            ) as captured:
                log_analysis_fallback(
                    code="envelope_invalid",
                    stage="envelope",
                    provider="deepseek",
                    model="deepseek-v4-flash",
                    output_mode="model_led",
                    detail=detail,
                    elapsed_ms=123,
                )

            text = captured.output[0]
            self.assertNotIn("PRIVATE", text)
            self.assertIn("detail=not_applicable", text)

    def test_unknown_values_cannot_inject_private_text(self) -> None:
        private = "PRIVATE_SECRET_PROMPT\nPRIVATE_URL"

        class AllowlistedEvilString(str):
            def __str__(self) -> str:
                return private

        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            log_analysis_fallback(
                code=private,
                stage=private,
                provider=private,
                model=private,
                output_mode=private,
                detail="not_applicable",
                elapsed_ms=-9,
            )

        text = captured.output[0]
        self.assertNotIn("PRIVATE", text)
        self.assertIn("code=unexpected_analysis_error", text)
        self.assertIn("stage=analysis", text)
        self.assertIn("provider=unknown model=unknown output_mode=unknown", text)
        self.assertIn("detail=not_applicable", text)
        self.assertIn("elapsed_ms=0", text)

        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as subclass_captured:
            log_analysis_fallback(
                code=AllowlistedEvilString("provider_auth"),
                stage=AllowlistedEvilString("provider"),
                provider=AllowlistedEvilString("deepseek"),
                model=AllowlistedEvilString("deepseek-v4-flash"),
                output_mode=AllowlistedEvilString("model_led"),
                detail=AllowlistedEvilString("analysis_shape"),
                elapsed_ms=123,
            )

        subclass_text = subclass_captured.output[0]
        self.assertNotIn("PRIVATE", subclass_text)
        self.assertIn("code=unexpected_analysis_error", subclass_text)
        self.assertIn("stage=analysis", subclass_text)
        self.assertIn(
            "provider=unknown model=unknown output_mode=unknown", subclass_text
        )
        self.assertIn("detail=not_applicable", subclass_text)

    def test_signature_has_no_sensitive_payload_channel(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(log_analysis_fallback).parameters),
            (
                "code",
                "stage",
                "provider",
                "model",
                "output_mode",
                "detail",
                "elapsed_ms",
            ),
        )


if __name__ == "__main__":
    unittest.main()
