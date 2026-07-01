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
            self.assertIn("| Current stage | local_eval_mvp |", report)

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

        self.assertIn("运行完整测试和维护扫描", report)
        self.assertIn("用虚构样例手动试用本地调试页面", report)
        self.assertIn("提供 GitHub 远程地址后推送第一阶段项目", report)
        self.assertIn("单独确认下一阶段正式邮箱前端路线", report)
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
