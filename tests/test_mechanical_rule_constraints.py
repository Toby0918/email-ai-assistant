"""Mechanical rule constraints for repeated code review issues.

Run:
    python -m unittest discover -s tests -p "test_mechanical_rule_constraints.py"
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from scripts.repo_utils import iter_python_files, read_text
from tests.support import failure_message


ROOT = Path(__file__).resolve().parents[1]

MAX_BACKEND_PY_FILE_LINES = 300
MAX_FUNCTION_LINES = 50


class FunctionLengthVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        # Store enough context to turn line-length failures into actionable reports.
        self.path = path
        self.violations: list[tuple[str, int, int, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_node(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return self._visit_function_node(node)

    def _visit_function_node(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        end_lineno = getattr(node, "end_lineno", None)
        if end_lineno is None:
            return
        length = end_lineno - node.lineno + 1
        if length > MAX_FUNCTION_LINES:
            self.violations.append((node.name, node.lineno, end_lineno, length))


class MechanicalRuleConstraintTests(unittest.TestCase):
    def test_backend_python_files_do_not_exceed_300_lines(self) -> None:
        backend = ROOT / "backend"
        if not backend.exists():
            self.skipTest("backend/ does not exist yet")

        for path in iter_python_files(backend):
            line_count = len(read_text(path).splitlines())
            with self.subTest(path=path):
                self.assertLessEqual(
                    line_count,
                    MAX_BACKEND_PY_FILE_LINES,
                    failure_message(
                        f"{path} 有 {line_count} 行，超过 {MAX_BACKEND_PY_FILE_LINES} 行限制。",
                        "拆分模块；把配置、清洗、分析、数据库、导出和 API 逻辑分离。",
                        "docs/constraints/mechanical_rule_translation.md",
                    ),
                )

    def test_backend_functions_do_not_exceed_50_lines(self) -> None:
        backend = ROOT / "backend"
        if not backend.exists():
            self.skipTest("backend/ does not exist yet")

        for path in iter_python_files(backend):
            try:
                tree = ast.parse(read_text(path))
            except SyntaxError as exc:
                self.fail(
                    failure_message(
                        f"{path} 存在 Python 语法错误：{exc}",
                        "先修复语法错误，再运行机械规则检查。",
                        "docs/constraints/mechanical_rule_translation.md",
                    )
                )

            visitor = FunctionLengthVisitor(path)
            visitor.visit(tree)

            for name, start, end, length in visitor.violations:
                with self.subTest(path=path, function=name):
                    self.fail(
                        failure_message(
                            f"{path} 中函数 {name} 第 {start}-{end} 行，共 {length} 行，超过 {MAX_FUNCTION_LINES} 行限制。",
                            "拆分函数；把输入校验、业务处理、外部调用和响应构造分离。",
                            "docs/constraints/mechanical_rule_translation.md",
                        )
                    )

    def test_review_rule_register_exists(self) -> None:
        path = ROOT / "docs" / "templates" / "code_review_rule_register.md"
        self.assertTrue(
            path.exists(),
            failure_message(
                "缺少 code review 重复规则登记表。",
                "创建 docs/templates/code_review_rule_register.md，用于记录超过 3 次的 review 规则。",
                "docs/constraints/mechanical_rule_translation.md",
            ),
        )

    def test_ci_workflow_exists(self) -> None:
        path = ROOT / ".github" / "workflows" / "agent_guardrails.yml"
        self.assertTrue(
            path.exists(),
            failure_message(
                "缺少 Agent Guardrails CI workflow。",
                "创建 .github/workflows/agent_guardrails.yml，并运行架构、静态 linter、机械规则和单元测试。",
                "docs/constraints/ci_guardrails.md",
            ),
        )

    def test_ci_runs_maintenance_scan(self) -> None:
        path = ROOT / ".github" / "workflows" / "agent_guardrails.yml"
        if not path.exists():
            self.skipTest("agent_guardrails.yml does not exist yet")

        text = path.read_text(encoding="utf-8", errors="ignore")
        self.assertIn(
            "scripts/maintenance_scan.py",
            text,
            failure_message(
                "CI 没有直接运行维护扫描脚本。",
                "在 Agent Guardrails workflow 中加入 python scripts/maintenance_scan.py。",
                "docs/constraints/ci_guardrails.md",
            ),
        )

    def test_agents_requires_status_log_update_after_non_trivial_tasks(self) -> None:
        path = ROOT / "AGENTS.md"
        text = path.read_text(encoding="utf-8", errors="ignore")
        self.assertIn(
            "scripts/generate_project_status.py",
            text,
            failure_message(
                "AGENTS.md 没有要求任务完成后更新项目状态日志。",
                "在开发规则中加入完成后运行 generate_project_status.py 的收尾要求。",
                "docs/operations/project_status_log_guide.md",
            ),
        )

    def test_project_structure_reflects_landed_first_phase_code(self) -> None:
        first_phase_files = [
            ROOT / "backend" / "email_agent" / "server.py",
            ROOT / "frontend" / "local_debug_page" / "index.html",
            ROOT / "scripts" / "manage_local_service.py",
            ROOT / "tests" / "test_golden_email_analysis.py",
        ]
        if not all(path.exists() for path in first_phase_files):
            self.skipTest("first-phase implementation files do not all exist yet")

        path = ROOT / "docs" / "operations" / "project_structure.md"
        text = path.read_text(encoding="utf-8", errors="ignore")

        self.assertNotIn(
            "当前实现代码尚未落地",
            text,
            failure_message(
                "项目结构文档仍声称实现代码尚未落地，但第一阶段实现文件已经存在。",
                "更新 docs/operations/project_structure.md，使它描述当前已落地的 first-phase 结构。",
                "docs/operations/project_structure.md",
            ),
        )
        self.assertIn("frontend/local_debug_page", text)
        self.assertIn("scripts/manage_local_service.py", text)

    def test_issue57_mechanical_and_ci_rules_are_documented(self) -> None:
        mechanical = (
            ROOT / "docs" / "constraints" / "mechanical_rule_translation.md"
        ).read_text(encoding="utf-8")
        ci = (ROOT / "docs" / "constraints" / "ci_guardrails.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Issue #57 managed publication rules", mechanical)
        self.assertIn("partial target remains", mechanical)
        self.assertIn("Post-authorization source drift", mechanical)
        self.assertIn("Wheelhouse enumeration stops", mechanical)
        self.assertIn("superscript `COM¹/²/³`", mechanical)
        self.assertIn("ZIP_STORED", mechanical)
        self.assertIn("`Lib/encodings/aliases/__init__.py`", mechanical)
        self.assertIn("Issue #57 managed publication gate", ci)
        self.assertIn("complete in-sandbox CPython distribution", ci)
        self.assertIn("`managed-startup.zip`", ci)
        self.assertIn("pre-script `encodings.aliases`/`codecs` injection", ci)
        self.assertIn("Linux", ci)
        self.assertIn("Issues #58/#59", ci)

    def test_issue110_mechanical_rules_are_documented(self) -> None:
        mechanical = read_text(
            ROOT / "docs" / "constraints" / "mechanical_rule_translation.md"
        )
        for marker in (
            "Issue #110 publication and validation rules",
            "exactly nine\n   modules",
            "numeric job id equals the hosted record",
            "generated-status normalized equivalence",
            "nineteen unique classifications exactly",
            "only `prepare` and `confirm`",
            "duplicate/extra/missing keys",
            "lone surrogates",
            "hosted-check ordering",
            "Real current state\n   with no ruleset must fail",
            "one-use acknowledgement",
            "wall/monotonic 300-second bounds",
            "create-only two-file publication",
            "final stable parent/child/DACL/oplock observation",
            "exact-target no-replace rename",
            "strictly after that linearization",
            "subsequent incident",
            "does not provide atomic arbitrary-sibling exclusion",
            "Git-common DACL mutation, kernel filter, or volume lock",
            "only-new-file inventory",
            "recursive legacy-surface rejection",
            "Do not execute the live verifier",
            "full discovery, maintenance scan",
            "callable leakage scan",
            "CI workflows remain byte-unchanged",
            "cannot approve Issue #38",
            "authorize or execute Issue #39",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, mechanical)

    def test_issue110_amendments_04_through_07_are_recorded(self) -> None:
        brief = read_text(
            ROOT / "docs" / "operations" / "r2_solo_maintainer_closure_task_brief.md"
        )
        for marker in (
            "Amendment 04",
            "tests/test_r2_rollback_recovery_v2_crash_matrix.py",
            "Amendment 05",
            "docs/templates/agent_task_brief_template.md",
            "Amendment 06",
            "5224508400",
            "8d23bc6aa9f0ddb7ef1f233c5b848db17c8c3c7a8c5824d714af73861cc313c7",
            "Amendment 07",
            "tests/test_r2_rollback_recovery_v2_architecture.py",
            "5224816599",
            "e0b9c955f6bf7909f8e099000ad0744574024d8b0d2b0b29fd08bad3f5c4320b",
            "182 paths (`A20/M123/D39`)",
            "final stable parent/child/DACL/oplock observation",
            "exact-target no-replace rename",
            "strictly after that linearization",
            "subsequent incident",
            "no atomic arbitrary-sibling exclusion",
            "Git-common DACL mutation, kernel filter, or volume lock",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, brief)


if __name__ == "__main__":
    unittest.main()
