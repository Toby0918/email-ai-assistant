"""Tests for scripts/generate_project_status.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import load_script_module


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_project_status.py"


class GenerateProjectStatusTests(unittest.TestCase):
    def test_script_exists(self) -> None:
        # The status generator is part of the Agent handoff contract.
        self.assertTrue(SCRIPT.exists(), "scripts/generate_project_status.py should exist")

    def test_build_project_status_contains_agent_handoff_sections(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        self.assertIn("# Project Status Log", report)
        self.assertIn("Agent-readable project progress snapshot", report)
        self.assertIn("## Snapshot", report)
        self.assertIn("## Guardrails Established", report)
        self.assertIn("## Key File Status", report)
        self.assertIn("## Recommended Next Steps", report)
        self.assertIn("## Do Not Touch Boundaries", report)

    def test_project_summary_is_readable_chinese(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        self.assertIn("本项目是企业邮箱中的 AI 辅助窗口", report)
        self.assertIn("用户点击按钮后分析当前打开邮件", report)
        self.assertNotIn("浼佷笟", report)
        self.assertNotIn("鈥", report)
        self.assertNotIn("涓嶆", report)

    def test_hard_boundaries_are_rendered_readably(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        self.assertIn("不接入真实邮箱账号", report)
        self.assertIn("不读取真实邮箱数据", report)
        self.assertIn("不自动发送邮件", report)
        self.assertIn("不把 OpenAI API key 放入前端", report)

    def test_golden_fixture_files_move_stage_to_local_eval(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        if (ROOT / "tests" / "fixtures" / "sample_emails.json").exists():
            expected_stage = (
                "multimodal_current_email_offline_ready_live_pending"
                if (
                    ROOT
                    / "docs"
                    / "operations"
                    / "authorized_mailbox_ingest_task_brief.md"
                ).exists()
                else "local_eval_mvp"
            )
            self.assertIn(f"| Current stage | {expected_stage} |", report)

    def test_authorized_ingest_stage_preserves_normal_runtime_boundary(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        self.assertIn(
            "| Current stage | multimodal_current_email_offline_ready_live_pending |",
            report,
        )
        self.assertIn("administrator-only CLI", report)
        self.assertIn("one authorized account", report)
        self.assertIn("rolling 24-month window", report)
        self.assertIn("browser extension and normal runtime remain click-only", report)
        self.assertIn("cannot scan a mailbox", report)

    def test_authorized_ingest_guardrails_and_next_steps_are_reported(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        self.assertIn("Authorized mailbox ingest boundary", report)
        self.assertIn("`docs/operations/authorized_mailbox_ingest_task_brief.md`", report)
        self.assertIn("`docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`", report)
        self.assertIn("`tests/test_mailbox_transport_constraints.py`", report)
        self.assertIn("Keep `EMAIL_AGENT_LLM_PROVIDER=disabled`", report)
        self.assertIn("repository leakage scan", report)
        self.assertIn("human_judge_unavailable", report)
        self.assertIn(
            "Task 9 semantic accuracy repair is offline complete",
            report,
        )
        self.assertIn(
            "Task 9 forced OpenAI-to-DeepSeek synthetic fallback is complete",
            report,
        )
        self.assertIn("one OpenAI attempt was intercepted before network access", report)
        self.assertIn("exactly one DeepSeek text-only request", report)
        self.assertIn("DeepSeek SDK retries were zero", report)
        self.assertIn(
            "parsed attachment status does not prove semantic correctness", report
        )
        self.assertIn("integrated into the current release line", report)
        self.assertNotIn("integration remains separate", report)
        self.assertNotIn("integrate the reviewed work into `master`", report)
        self.assertNotIn("remaining Task 9 gate is final master integration", report)
        self.assertIn(
            "Any new live operation still requires fresh explicit authorization",
            report,
        )
        self.assertNotIn("current-clicked Tencent smoke remains pending", report)

    def test_bounded_handoff_contract_and_adr_are_reported(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status_handoffs")
        report = module.build_project_status()

        for marker in (
            "Bounded corpus-to-runtime handoffs",
            "Issue #10 adds no sync command or evidence inbox",
            "future issues #17 and #18",
            "`backend/current_evidence/artifact_policy.py`",
            "`backend/current_evidence/contract.py`",
            "`backend/current_evidence/handoff.py`",
            "`docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md`",
            "`docs/operations/bounded_corpus_runtime_handoffs_task_brief.md`",
            "`tests/test_current_evidence_handoff.py`",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, report)

    def test_governed_sales_corpus_bootstrap_is_reported(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status_sales_corpus")
        report = module.build_project_status()

        for marker in (
            "Issue #11 governed sales-corpus bootstrap is offline implemented",
            "`backend/mailbox_ingest/governed_scan.py`",
            "`backend/mailbox_ingest/sales_corpus_index.py`",
            "`backend/mailbox_ingest/sales_message_policy.py`",
            "`docs/operations/issue11_governed_sales_corpus_task_brief.md`",
            "`tests/test_mailbox_governed_scan.py`",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, report)

    def test_attachment_acquisition_safeguards_and_live_gate_are_reported(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status_attachments")
        report = module.build_project_status()

        for marker in (
            "verified legacy current-message control",
            "manual picker selection is inert until Analyze",
            "5 files, 10 MiB per file, and 25 MiB total",
            "request `finally`",
            "24-hour mtime cleanup is crash recovery only",
            "Only `attachment_insights[].status=parsed` proves content parsing",
            "Task 9 semantic accuracy repair is offline complete",
            "parsed attachment status does not prove semantic correctness",
            "Any new live operation still requires fresh explicit authorization",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, report)
        self.assertNotIn(
            "Task 5 real current-message attachment smoke remains pending", report
        )
        self.assertNotIn("The new attachment acquisition path is not live-tested", report)

    def test_status_log_uses_stable_head_reference(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        self.assertIn("| Git HEAD reference | Run `git rev-parse --short HEAD` in this workspace |", report)
        self.assertIn("| Working tree status | Run `git status --short --ignored` in this workspace |", report)
        self.assertNotIn("| Git commit |", report)
        self.assertNotIn("| Working tree dirty |", report)

    def test_local_eval_next_steps_reflect_first_phase_closeout(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        if (
            ROOT
            / "docs"
            / "operations"
            / "authorized_mailbox_ingest_task_brief.md"
        ).exists():
            self.assertIn("Keep `EMAIL_AGENT_LLM_PROVIDER=disabled`", report)
            self.assertIn("offline completion does not authorize live operation", report)
            self.assertIn("content-free repository leakage scan", report)
            return

        self.assertIn("运行完整测试和维护扫描", report)
        self.assertIn("用虚构样例手动试用本地调试页面", report)
        self.assertIn("提供 GitHub 远程地址后推送第一阶段项目", report)
        self.assertIn("Tencent Exmail Chrome / Edge 浏览器扩展", report)
        self.assertIn("Outlook Add-in 和 Google Workspace Add-on 保持后续单独确认", report)
        self.assertNotIn("单独确认下一阶段正式邮箱前端路线", report)
        self.assertNotIn("继续扩展 golden 样例覆盖中文邮件、报价请求和历史引用", report)
        self.assertNotIn("补充前端本地调试页面", report)

    def test_shared_repo_utils_are_reported_as_key_files(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        self.assertIn("`scripts/repo_utils.py`", report)
        self.assertIn("`tests/test_repo_utils.py`", report)
        self.assertIn("`tests/test_config.py`", report)
        self.assertIn("`tests/test_run_local_debug.py`", report)
        self.assertIn("`tests/fixtures/sample_emails.json`", report)
        self.assertIn("`tests/test_golden_email_analysis.py`", report)
        self.assertIn("`tests/support.py`", report)
        self.assertIn("`backend/email_agent/server.py`", report)
        self.assertIn("`frontend/local_debug_page/index.html`", report)
        self.assertIn("`scripts/run_local_debug.py`", report)

    def test_local_service_manager_files_are_reported_as_key_files(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        self.assertIn("`scripts/manage_local_service.py`", report)
        self.assertIn("`start_local_service.cmd`", report)
        self.assertIn("`stop_local_service.cmd`", report)
        self.assertIn("`restart_local_service.cmd`", report)
        self.assertIn("`status_local_service.cmd`", report)
        self.assertIn("`tests/test_manage_local_service.py`", report)

    def test_managed_container_checkpoint_is_reported_without_cutover_claim(
        self,
    ) -> None:
        module = load_script_module(
            SCRIPT,
            "generate_project_status_managed_container",
        )
        report = module.build_project_status()

        for marker in (
            "Issue #32 Managed launcher is implemented",
            "exact `email_ai_assistant\\main` placement",
            "`backend/email_agent/managed_runtime.py`",
            "`docs/operations/issue32_managed_container_mode_task_brief.md`",
            "`tests/test_managed_container_mode.py`",
            "no real Project Container migration or operational cutover",
            "Issues #34 through #40 remain separate",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, report)

    def test_browser_extension_files_are_reported_as_key_files(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")
        report = module.build_project_status()

        self.assertIn("`frontend/browser_extension/manifest.json`", report)
        self.assertIn("`frontend/browser_extension/popup.js`", report)
        self.assertIn("`frontend/browser_extension/content/exmail_adapter.js`", report)
        self.assertIn("`frontend/browser_extension/shared/api_client.js`", report)
        self.assertIn(
            "`frontend/browser_extension/shared/manual_attachment_files.js`",
            report,
        )
        self.assertIn(
            "`docs/operations/current_email_grounding_and_attachment_repair_task_brief.md`",
            report,
        )
        self.assertIn(
            "`tests/test_browser_extension_manual_attachment_files.py`",
            report,
        )
        self.assertIn("`docs/operations/tencent_exmail_browser_extension_task_brief.md`", report)
        self.assertIn("`tests/test_browser_extension_manifest.py`", report)
        self.assertIn("`tests/test_browser_extension_static.py`", report)
        self.assertIn("`tests/test_browser_extension_behavior.py`", report)

    def test_current_context_shared_ui_and_admin_files_are_reported_safely(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status_current_context")
        report = module.build_project_status()

        for path in (
            "backend/email_agent/analysis_route_support.py",
            "backend/email_agent/frontend_assets.py",
            "backend/email_agent/model_context_selection.py",
            "backend/email_agent/participant_identity_aliases.py",
            "backend/email_agent/private_provider_output_gate.py",
            "frontend/browser_extension/content/current_message_collector.js",
            "frontend/browser_extension/shared/analysis_components.css",
            "scripts/manage_private_knowledge.py",
        ):
            with self.subTest(path=path):
                self.assertIn(f"`{path}`", report)

        for forbidden in (
            "outputs/email_agent.sqlite3",
            ".pkeval",
            "DEEPSEEK_API_KEY",
            "EMAIL_AGENT_PRIVATE_KNOWLEDGE_SNAPSHOT_PATH=",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, report)

    def test_multimodal_current_email_files_and_live_gate_are_reported(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status_multimodal")
        report = module.build_project_status()

        for path in (
            "frontend/browser_extension/content/exmail_visible_context.js",
            "frontend/browser_extension/content/exmail_visible_resource_classifier.js",
            "backend/email_agent/multimodal_media.py",
            "backend/email_agent/openai_multimodal_client.py",
            "backend/email_agent/analysis_model_routes.py",
            "backend/email_agent/model_grounding.py",
            "backend/email_agent/model_visual_grounding.py",
        ):
            with self.subTest(path=path):
                self.assertIn(f"`{path}`", report)

        self.assertIn("Tasks 1-7", report)
        self.assertIn("60/55/35/10/12/8/5", report)
        self.assertIn(
            "Task 9 semantic accuracy repair is offline complete",
            report,
        )
        self.assertIn(
            "Task 9 forced OpenAI-to-DeepSeek synthetic fallback is complete",
            report,
        )
        self.assertIn("exactly one DeepSeek text-only request", report)
        self.assertIn("DeepSeek SDK retries were zero", report)
        self.assertIn(
            "parsed attachment status does not prove semantic correctness", report
        )
        self.assertNotIn("remaining Task 9 gate is final master integration", report)
        self.assertNotIn("15/13/10/5", report)

    def test_main_writes_requested_output(self) -> None:
        module = load_script_module(SCRIPT, "generate_project_status")

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "project_status_log.md"
            exit_code = module.main(["--output", str(output)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.exists())
            self.assertIn("# Project Status Log", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
