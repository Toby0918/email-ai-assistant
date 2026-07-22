"""Operational and generated-status closeout contracts for Task 8."""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.support import load_script_module


ROOT = Path(__file__).resolve().parents[1]


class RolloutCloseoutContractTests(unittest.TestCase):
    def test_public_analysis_engine_context_metadata_contract_is_documented(self) -> None:
        schema = (ROOT / "docs" / "data" / "analysis_result_schema.md").read_text(
            encoding="utf-8"
        )
        api = (ROOT / "docs" / "api" / "backend_api_contract.md").read_text(
            encoding="utf-8"
        )

        for text in (schema, api):
            with self.subTest(document="schema" if text is schema else "api"):
                self.assertIn("analysis_engine.context_scope", text)
                self.assertIn("analysis_engine.context_limited", text)
                self.assertIn("current_only | relevant_history", text)
                self.assertIn("both absent or both present", text)
                self.assertIn("no extra keys", text)

    def test_private_model_context_policy_is_documented(self) -> None:
        paths = (
            ROOT / "docs" / "security" / "privacy_rules.md",
            ROOT / "docs" / "security" / "email_data_handling.md",
            ROOT / "docs" / "decisions" / "0005-deepseek-led-analysis.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

        for required in (
            "current-first",
            "relevant_history",
            "downgrades to `current_only`",
            "zero provider calls",
            "per-value deidentification",
            "local exact-fact merge",
            "full deterministic timeline",
        ):
            with self.subTest(required=required):
                self.assertIn(required, combined)

    def test_frontend_task_card_contract_is_documented(self) -> None:
        paths = (
            ROOT / "docs" / "api" / "frontend_backend_flow.md",
            ROOT / "docs" / "operations" / "testing_checklist.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

        for required in (
            "task card",
            "closed native `<details>`",
            "OpenAI 多模态结果未采用，本次使用 DeepSeek 文本回退。",
            "远程模型结果未采用，本次使用安全规则结果。",
            "render_analysis.js",
            "analysis_components.css",
            "0.2.3",
        ):
            with self.subTest(required=required):
                self.assertIn(required, combined)

    def test_real_mailbox_runbook_keeps_separate_live_gates(self) -> None:
        paths = (
            ROOT / "docs" / "operations" / "testing_checklist.md",
            ROOT / "docs" / "operations" / "deployment_notes.md",
            ROOT / "docs" / "operations" / "authorized_mailbox_ingest_task_brief.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

        for required in (
            "python -B -m scripts.manage_mailbox_vault inventory",
            "python -B -m scripts.manage_mailbox_vault scan",
            "STOP after inventory",
            "no credentials are supplied to Codex",
            "no automatic mailbox scan",
            "separate operator confirmations",
        ):
            with self.subTest(required=required):
                self.assertIn(required, combined)

    def test_generated_status_describes_offline_ready_fail_closed_state(self) -> None:
        module = load_script_module(
            ROOT / "scripts" / "generate_project_status.py",
            "generate_project_status_closeout",
        )
        report = module.build_project_status()

        self.assertIn(
            "| Current stage | multimodal_current_email_offline_ready_live_pending |",
            report,
        )
        self.assertIn("administrator-only CLI remains default-off", report)
        self.assertIn("browser extension and normal runtime remain click-only", report)
        self.assertIn("private-knowledge snapshot", report)
        self.assertIn("generic rule fallback", report)
        self.assertIn("60/55/35/10/12/8/5", report)
        self.assertNotIn("15/13/10/5", report)
        self.assertIn("human_judge_unavailable", report)
        self.assertIn("does not switch production models", report)
        self.assertIn("repository leakage scan", report)
        for required in (
            "Task 9 forced OpenAI-to-DeepSeek synthetic fallback is complete",
            "one OpenAI attempt was intercepted before network access",
            "exactly one DeepSeek text-only request",
            "DeepSeek SDK retries were zero",
            "no SQLite write occurred",
            "Task 9 semantic accuracy repair is offline complete",
            "parsed attachment status does not prove semantic correctness",
            "integrated into the current release line",
            "Any new live operation still requires fresh explicit authorization",
        ):
            with self.subTest(required=required):
                self.assertIn(required, report)
        self.assertNotIn(
            "Task 5 real current-message attachment smoke remains pending", report
        )
        self.assertNotIn("The new attachment acquisition path is not live-tested", report)
        self.assertNotIn("integration remains separate", report)

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
        self.assertIn("multimodal_current_email_offline_ready_live_pending", text)
        self.assertIn("Task 9", text)
        self.assertIn(
            "Task 9 semantic accuracy repair is offline complete",
            text,
        )
        self.assertIn(
            "parsed attachment status does not prove semantic correctness", text
        )
        self.assertIn("offline completion does not equal live authorization", text)
        self.assertNotIn("current status is `authorized_private_ingest_build`", text)


if __name__ == "__main__":
    unittest.main()
