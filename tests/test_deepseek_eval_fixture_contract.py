"""Semantic and mechanical contracts for the offline DeepSeek gate."""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "deepseek_eval" / "cases.json"
FALLBACK_SCENARIOS = {
    "fallback_timeout",
    "fallback_malformed_json",
    "fallback_disabled",
    "unsafe_commitment",
    "automatic_action",
}
SIZE_CHECK_PATHS = (
    ROOT / "scripts" / "evaluate_deepseek_analysis.py",
    ROOT / "tests" / "deepseek_eval_support.py",
)


class DeepSeekEvalFixtureContractTests(unittest.TestCase):
    def test_exactly_ten_fallbacks_map_only_to_failure_scenarios(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        selected_fallbacks = 0
        for case in cases:
            should_fallback = case["scenario"] in FALLBACK_SCENARIOS
            expected_result = (
                "rule_public_result" if should_fallback else "model_public_result"
            )
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(case["expected"]["selected_result"], expected_result)
                self.assertEqual(case["review_labels"]["used_fallback"], should_fallback)
                selected = case["recorded_results"][expected_result]
                expected_engine = "rule_fallback" if should_fallback else "ai_model"
                self.assertEqual(selected["analysis_engine"]["source"], expected_engine)
            selected_fallbacks += should_fallback
        self.assertEqual(selected_fallbacks, 10)

    def test_evaluator_and_support_modules_respect_size_limits(self) -> None:
        for path in SIZE_CHECK_PATHS:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            with self.subTest(path=path.name, constraint="module"):
                self.assertLessEqual(len(source.splitlines()), 300)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    length = node.end_lineno - node.lineno + 1
                    with self.subTest(path=path.name, function=node.name):
                        self.assertLessEqual(length, 50)


if __name__ == "__main__":
    unittest.main()
