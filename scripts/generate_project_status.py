"""Generate an Agent-readable project progress snapshot.

Run:
    python scripts/generate_project_status.py --output docs/operations/project_status_log.md
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

try:
    from scripts.repo_utils import parse_front_matter_field, read_text
except ModuleNotFoundError:
    from repo_utils import parse_front_matter_field, read_text


ROOT = Path(__file__).resolve().parents[1]

# Key files define the handoff surface for the next Agent.
KEY_FILES = [
    "AGENTS.md",
    "README.md",
    ".env.example",
    "requirements.txt",
    ".gitignore",
    ".github/workflows/agent_guardrails.yml",
    ".github/workflows/cleanup_agent.yml",
    "backend/email_agent/__init__.py",
    "backend/email_agent/analysis_schema.py",
    "backend/email_agent/config.py",
    "backend/email_agent/logging_config.py",
    "backend/email_agent/email_cleaner.py",
    "backend/email_agent/analyzer.py",
    "backend/email_agent/rule_analyzer.py",
    "backend/email_agent/llm_client.py",
    "backend/email_agent/database.py",
    "backend/email_agent/exporter.py",
    "backend/email_agent/api.py",
    "backend/email_agent/server.py",
    "frontend/local_debug_page/index.html",
    "frontend/local_debug_page/app.js",
    "frontend/local_debug_page/styles.css",
    "frontend/browser_extension/manifest.json",
    "frontend/browser_extension/popup.html",
    "frontend/browser_extension/popup.css",
    "frontend/browser_extension/popup.js",
    "frontend/browser_extension/content/exmail_adapter.js",
    "frontend/browser_extension/shared/api_client.js",
    "frontend/browser_extension/shared/render_analysis.js",
    "docs/constraints/tooling_constraints.md",
    "docs/constraints/architecture_constraints.md",
    "docs/constraints/linter_constraints.md",
    "docs/constraints/mechanical_rule_translation.md",
    "docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md",
    "docs/operations/authorized_mailbox_ingest_task_brief.md",
    "docs/operations/project_status_log.md",
    "docs/operations/project_status_log_guide.md",
    "docs/operations/agents_project_status_snippet.md",
    "docs/operations/cleanup_agent.md",
    "docs/operations/cleanup_agent_codex.md",
    "docs/operations/codex_cleanup_task.md",
    "docs/operations/documentation_rules.md",
    "docs/operations/first_version_task_brief.md",
    "docs/operations/tencent_exmail_browser_extension_task_brief.md",
    "docs/superpowers/plans/2026-07-14-authorized-mailbox-ingest-knowledge-deepseek.md",
    "docs/superpowers/plans/2026-07-14-mailbox-vault.md",
    "docs/superpowers/plans/2026-07-14-private-knowledge.md",
    "docs/superpowers/plans/2026-07-14-private-deepseek-evaluation.md",
    "docs/templates/agent_task_brief_template.md",
    "docs/templates/cleanup_task_template.md",
    "scripts/repo_utils.py",
    "scripts/maintenance_scan.py",
    "scripts/generate_project_status.py",
    "scripts/run_local_debug.py",
    "scripts/manage_local_service.py",
    "start_local_service.cmd",
    "stop_local_service.cmd",
    "restart_local_service.cmd",
    "status_local_service.cmd",
    "tests/fixtures/sample_emails.json",
    "tests/test_analysis_schema.py",
    "tests/test_golden_email_analysis.py",
    "tests/test_rule_analyzer.py",
    "tests/test_database.py",
    "tests/test_server.py",
    "tests/test_frontend_local_debug.py",
    "tests/test_repo_utils.py",
    "tests/test_config.py",
    "tests/test_run_local_debug.py",
    "tests/test_manage_local_service.py",
    "tests/support.py",
    "tests/test_architecture_constraints.py",
    "tests/test_static_linter_constraints.py",
    "tests/test_mechanical_rule_constraints.py",
    "tests/test_mailbox_transport_constraints.py",
    "tests/test_maintenance_scan.py",
    "tests/test_generate_project_status.py",
    "tests/test_email_cleaner.py",
    "tests/test_analyzer.py",
    "tests/test_api.py",
    "tests/test_browser_extension_manifest.py",
    "tests/test_browser_extension_static.py",
    "tests/test_browser_extension_behavior.py",
]

DOC_DIRS = [
    "docs/product",
    "docs/knowledge_base",
    "docs/prompts",
    "docs/data",
    "docs/api",
    "docs/security",
    "docs/constraints",
    "docs/conventions",
    "docs/decisions",
    "docs/operations",
    "docs/templates",
]

GUARDRAILS = [
    ("Project entry rules", "AGENTS.md"),
    ("Tooling constraints", "docs/constraints/tooling_constraints.md"),
    ("Architecture constraints", "docs/constraints/architecture_constraints.md"),
    ("Static linter constraints", "docs/constraints/linter_constraints.md"),
    ("Mechanical rule translation", "docs/constraints/mechanical_rule_translation.md"),
    ("CI guardrails", ".github/workflows/agent_guardrails.yml"),
    ("Cleanup automation", "docs/operations/cleanup_agent_codex.md"),
    ("Maintenance scan", "scripts/maintenance_scan.py"),
    ("Agent task brief", "docs/templates/agent_task_brief_template.md"),
    (
        "Authorized mailbox ingest boundary",
        "docs/operations/authorized_mailbox_ingest_task_brief.md",
    ),
]

AUTHORIZED_PRIVATE_INGEST_FILES = {
    "docs/operations/authorized_mailbox_ingest_task_brief.md",
    "docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md",
    "docs/superpowers/plans/2026-07-14-authorized-mailbox-ingest-knowledge-deepseek.md",
    "docs/superpowers/plans/2026-07-14-mailbox-vault.md",
    "docs/superpowers/plans/2026-07-14-private-knowledge.md",
    "docs/superpowers/plans/2026-07-14-private-deepseek-evaluation.md",
}

HARD_BOUNDARIES = [
    "浏览器扩展和正常运行时不接入真实邮箱账号；唯一例外是管理员手动运行的单账户只读导入 CLI。",
    "浏览器扩展和正常运行时不读取真实邮箱数据；管理员 CLI 只处理授权范围并先确认 inventory fingerprint。",
    "不自动发送邮件。",
    "不自动删除邮件。",
    "不自动归档邮件。",
    "浏览器扩展和正常运行时不自动扫描所有邮件；管理员 CLI 没有 schedule、后台轮询或自动模型推理。",
    "不把 OpenAI API key 放入前端。",
    "不新增依赖，除非先更新约束文档并获得确认。",
    "不放宽任何测试、linter 或架构约束。",
]


@dataclass(frozen=True)
class FileStatus:
    path: str
    exists: bool


@dataclass(frozen=True)
class GitStatus:
    branch: str


def run_git_command(args: Sequence[str]) -> str:
    command = ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "not available"
    if result.returncode != 0:
        return "not available"
    return result.stdout.strip() or "not available"


def get_git_status() -> GitStatus:
    branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    return GitStatus(branch=branch)


def collect_file_status(paths: Sequence[str]) -> list[FileStatus]:
    return [FileStatus(path=item, exists=(ROOT / item).exists()) for item in paths]


def count_docs_by_status() -> dict[str, int]:
    counts = {"active": 0, "draft": 0, "deprecated": 0, "missing_front_matter": 0}
    docs = ROOT / "docs"
    if not docs.exists():
        return counts
    for path in docs.rglob("*.md"):
        status = parse_front_matter_field(read_text(path), "status")
        if status in counts:
            counts[status] += 1
        else:
            counts["missing_front_matter"] += 1
    return counts


def infer_stage(files: Sequence[FileStatus]) -> str:
    existing = {item.path for item in files if item.exists}
    if AUTHORIZED_PRIVATE_INGEST_FILES.issubset(existing):
        return "authorized_private_ingest_build"
    local_eval_files = {
        "tests/fixtures/sample_emails.json",
        "tests/test_golden_email_analysis.py",
    }
    if local_eval_files.issubset(existing):
        return "local_eval_mvp"
    first_version_files = {
        "backend/email_agent/api.py",
        "backend/email_agent/server.py",
        "frontend/local_debug_page/index.html",
        "frontend/local_debug_page/app.js",
        "scripts/run_local_debug.py",
        "tests/test_server.py",
        "tests/test_frontend_local_debug.py",
    }
    if first_version_files.issubset(existing):
        return "first_version_local_debug"
    if "backend/email_agent/api.py" in existing:
        return "backend_mvp"
    if "tests/test_generate_project_status.py" in existing and "scripts/maintenance_scan.py" in existing:
        return "agent_handoff_guardrails"
    if "docs/constraints/architecture_constraints.md" in existing:
        return "guardrails_setup"
    if "AGENTS.md" in existing:
        return "project_planning"
    return "not_initialized"


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def render_file_table(files: Sequence[FileStatus]) -> str:
    lines = ["| File | Exists |", "|---|---|"]
    lines.extend(f"| `{item.path}` | {format_bool(item.exists)} |" for item in files)
    return "\n".join(lines)


def render_doc_status(counts: dict[str, int]) -> str:
    lines = ["| Status | Count |", "|---|---:|"]
    for key in ("active", "draft", "deprecated", "missing_front_matter"):
        lines.append(f"| {key} | {counts.get(key, 0)} |")
    return "\n".join(lines)


def render_guardrails() -> str:
    rows = [FileStatus(path=f"{name}: {path}", exists=(ROOT / path).exists()) for name, path in GUARDRAILS]
    return render_file_table(rows)


def render_boundaries() -> str:
    return "\n".join(f"- {item}" for item in HARD_BOUNDARIES)


def render_next_steps(stage: str) -> str:
    if stage == "authorized_private_ingest_build":
        steps = [
            "Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` during implementation and automated verification.",
            "Implement later plan tasks with synthetic fakes and injected probes only.",
            "Do not connect to a mailbox or run DeepSeek without a separate operator authorization after offline gates pass.",
            "Preserve the click-only current-message browser extension and normal runtime boundary.",
        ]
    elif stage in {"agent_handoff_guardrails", "guardrails_setup"}:
        steps = [
            "创建 `backend/email_agent/` 最小骨架。",
            "先实现邮件清洗、AI JSON 校验和本地 API 的测试。",
            "用脱敏样例验证“点击按钮分析当前邮件”流程。",
        ]
    elif stage == "local_eval_mvp":
        steps = [
            "运行完整测试和维护扫描。",
            "用虚构样例手动试用本地调试页面。",
            "提供 GitHub 远程地址后推送第一阶段项目。",
            "继续验证 Tencent Exmail Chrome / Edge 浏览器扩展原型；Outlook Add-in 和 Google Workspace Add-on 保持后续单独确认。",
        ]
    elif stage == "first_version_local_debug":
        steps = [
            "运行完整测试和维护扫描。",
            "用虚构样例手动试用本地调试页面。",
            "后续单独确认正式前端路线：Outlook Add-in、Google Workspace Add-on 或浏览器扩展。",
        ]
    elif stage == "backend_mvp":
        steps = ["运行完整测试。", "补充前端本地调试页面。", "更新 API 和数据 schema 文档。"]
    else:
        steps = ["创建 AGENTS.md。", "创建 docs/ 目录。", "写入项目边界和技术栈约束。"]
    return "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))


def build_project_status() -> str:
    git = get_git_status()
    files = collect_file_status(KEY_FILES)
    doc_dirs = collect_file_status(DOC_DIRS)
    doc_counts = count_docs_by_status()
    stage = infer_stage(files)
    today = date.today().isoformat()

    return f"""---
last_update: {today}
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Project Status Log

> Agent-readable project progress snapshot. This is not a normal development log.
> Agent should read `AGENTS.md` and this file before starting non-trivial work.

## Snapshot

| Field | Value |
|---|---|
| Generated on | {today} |
| Current stage | {stage} |
| Git branch | {git.branch} |
| Git HEAD reference | Run `git rev-parse --short HEAD` in this workspace |
| Working tree status | Run `git status --short --ignored` in this workspace |

## Project Summary

本项目是企业邮箱中的 AI 辅助窗口。正常产品只做“用户点击按钮后分析当前打开邮件”，不做全邮箱扫描、不自动发送邮件、不删除邮件或归档邮件。

Separately authorized exception: the `administrator-only CLI` may import one authorized account within a rolling 24-month window after explicit inventory fingerprint confirmation. The browser extension and normal runtime remain click-only and cannot scan a mailbox. The exception has no schedule, browser hook, normal-backend route, or automatic model call.

## Guardrails Established

{render_guardrails()}

## Key File Status

{render_file_table(files)}

## docs Directory Status

{render_file_table(doc_dirs)}

## docs Metadata Summary

{render_doc_status(doc_counts)}

## Recommended Next Steps

{render_next_steps(stage)}

## Do Not Touch Boundaries

{render_boundaries()}

## Notes for Agent

- 先读 `AGENTS.md`，再读本文件。
- 涉及工具、架构、linter、机械规则、安全边界时，继续读 `docs/constraints/`。
- 涉及任务执行前规划时，填写 `docs/templates/agent_task_brief_template.md`。
- 不要把项目进度流水账写入 `AGENTS.md`。
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "operations" / "project_status_log.md")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_project_status(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
