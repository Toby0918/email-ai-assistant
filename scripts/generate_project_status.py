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
    "backend/email_agent/analysis_budget.py",
    "backend/email_agent/analysis_diagnostics.py",
    "backend/email_agent/analysis_model_routes.py",
    "backend/email_agent/analysis_provider_policy.py",
    "backend/email_agent/analysis_route_support.py",
    "backend/email_agent/attachment_media_context.py",
    "backend/email_agent/attachment_parser.py",
    "backend/email_agent/attachment_safety.py",
    "backend/email_agent/attachment_storage.py",
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
    "backend/email_agent/frontend_assets.py",
    "backend/email_agent/image_media_safety.py",
    "backend/email_agent/llm_errors.py",
    "backend/email_agent/model_context_selection.py",
    "backend/email_agent/model_cross_language_grounding.py",
    "backend/email_agent/model_grounding.py",
    "backend/email_agent/model_multimodal_claim_safety.py",
    "backend/email_agent/model_request.py",
    "backend/email_agent/model_result_safety.py",
    "backend/email_agent/model_source_grounding.py",
    "backend/email_agent/model_visual_grounding.py",
    "backend/email_agent/multimodal_media.py",
    "backend/email_agent/office_embedded_media.py",
    "backend/email_agent/openai_multimodal_client.py",
    "backend/email_agent/participant_identity_aliases.py",
    "backend/email_agent/pdf_media_safety.py",
    "backend/email_agent/private_context_gate.py",
    "backend/email_agent/private_provider_output_gate.py",
    "backend/email_agent/prompt_context.py",
    "backend/email_agent/thread_prompt_projection.py",
    "frontend/local_debug_page/index.html",
    "frontend/local_debug_page/app.js",
    "frontend/local_debug_page/styles.css",
    "frontend/browser_extension/manifest.json",
    "frontend/browser_extension/popup.html",
    "frontend/browser_extension/popup.css",
    "frontend/browser_extension/popup.js",
    "frontend/browser_extension/content/current_message_collector.js",
    "frontend/browser_extension/content/exmail_adapter.js",
    "frontend/browser_extension/content/exmail_visible_context.js",
    "frontend/browser_extension/content/exmail_visible_resource_classifier.js",
    "frontend/browser_extension/shared/api_client.js",
    "frontend/browser_extension/shared/manual_attachment_files.js",
    "frontend/browser_extension/shared/render_analysis.js",
    "frontend/browser_extension/shared/analysis_components.css",
    "docs/constraints/tooling_constraints.md",
    "docs/constraints/architecture_constraints.md",
    "docs/constraints/linter_constraints.md",
    "docs/constraints/mechanical_rule_translation.md",
    "docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md",
    "docs/decisions/0007-multimodal-current-email-analysis.md",
    "docs/operations/authorized_mailbox_ingest_task_brief.md",
    "docs/operations/deepseek_analysis_contract_alignment_task_brief.md",
    "docs/operations/private_deepseek_evaluation_task_brief.md",
    "docs/operations/private_mailbox_rollout_closeout_task_brief.md",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "docs/operations/current_email_grounding_and_attachment_repair_task_brief.md",
    "docs/operations/project_status_log.md",
    "docs/operations/project_status_log_guide.md",
    "docs/operations/agents_project_status_snippet.md",
    "docs/operations/cleanup_agent.md",
    "docs/operations/cleanup_agent_codex.md",
    "docs/operations/codex_cleanup_task.md",
    "docs/operations/documentation_rules.md",
    "docs/operations/first_version_task_brief.md",
    "docs/operations/tencent_exmail_browser_extension_task_brief.md",
    "docs/templates/agent_task_brief_template.md",
    "docs/templates/cleanup_task_template.md",
    "scripts/repo_utils.py",
    "scripts/maintenance_scan.py",
    "scripts/repository_leakage_scan.py",
    "scripts/generate_project_status.py",
    "scripts/run_local_debug.py",
    "scripts/manage_local_service.py",
    "scripts/manage_mailbox_vault.py",
    "scripts/manage_private" + "_knowledge.py",
    "scripts/evaluate_private_deepseek.py",
    "start_local_service.cmd",
    "stop_local_service.cmd",
    "restart_local_service.cmd",
    "status_local_service.cmd",
    "tests/fixtures/sample_emails.json",
    "tests/test_analysis_schema.py",
    "tests/test_analysis_model_routes.py",
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
    "tests/test_repository_leakage_scan.py",
    "tests/test_rollout_closeout_contracts.py",
    "tests/test_email_cleaner.py",
    "tests/test_analyzer.py",
    "tests/test_api.py",
    "tests/test_browser_extension_manifest.py",
    "tests/test_browser_extension_static.py",
    "tests/test_browser_extension_behavior.py",
    "tests/test_browser_extension_renderer_behavior.py",
    "tests/test_browser_extension_manual_attachment_files.py",
    "tests/test_browser_extension_task_focused_ui.py",
    "tests/test_browser_extension_visible_resource_classifier.py",
    "tests/test_model_grounding.py",
    "tests/test_model_result_safety.py",
    "tests/test_multimodal_documentation_contracts.py",
    "tests/test_multimodal_media.py",
    "tests/test_office_embedded_media.py",
    "tests/test_openai_multimodal_client.py",
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
    ("Repository leakage scan", "scripts/repository_leakage_scan.py"),
    ("Agent task brief", "docs/templates/agent_task_brief_template.md"),
    (
        "Authorized mailbox ingest boundary",
        "docs/operations/authorized_mailbox_ingest_task_brief.md",
    ),
]

AUTHORIZED_PRIVATE_INGEST_FILES = {
    "docs/constraints/architecture_constraints.md",
    "docs/operations/authorized_mailbox_ingest_task_brief.md",
    "docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md",
}

AUTHORIZED_PRIVATE_READY_FILES = {
    "backend/email_agent/private_context_gate.py",
    "scripts/manage_mailbox_vault.py",
    "scripts/evaluate_private_deepseek.py",
    "scripts/repository_leakage_scan.py",
    "docs/operations/private_deepseek_evaluation_task_brief.md",
    "docs/operations/private_mailbox_rollout_closeout_task_brief.md",
}

MULTIMODAL_CURRENT_EMAIL_READY_FILES = {
    "frontend/browser_extension/content/exmail_visible_context.js",
    "frontend/browser_extension/content/exmail_visible_resource_classifier.js",
    "frontend/browser_extension/shared/render_analysis.js",
    "backend/email_agent/multimodal_media.py",
    "backend/email_agent/openai_multimodal_client.py",
    "backend/email_agent/analysis_model_routes.py",
    "backend/email_agent/model_grounding.py",
    "backend/email_agent/model_visual_grounding.py",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "tests/test_openai_multimodal_client.py",
    "tests/test_analysis_model_routes.py",
    "tests/test_browser_extension_task_focused_ui.py",
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
    if MULTIMODAL_CURRENT_EMAIL_READY_FILES.issubset(existing):
        return "multimodal_current_email_offline_ready_live_pending"
    if AUTHORIZED_PRIVATE_READY_FILES.issubset(existing):
        return "authorized_private_analysis_offline_ready"
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
    if stage == "multimodal_current_email_offline_ready_live_pending":
        steps = [
            "Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled` outside a separately authorized, bounded live test process; all providers remain disabled by default, and offline completion does not authorize live operation.",
            "Task 9 synthetic provider and current-clicked Tencent smokes are complete. Task 9 forced OpenAI-to-DeepSeek synthetic fallback is complete: one OpenAI attempt was intercepted before network access, exactly one DeepSeek text-only request was made, DeepSeek SDK retries were zero, and no SQLite write occurred. The root `.env` was unchanged.",
            "Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. The evidence-reconciliation and private human gold-standard gates pass offline and the reviewed repair is integrated into the current release line.",
            "Any new live operation still requires fresh explicit authorization.",
            "Keep the administrator-only mailbox CLI and click-only current-message runtime as separate authorization surfaces.",
            "Run the content-free repository leakage scan and complete final verification before release; preserve unrelated working-copy changes and keep any remote push separate.",
        ]
    elif stage == "authorized_private_analysis_offline_ready":
        steps = [
            "Keep `EMAIL_AGENT_LLM_PROVIDER=disabled`; offline completion does not authorize live operation.",
            "Do not connect to a mailbox or run DeepSeek without a separate operator authorization after offline gates pass.",
            "Keep private evaluation blocked by default with `human_judge_unavailable`; the evaluator does not switch production models.",
            "If the signed private-knowledge snapshot is missing or invalid, preserve generic rule fallback.",
            "Run the content-free repository leakage scan and complete local human review before any release.",
        ]
    elif stage == "authorized_private_ingest_build":
        steps = [
            "Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` during implementation and automated verification.",
            "Implement later plan tasks with synthetic fakes and injected probes only.",
            "Do not connect to a mailbox or run DeepSeek without a separate operator authorization after offline gates pass.",
            "Preserve the click-only current-message Tencent Exmail Chrome / Edge 浏览器扩展 and normal runtime boundary.",
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

Separately authorized exception: the `administrator-only CLI remains default-off` and may import one authorized account within a rolling 24-month window only after explicit inventory fingerprint confirmation. The browser extension and normal runtime remain click-only and cannot scan a mailbox. The exception has no schedule, browser hook, normal-backend route, or automatic model call.

The private-knowledge snapshot is verified and read-only; an invalid or missing private-knowledge snapshot returns generic rule fallback. Tasks 1-7 of the multimodal current-email route are offline implemented and review-clean. The route is one OpenAI multimodal primary call, at most one eligible DeepSeek text-only fallback, and deterministic rules last; all providers remain disabled by default. Its budget tuple is `60/55/35/10/12/8/5` seconds: 60-second POST wait, 55-second backend target, 35-second OpenAI cap, 10-second DeepSeek cap, 12-second fallback minimum, 8-second parser cap, and 5-second reserve. Browser media discovery remains a separate 20-second resource collection phase. Private evaluation is blocked by `human_judge_unavailable` by default and does not switch production models.

Current-message attachment acquisition recognizes only a verified legacy current-message control after Analyze and keeps automatic bytes in browser memory. The manual picker selection is inert until Analyze. Both paths share 5 files, 10 MiB per file, and 25 MiB total, add no download/storage/filesystem permission, and expose no local path. Backend request-local files are removed from request `finally`; the 24-hour mtime cleanup is crash recovery only, not normal retention or a scheduled job. Only `attachment_insights[].status=parsed` proves content parsing.

Prior Task 9 synthetic and current-clicked smokes remain valid acquisition, routing, status, and cleanup evidence only. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. Current/history evidence alignment, provider-visible attachment coverage, deterministic reconciliation safeguards, and the documented private human gold-standard method now pass the offline gate; the reviewed repair is integrated into the current release line. Any new live operation still requires fresh explicit authorization. All providers remain disabled by default.

The selected daily frontend remains the Tencent Exmail Chrome / Edge 浏览器扩展, with current-message collection only after an explicit user click.

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
