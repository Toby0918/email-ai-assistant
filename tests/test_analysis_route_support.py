"""Focused contracts for provider-neutral analysis route values."""

from __future__ import annotations

import unittest

from backend.email_agent.analysis_route_support import ModelRun


class ModelRunTests(unittest.TestCase):
    def test_model_run_carries_only_accepted_public_engine_metadata(self) -> None:
        run = ModelRun(
            analysis={"summary": "synthetic"},
            engine_source="ai_model",
            engine_label="OpenAI GPT-5.6 Sol",
        )

        self.assertEqual(run.engine_source, "ai_model")
        self.assertEqual(run.engine_label, "OpenAI GPT-5.6 Sol")
        self.assertNotIn("request", repr(run).casefold())


if __name__ == "__main__":
    unittest.main()
