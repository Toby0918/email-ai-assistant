from __future__ import annotations

import inspect
import unittest

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
                elapsed_ms=123,
            )

        self.assertEqual(len(captured.output), 1)
        self.assertIn(
            "event=analysis_fallback code=provider_auth stage=provider "
            "provider=deepseek model=deepseek-v4-flash "
            "output_mode=model_led elapsed_ms=123",
            captured.output[0],
        )

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
                elapsed_ms=-9,
            )

        text = captured.output[0]
        self.assertNotIn("PRIVATE", text)
        self.assertIn("code=unexpected_analysis_error", text)
        self.assertIn("stage=analysis", text)
        self.assertIn("provider=unknown model=unknown output_mode=unknown", text)
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
                elapsed_ms=123,
            )

        subclass_text = subclass_captured.output[0]
        self.assertNotIn("PRIVATE", subclass_text)
        self.assertIn("code=unexpected_analysis_error", subclass_text)
        self.assertIn("stage=analysis", subclass_text)
        self.assertIn(
            "provider=unknown model=unknown output_mode=unknown", subclass_text
        )

    def test_signature_has_no_sensitive_payload_channel(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(log_analysis_fallback).parameters),
            ("code", "stage", "provider", "model", "output_mode", "elapsed_ms"),
        )


if __name__ == "__main__":
    unittest.main()
