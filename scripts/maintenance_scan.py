"""Repository maintenance scanner for the email AI assistant project.

This script is read-only. It scans repository hygiene issues and prints a Markdown report.

Run:
    python scripts/maintenance_scan.py
    python scripts/maintenance_scan.py --output outputs/cleanup_report.md
    python scripts/maintenance_scan.py --fail-on-high
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

# Support both unittest imports and direct `python scripts/maintenance_scan.py`.
try:
    from scripts.repo_utils import (
        FORBIDDEN_REPO_FILE_NAMES,
        FORBIDDEN_REPO_SUFFIXES,
        TEXT_SUFFIXES,
        has_required_front_matter,
        is_ignored_by_gitignore,
        iter_project_files,
        iter_python_files,
        load_gitignore_patterns,
        parse_front_matter,
        read_text,
    )
    from scripts.repository_leakage_scan import (
        LeakageFinding,
        scan_repository as scan_repository_for_leakage,
    )
except ModuleNotFoundError:
    from repo_utils import (
        FORBIDDEN_REPO_FILE_NAMES,
        FORBIDDEN_REPO_SUFFIXES,
        TEXT_SUFFIXES,
        has_required_front_matter,
        is_ignored_by_gitignore,
        iter_project_files,
        iter_python_files,
        load_gitignore_patterns,
        parse_front_matter,
        read_text,
    )
    from repository_leakage_scan import (
        LeakageFinding,
        scan_repository as scan_repository_for_leakage,
    )


ROOT = Path(__file__).resolve().parents[1]

MAX_BACKEND_PY_FILE_LINES = 300
MAX_FUNCTION_LINES = 50
STALE_DRAFT_DAYS = 30

TODO_PATTERN = re.compile(r"\b(TODO|FIXME)\b", re.IGNORECASE)
TODO_REFERENCE_FILES = {
    "scripts/maintenance_scan.py",
    "docs/operations/cleanup_agent.md",
    "docs/operations/codex_cleanup_task.md",
    "docs/templates/cleanup_task_template.md",
    "docs/constraints/mechanical_rule_translation.md",
}


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    path: str
    message: str
    fix: str
    doc: str


GITIGNORE_PATTERNS = load_gitignore_patterns(ROOT)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def scan_forbidden_files() -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_project_files(ROOT):
        name = path.name.lower()
        suffix = path.suffix.lower()
        if (
            name in FORBIDDEN_REPO_FILE_NAMES or suffix in FORBIDDEN_REPO_SUFFIXES
        ) and not is_ignored_by_gitignore(path, ROOT, GITIGNORE_PATTERNS):
            findings.append(Finding(
                "high", "security_hygiene", rel(path),
                "禁止提交未忽略的本地配置、数据库或敏感运行文件。",
                "删除该文件或加入 .gitignore；如需示例配置，使用 .env.example。",
                "docs/security/email_data_handling.md",
            ))
    return findings


def scan_backend_file_lengths() -> list[Finding]:
    findings: list[Finding] = []
    backend = ROOT / "backend"
    if not backend.exists():
        return findings

    for path in iter_python_files(backend):
        line_count = len(read_text(path).splitlines())
        if line_count > MAX_BACKEND_PY_FILE_LINES:
            findings.append(Finding(
                "medium", "oversized_file", rel(path),
                f"Python 文件 {line_count} 行，超过 {MAX_BACKEND_PY_FILE_LINES} 行限制。",
                "拆分模块；保持单文件职责单一。",
                "docs/constraints/mechanical_rule_translation.md",
            ))
    return findings


def scan_backend_function_lengths() -> list[Finding]:
    findings: list[Finding] = []
    backend = ROOT / "backend"
    if not backend.exists():
        return findings

    for path in iter_python_files(backend):
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError as exc:
            findings.append(Finding(
                "high", "linter_failure", rel(path),
                f"Python 语法错误：{exc}",
                "先修复语法错误，再运行清理扫描。",
                "docs/constraints/mechanical_rule_translation.md",
            ))
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_lineno = getattr(node, "end_lineno", None)
                if end_lineno is None:
                    continue
                length = end_lineno - node.lineno + 1
                if length > MAX_FUNCTION_LINES:
                    findings.append(Finding(
                        "medium", "oversized_function", rel(path),
                        f"函数 {node.name} 第 {node.lineno}-{end_lineno} 行，共 {length} 行，超过 {MAX_FUNCTION_LINES} 行限制。",
                        "拆分函数；分离输入校验、业务逻辑、外部调用和响应构造。",
                        "docs/constraints/mechanical_rule_translation.md",
                    ))
    return findings


def scan_todo_fixme() -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_project_files(ROOT):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if rel(path) in TODO_REFERENCE_FILES:
            continue
        for index, line in enumerate(read_text(path).splitlines(), start=1):
            if TODO_PATTERN.search(line):
                findings.append(Finding(
                    "low", "todo_fixme", f"{rel(path)}:{index}",
                    "发现 TODO/FIXME 标记。",
                    "判断是否需要创建清理任务；超过 30 天未处理的应进入 cleanup PR。",
                    "docs/operations/cleanup_agent.md",
                ))
    return findings


def scan_docs_metadata_and_staleness() -> list[Finding]:
    findings: list[Finding] = []
    docs = ROOT / "docs"
    if not docs.exists():
        return findings

    today = date.today()
    for path in docs.rglob("*.md"):
        text = read_text(path)
        if not has_required_front_matter(text):
            findings.append(Finding(
                "medium", "other", rel(path),
                "docs Markdown 缺少标准 YAML front matter。",
                "补充 last_update、status、owner、review_cycle、source_type。",
                "docs/operations/documentation_rules.md",
            ))
            continue

        meta = parse_front_matter(text)
        if meta.get("status") != "draft":
            continue

        last_update = meta.get("last_update")
        if not last_update:
            continue

        try:
            updated = datetime.strptime(last_update, "%Y-%m-%d").date()
        except ValueError:
            findings.append(Finding(
                "medium", "other", rel(path),
                "last_update 不是 YYYY-MM-DD 格式。",
                "修正日期格式。",
                "docs/operations/documentation_rules.md",
            ))
            continue

        age = (today - updated).days
        if age > STALE_DRAFT_DAYS:
            findings.append(Finding(
                "low", "stale_doc", rel(path),
                f"draft 文档已 {age} 天未更新。",
                "确认是否转为 active、更新内容，或标记为 deprecated。",
                "docs/operations/cleanup_agent.md",
            ))
    return findings


def scan_repository_leakage(
    *, scan=scan_repository_for_leakage,
) -> list[Finding]:
    """Convert aggregate leakage codes without exposing source content or paths."""
    findings: list[Finding] = []
    for item in scan():
        findings.append(Finding(
            "high",
            "repository_leakage",
            f"[{item.scope}]",
            f"code={item.code} count={item.count}",
            "Stop release and inspect the named scope locally without copying content.",
            "docs/operations/testing_checklist.md",
        ))
    return findings


def collect_findings() -> list[Finding]:
    # Scans are read-only: collect independent findings, then render a report.
    findings: list[Finding] = []
    findings.extend(scan_forbidden_files())
    findings.extend(scan_backend_file_lengths())
    findings.extend(scan_backend_function_lengths())
    findings.extend(scan_todo_fixme())
    findings.extend(scan_docs_metadata_and_staleness())
    findings.extend(scan_repository_leakage())
    return findings


def render_report(findings: list[Finding]) -> str:
    lines = ["# Cleanup Agent Report", "", f"Generated on: {date.today().isoformat()}", ""]
    if not findings:
        lines.extend(["No cleanup findings detected.", ""])
        return "\n".join(lines)

    lines.extend(["| Severity | Category | File | Problem | Suggested Fix | Reference |", "|---|---|---|---|---|---|"])
    for item in findings:
        lines.append(
            f"| {item.severity} | {item.category} | `{item.path}` | {item.message} | {item.fix} | `{item.doc}` |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fail-on-high", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings = collect_findings()
    report = render_report(findings)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report)

    if args.fail_on_high and any(item.severity == "high" for item in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
