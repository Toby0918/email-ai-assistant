"""Golden tests for anonymized local email analysis samples."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from backend.email_agent.analyzer import AnalysisError, analyze_current_email


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_emails.json"


def load_samples() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class GoldenEmailAnalysisTests(unittest.TestCase):
    def test_sample_fixture_uses_only_anonymized_addresses(self) -> None:
        for sample in load_samples():
            with self.subTest(sample=sample["id"]):
                sender = sample["email"]["from"]
                self.assertTrue(sender.endswith(".test"), sender)

    def test_rule_based_analysis_matches_golden_samples(self) -> None:
        for sample in load_samples():
            if "expected_error" in sample:
                continue
            with self.subTest(sample=sample["id"]):
                result = analyze_current_email(sample["email"])
                expected = sample["expected"]

                self.assertEqual(result["category"], expected["category"])
                self.assertEqual(result["priority"], expected["priority"])
                self.assertTrue(result["reply_draft"]["needs_human_review"])
                risk_types = {item["type"] for item in result["risk_flags"]}
                action_types = {item["type"] for item in result["suggested_actions"]}
                self.assertTrue(set(expected["risk_flags"]).issubset(risk_types))
                self.assertTrue(set(expected.get("excluded_risk_flags", [])).isdisjoint(risk_types))
                self.assertTrue(set(expected["action_types"]).issubset(action_types))

    def test_rule_based_analysis_keeps_empty_body_as_error(self) -> None:
        sample = next(item for item in load_samples() if item["id"] == "empty_body")

        with self.assertRaisesRegex(AnalysisError, sample["expected_error"]):
            analyze_current_email(sample["email"])


if __name__ == "__main__":
    unittest.main()
