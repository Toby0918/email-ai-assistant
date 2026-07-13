"""Semantic and mechanical contracts for the offline DeepSeek replay gate."""

from __future__ import annotations

import ast
import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "deepseek_eval" / "cases.json"
FAILURE_CASES = {
    "automatic_action",
    "passive_commitment",
    "unsupported_fact",
    "malformed_json",
    "evidence_failure",
}
SIZE_CHECK_PATHS = (
    ROOT / "scripts" / "evaluate_deepseek_analysis.py",
    ROOT / "scripts" / "deepseek_eval_replay.py",
    ROOT / "tests" / "deepseek_eval_support.py",
)


class DeepSeekEvalFixtureContractTests(unittest.TestCase):
    def test_exactly_ten_failures_cover_each_raw_failure_twice(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        counts = Counter(case["provider_case"] for case in cases)

        self.assertEqual(counts["accepted"], 40)
        self.assertEqual({name: counts[name] for name in FAILURE_CASES}, {
            name: 2 for name in FAILURE_CASES
        })
        for case in cases:
            expected = (
                "rule_fallback"
                if case["provider_case"] in FAILURE_CASES
                else "ai_model"
            )
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(case["expected"]["analysis_source"], expected)

    def test_evaluator_support_modules_respect_size_limits(self) -> None:
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
