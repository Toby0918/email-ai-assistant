"""Contracts that close Task 9 offline semantics without closing live integration."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_SURFACES = (
    ".superpowers/sdd/progress.md",
    "docs/decisions/0007-multimodal-current-email-analysis.md",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "docs/operations/project_status_log.md",
    "docs/operations/testing_checklist.md",
    "docs/product/roadmap.md",
    "docs/superpowers/plans/2026-07-16-multimodal-current-email-analysis.md",
    "scripts/generate_project_status.py",
)


class Task9SemanticAccuracyContractTests(unittest.TestCase):
    def _read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_status_surfaces_close_only_the_offline_semantic_repair(self) -> None:
        for relative in STATUS_SURFACES:
            text = self._read(relative)
            with self.subTest(path=relative):
                self.assertNotIn(
                    "remaining Task 9 gate is final master integration", text
                )
                self.assertIn(
                    "Task 9 semantic accuracy repair is offline complete", text
                )
                self.assertNotIn("Task 9 semantic accuracy repair is in progress", text)
                self.assertIn(
                    "parsed attachment status does not prove semantic correctness",
                    text,
                )

    def test_original_task9_plan_closes_the_semantic_evidence_gates(self) -> None:
        text = self._read(
            "docs/superpowers/plans/2026-07-16-multimodal-current-email-analysis.md"
        )
        for marker in (
            "2026-07-20-task9-semantic-accuracy-repair.md",
            "current message and bounded verified history use one backend evidence set",
            "every provider-visible parsed attachment is semantically accounted for",
            "deterministic reconciliation safeguards survive model merge",
            "private human gold-standard contract is documented",
        ):
            with self.subTest(marker=marker):
                self.assertIn(f"- [x] {marker}", text)
        self.assertIn(
            "- [ ] Run final diff/status/leakage checks, merge the reviewed commits",
            text,
        )

    def test_repair_contract_separates_extraction_semantics_and_usefulness(self) -> None:
        combined = self._read(
            "docs/operations/task9_semantic_accuracy_repair_task_brief.md"
        ) + self._read(
            "docs/superpowers/specs/2026-07-20-task9-semantic-accuracy-repair-design.md"
        )
        for marker in (
            "Extraction, semantic correctness, and human usefulness",
            "current message, bounded verified history",
            "every sent parsed attachment",
            "independently authored human reference",
            "cannot guarantee",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_thread_limitation_request_boolean_is_explicit_and_content_free(self) -> None:
        api = self._read("docs/api/backend_api_contract.md")
        brief = self._read(
            "docs/operations/task9_semantic_accuracy_repair_task_brief.md"
        )
        combined = api + brief
        for marker in (
            "thread_context_limited",
            "optional request boolean",
            "backward-compatible",
            "literal `true`",
            "no diagnostic text",
            "no response schema change",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)
        self.assertNotIn("Public HTTP JSON: none", brief)


if __name__ == "__main__":
    unittest.main()
