"""Contracts that close Task 9 offline semantics without closing live integration."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_SURFACES = (
    "docs/decisions/0007-multimodal-current-email-analysis.md",
    "docs/operations/task9_semantic_accuracy_repair_task_brief.md",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "docs/operations/project_status_log.md",
    "docs/operations/testing_checklist.md",
    "docs/product/roadmap.md",
    "scripts/generate_project_status.py",
)


class Task9SemanticAccuracyContractTests(unittest.TestCase):
    def _read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_status_surfaces_close_only_the_offline_semantic_repair(self) -> None:
        for relative in STATUS_SURFACES:
            text = self._read(relative)
            normalized_text = " ".join(text.split())
            with self.subTest(path=relative):
                self.assertNotIn(
                    "remaining Task 9 gate is final master integration", normalized_text
                )
                self.assertIn(
                    "Task 9 semantic accuracy repair is offline complete", normalized_text
                )
                self.assertNotIn(
                    "Task 9 semantic accuracy repair is in progress", normalized_text
                )
                self.assertIn(
                    "parsed attachment status does not prove semantic correctness",
                    normalized_text,
                )

    def test_canonical_task9_brief_closes_the_semantic_evidence_gates(self) -> None:
        text = " ".join(
            self._read(
                "docs/operations/task9_semantic_accuracy_repair_task_brief.md"
            ).split()
        )
        for marker in (
            "same complete bounded source set to the deterministic timeline and model selection",
            "every sent parsed attachment",
            "Backend-generated semantic-review and cross-source warning items survive model merge",
            "independently authored human reference",
            "Offline implementation and independent review are complete",
            "Any new live operation still requires fresh explicit authorization",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_repair_contract_separates_extraction_semantics_and_usefulness(self) -> None:
        combined = self._read(
            "docs/operations/task9_semantic_accuracy_repair_task_brief.md"
        )
        for marker in (
            "Extraction, semantic correctness, and human usefulness are three separate measurements",
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
