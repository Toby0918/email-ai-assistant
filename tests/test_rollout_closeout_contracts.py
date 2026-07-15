"""Operational and generated-status closeout contracts for Task 7."""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.support import load_script_module


ROOT = Path(__file__).resolve().parents[1]


class RolloutCloseoutContractTests(unittest.TestCase):
    def test_generated_status_describes_offline_ready_fail_closed_state(self) -> None:
        module = load_script_module(
            ROOT / "scripts" / "generate_project_status.py",
            "generate_project_status_closeout",
        )
        report = module.build_project_status()

        self.assertIn("| Current stage | authorized_private_analysis_offline_ready |", report)
        self.assertIn("administrator-only CLI remains default-off", report)
        self.assertIn("browser extension and normal runtime remain click-only", report)
        self.assertIn("private-knowledge snapshot", report)
        self.assertIn("generic rule fallback", report)
        self.assertIn("15/13/10/5", report)
        self.assertIn("human_judge_unavailable", report)
        self.assertIn("does not switch production models", report)
        self.assertIn("repository leakage scan", report)

    def test_testing_checklist_has_complete_offline_release_sequence(self) -> None:
        text = (ROOT / "docs" / "operations" / "testing_checklist.md").read_text(
            encoding="utf-8"
        )
        for required in (
            "python -B -m scripts.manage_mailbox_vault init",
            "python -B -m scripts.manage_mailbox_vault inventory",
            "--confirm-inventory-fingerprint",
            "attachment approval",
            "50",
            "python -B -m scripts.manage_mailbox_vault verify",
            "python -B -m scripts.manage_mailbox_vault purge-expired",
            "python -B -m scripts.manage_mailbox_vault revoke",
            "python -B -m scripts.manage_mailbox_vault rewrap-recovery",
            "python -B -m scripts.manage_private_knowledge import-candidate",
            "python -B -m scripts.manage_private_knowledge publish",
            "python -B -m scripts.evaluate_private_deepseek verify",
            "human_judge_unavailable",
            "evaluate_deepseek_analysis.py",
            "repository_leakage_scan",
            "--fail-on-high",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_review_and_deployment_docs_cover_stops_and_rollbacks(self) -> None:
        review = (ROOT / "docs" / "operations" / "review_checklist.md").read_text(
            encoding="utf-8"
        )
        deployment = (ROOT / "docs" / "operations" / "deployment_notes.md").read_text(
            encoding="utf-8"
        )
        combined = review + deployment
        for required in (
            "not a legal archive",
            "no automatic second backup",
            "best-effort",
            "zero-retention",
            "incident stop",
            "EMAIL_AGENT_LLM_PROVIDER=disabled",
            "generic rule fallback",
            "dual approval",
            "human_judge_unavailable",
            "no automatic production model switch",
        ):
            with self.subTest(required=required):
                self.assertIn(required, combined)

    def test_project_structure_lists_all_isolated_packages_and_admin_clis(self) -> None:
        text = (ROOT / "docs" / "operations" / "project_structure.md").read_text(
            encoding="utf-8"
        )
        for required in (
            "backend/mailbox_ingest/",
            "backend/private_knowledge/",
            "backend/private_evaluation/",
            "scripts/manage_mailbox_vault.py",
            "scripts/manage_private_knowledge.py",
            "scripts/evaluate_private_deepseek.py",
            "scripts/repository_leakage_scan.py",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_product_roadmap_does_not_claim_live_authorization(self) -> None:
        text = (ROOT / "docs" / "product" / "roadmap.md").read_text(encoding="utf-8")
        self.assertIn("authorized_private_analysis_offline_ready", text)
        self.assertIn("offline completion does not equal live authorization", text)
        self.assertNotIn("current status is `authorized_private_ingest_build`", text)


if __name__ == "__main__":
    unittest.main()
