"""Custom static linter constraints for the email AI assistant project.

Run:
    python -m unittest discover -s tests -p "test_static_linter_constraints.py"
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from scripts import repo_utils
from scripts.repo_utils import (
    FORBIDDEN_REPO_FILE_NAMES,
    FORBIDDEN_REPO_SUFFIXES,
    has_required_front_matter,
    is_ignored_by_gitignore,
    is_text_file,
    iter_project_files,
    load_gitignore_patterns,
    parse_front_matter,
    read_text,
)
from tests.support import failure_message


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_PRINT_FILES: set[str] = set()

FORBIDDEN_FRONTEND_PATTERNS = {
    "OpenAI API key in frontend": r"OPENAI_API_KEY",
    "OpenAI secret key literal in frontend": r"\bsk-[A-Za-z0-9_-]{10,}",
    "OpenAI API host in frontend": r"api\.openai\.com",
    "OpenAI responses endpoint in frontend": r"/v1/responses",
    "OpenAI chat endpoint in frontend": r"/v1/chat/completions",
    "OpenAI JS client in frontend": r"new\s+OpenAI\s*\(",
    "OpenAI package import in frontend": r"from\s+['\"]openai['\"]|require\(['\"]openai['\"]\)",
    "Ollama host in frontend": r"127\.0\.0\.1:11434|localhost:11434",
    "Ollama generate endpoint in frontend": r"/api/generate",
    "Ollama chat endpoint in frontend": r"/api/chat",
    "Ollama marker in frontend": r"\bollama\b",
    "local Qwen model marker in frontend": r"\bqwen(?:3\.6)?\b",
    "local Gemma model marker in frontend": r"\bgemma(?:4)?\b",
    "browser OAuth flow in frontend": r"chrome\.identity|client_secret|refresh_token|access_token",
    "environment access in frontend": r"process\.env|\.env",
    "SQLite access in frontend": r"\bsqlite3?\b",
}

FORBIDDEN_EMAIL_ACTION_PATTERNS = {
    "automatic send mail action": r"\bsendMail\b",
    "Gmail send action": r"gmail\.users\.messages\.send",
    "archive action": r"archiveMessage|archive\s*\(",
    "delete action": r"deleteMessage|trashMessage|messages\.trash",
    "modify or move action": r"gmail\.users\.messages\.modify|messages\.modify|moveMessage|move\s*\(",
    "forward action": r"forwardMessage|forward\s*\(",
}

SECRET_PATTERNS = {
    "OpenAI-like secret key": r"\bsk-[A-Za-z0-9_-]{10,}",
    "Google OAuth-like token": r"ya29\.[A-Za-z0-9_-]+",
    "hardcoded password assignment": r"password\s*=\s*['\"][^'\"]+['\"]",
}

GITIGNORE_PATTERNS = load_gitignore_patterns(ROOT)
ALLOWED_DOC_STATUSES = {"draft", "active", "deprecated"}


class PrintCallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        # Record line numbers so failures point to the exact mechanical violation.
        self.print_lines: list[int] = []
        self.traceback_print_exc_lines: list[int] = []
        self.bare_except_lines: list[int] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            self.print_lines.append(node.lineno)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "print_exc"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "traceback"
        ):
            self.traceback_print_exc_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.bare_except_lines.append(node.lineno)
        self.generic_visit(node)


class StaticLinterConstraintTests(unittest.TestCase):
    def test_deepseek_reuses_pinned_openai_sdk_without_remote_base_url_configuration(self) -> None:
        requirements = read_text(ROOT / "requirements.txt")
        tooling = read_text(ROOT / "docs" / "constraints" / "tooling_constraints.md")
        deployment = read_text(ROOT / "docs" / "operations" / "deployment_notes.md")

        self.assertIn("openai==2.45.0", requirements)
        self.assertNotRegex(requirements, r"(?im)^\s*deepseek(?:[-_.][A-Za-z0-9]+)*\s*[=<>~!]")
        for path, guidance in (
            ("docs/constraints/tooling_constraints.md", tooling),
            ("docs/operations/deployment_notes.md", deployment),
        ):
            with self.subTest(path=path):
                self.assertIn("OpenAI-compatible", guidance)
                self.assertIn("arbitrary remote base URL", guidance)
                self.assertIn("third-party DeepSeek SDK", guidance)

    def test_active_phase_two_design_keeps_provider_disabled_by_default(self) -> None:
        design = read_text(
            ROOT
            / "docs"
            / "superpowers"
            / "specs"
            / "2026-07-09-phase-two-attachment-thread-analysis-design.md"
        )

        self.assertIn("defaults to `EMAIL_AGENT_LLM_PROVIDER=disabled`", design)
        self.assertIn("only the default model name when Ollama is explicitly enabled", design)
        self.assertNotIn("defaults to `EMAIL_AGENT_LLM_PROVIDER=ollama`", design)

    def test_pinned_dependency_versions_are_consistent_across_active_guidance(self) -> None:
        expected_versions = {
            "openai": "2.45.0",
            "pypdf": "6.14.2",
            "python-docx": "1.2.0",
            "Pillow": "12.3.0",
            "pytesseract": "0.3.13",
        }
        requirements = read_text(ROOT / "requirements.txt")
        repo_utils.parse_pinned_dependency_versions(requirements)
        guidance_files = [
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / "docs" / "constraints" / "tooling_constraints.md",
            ROOT / "docs" / "operations" / "phase_two_attachment_thread_task_brief.md",
            ROOT / "docs" / "superpowers" / "plans" / "2026-07-09-phase-two-attachment-thread-analysis.md",
        ]

        for package, version in expected_versions.items():
            pin = f"{package}=={version}"
            with self.subTest(package=package, path="requirements.txt"):
                self.assertIn(pin, requirements)
            for path in guidance_files:
                with self.subTest(package=package, path=path):
                    marker = (
                        rf"{re.escape(package)}"
                        rf"(?:==|\s*\|\s*|\s+){re.escape(version)}"
                    )
                    self.assertRegex(read_text(path), marker)

    def test_no_forbidden_repository_files_are_unignored(self) -> None:
        for path in iter_project_files(ROOT):
            name = path.name.lower()
            suffix = path.suffix.lower()
            if name in FORBIDDEN_REPO_FILE_NAMES or suffix in FORBIDDEN_REPO_SUFFIXES:
                with self.subTest(path=path):
                    self.assertTrue(
                        is_ignored_by_gitignore(path, ROOT, GITIGNORE_PATTERNS),
                        failure_message(
                            f"{path} 是敏感或本地运行文件，且未被 .gitignore 忽略。",
                            "删除该文件或加入 .gitignore；示例配置只放 .env.example。",
                            "docs/security/api_key_rules.md",
                        ),
                    )
            with self.subTest(path=path):
                self.assertFalse(
                    name.endswith(".token") or name.endswith(".secret"),
                    failure_message(
                        f"{path} 看起来是 token 或 secret 文件。",
                        "移出版本库，并改用环境变量或本地受控配置。",
                        "docs/security/api_key_rules.md",
                    ),
                )

    def test_no_print_traceback_or_bare_except_in_backend_business_code(self) -> None:
        backend = ROOT / "backend"
        if not backend.exists():
            self.skipTest("backend/ does not exist yet")

        for path in backend.rglob("*.py"):
            if path.name in ALLOWED_PRINT_FILES:
                continue
            try:
                tree = ast.parse(read_text(path))
            except SyntaxError as exc:
                self.fail(
                    failure_message(
                        f"{path} 存在 Python 语法错误：{exc}",
                        "先修复语法错误，再运行静态约束测试。",
                        "docs/constraints/linter_constraints.md",
                    )
                )

            visitor = PrintCallVisitor()
            visitor.visit(tree)
            self.assertFalse(
                visitor.print_lines,
                failure_message(
                    f"{path} 在行 {visitor.print_lines} 使用了裸 print()。",
                    "改用 logging.getLogger(__name__)，并避免输出真实邮件正文或密钥。",
                    "docs/conventions/logging.md",
                ),
            )
            self.assertFalse(
                visitor.traceback_print_exc_lines,
                failure_message(
                    f"{path} 在行 {visitor.traceback_print_exc_lines} 使用了 traceback.print_exc()。",
                    "改用 logger.exception(...) 并保留必要上下文。",
                    "docs/conventions/logging.md",
                ),
            )
            self.assertFalse(
                visitor.bare_except_lines,
                failure_message(
                    f"{path} 在行 {visitor.bare_except_lines} 使用了裸 except。",
                    "捕获明确异常类型，例如 except ValueError as exc。",
                    "docs/conventions/logging.md",
                ),
            )

    def test_frontend_has_no_openai_secret_or_direct_api_call(self) -> None:
        frontend = ROOT / "frontend"
        if not frontend.exists():
            self.skipTest("frontend/ does not exist yet")

        for path in frontend.rglob("*"):
            if not path.is_file() or not is_text_file(path):
                continue
            text = read_text(path)
            for rule_name, pattern in FORBIDDEN_FRONTEND_PATTERNS.items():
                with self.subTest(rule=rule_name, path=path):
                    self.assertIsNone(
                        re.search(pattern, text, re.IGNORECASE),
                        failure_message(
                            f"{path} 触发前端禁用规则：{rule_name}。",
                            "前端只能调用本地后端 API；OpenAI key 和 OpenAI 调用必须留在后端 llm_client.py。",
                            "docs/constraints/linter_constraints.md",
                        ),
                    )

    def test_frontend_has_no_dangerous_email_action(self) -> None:
        frontend = ROOT / "frontend"
        if not frontend.exists():
            self.skipTest("frontend/ does not exist yet")

        for path in frontend.rglob("*"):
            if not path.is_file() or not is_text_file(path):
                continue
            text = read_text(path)
            for rule_name, pattern in FORBIDDEN_EMAIL_ACTION_PATTERNS.items():
                with self.subTest(rule=rule_name, path=path):
                    self.assertIsNone(
                        re.search(pattern, text, re.IGNORECASE),
                        failure_message(
                            f"{path} 触发高风险邮箱动作规则：{rule_name}。",
                            "第一阶段禁止自动发送、删除、归档邮件；只允许用户点击后分析当前邮件。",
                            "docs/product/feature_scope.md",
                        ),
                    )

    def test_no_raw_secret_literals_in_text_files(self) -> None:
        documented_pattern_files = {
            "linter_constraints.md",
            "test_static_linter_constraints.py",
            "test_architecture_constraints.py",
            "api_key_rules.md",
        }
        for path in iter_project_files(ROOT):
            if not is_text_file(path):
                continue
            if path.name in documented_pattern_files:
                continue
            text = read_text(path)

            for rule_name, pattern in SECRET_PATTERNS.items():
                with self.subTest(rule=rule_name, path=path):
                    matches = list(re.finditer(pattern, text, re.IGNORECASE))
                    if rule_name == "OpenAI-like secret key":
                        matches = [
                            match for match in matches
                            if not match.group(0).lower().startswith("sk-your-")
                        ]
                    self.assertFalse(
                        matches,
                        failure_message(
                            f"{path} 出现疑似敏感值：{rule_name}。",
                            "删除真实密钥；测试中使用 your_api_key_here 这类明显假值。",
                            "docs/security/api_key_rules.md",
                        ),
                    )

    def test_docs_markdown_files_have_front_matter(self) -> None:
        docs = ROOT / "docs"
        if not docs.exists():
            self.skipTest("docs/ does not exist yet")

        for path in docs.rglob("*.md"):
            text = read_text(path)
            with self.subTest(path=path):
                self.assertTrue(
                    has_required_front_matter(text),
                    failure_message(
                        f"{path} 缺少标准 YAML front matter。",
                        "在文件顶部补充 last_update、status、owner、review_cycle、source_type。",
                        "docs/operations/documentation_rules.md",
                    ),
                )

    def test_docs_markdown_front_matter_status_uses_allowed_values(self) -> None:
        docs = ROOT / "docs"
        if not docs.exists():
            self.skipTest("docs/ does not exist yet")

        for path in docs.rglob("*.md"):
            text = read_text(path)
            if not has_required_front_matter(text):
                continue
            status = parse_front_matter(text).get("status")
            with self.subTest(path=path):
                self.assertIn(
                    status,
                    ALLOWED_DOC_STATUSES,
                    failure_message(
                        f"{path} 使用了非法 docs front matter status: {status}。",
                        "改用 draft、active 或 deprecated；任务执行状态应写在正文 Current Status 中。",
                        "docs/operations/documentation_rules.md",
                    ),
                )


if __name__ == "__main__":
    unittest.main()
