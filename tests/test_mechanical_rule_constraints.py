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


if __name__ == "__main__":
    unittest.main()
