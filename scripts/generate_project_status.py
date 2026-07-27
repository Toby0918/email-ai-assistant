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
    "backend/current_evidence/__init__.py",
    "backend/current_evidence/artifact_policy.py",
    "backend/current_evidence/contract.py",
    "backend/current_evidence/handoff.py",
    "backend/cutover_contracts/__init__.py",
    "backend/cutover_contracts/_canonical.py",
    "backend/cutover_contracts/authorization.py",
    "backend/cutover_contracts/authorization_schema.py",
    "backend/cutover_contracts/authorization_validation.py",
    "backend/cutover_contracts/errors.py",
    "backend/cutover_contracts/operator_entry.py",
    "backend/cutover_contracts/profile.py",
    "backend/cutover_contracts/profile_schema.py",
    "backend/cutover_contracts/receipt.py",
    "backend/cutover_contracts/receipt_matrix.py",
    "backend/cutover_contracts/receipt_schema.py",
    "backend/cutover_contracts/receipt_types.py",
    "backend/cutover_journal/__init__.py",
    "backend/cutover_journal/_canonical.py",
    "backend/cutover_journal/action_common.py",
    "backend/cutover_journal/chain_reducer.py",
    "backend/cutover_journal/closed_classifier.py",
    "backend/cutover_journal/contracts_bridge.py",
    "backend/cutover_journal/durability.py",
    "backend/cutover_journal/effect_permit.py",
    "backend/cutover_journal/effect_guard.py",
    "backend/cutover_journal/effect_state.py",
    "backend/cutover_journal/errors.py",
    "backend/cutover_journal/journal_chain.py",
    "backend/cutover_journal/journal_record.py",
    "backend/cutover_journal/journal_store.py",
    "backend/cutover_journal/journal_types.py",
    "backend/cutover_journal/operation_binding.py",
    "backend/cutover_journal/pending_classifier.py",
    "backend/cutover_journal/record_schema.py",
    "backend/cutover_journal/recovery.py",
    "backend/cutover_journal/recovery_classifier.py",
    "backend/cutover_journal/recovery_types.py",
    "backend/cutover_journal/resume_actions.py",
    "backend/cutover_journal/rollback_actions.py",
    "backend/cutover_journal/store_support.py",
    "backend/cutover_journal/transaction.py",
    "backend/real_host_preflight/__init__.py",
    "backend/real_host_preflight/audit_bridge.py",
    "backend/real_host_preflight/audit_types.py",
    "backend/real_host_preflight/authorization_gate.py",
    "backend/real_host_preflight/baseline.py",
    "backend/real_host_preflight/baseline_bridge.py",
    "backend/real_host_preflight/baseline_evidence.py",
    "backend/real_host_preflight/callbacks.py",
    "backend/real_host_preflight/canonical.py",
    "backend/real_host_preflight/collection.py",
    "backend/real_host_preflight/composition.py",
    "backend/real_host_preflight/contracts.py",
    "backend/real_host_preflight/contracts_bridge.py",
    "backend/real_host_preflight/errors.py",
    "backend/real_host_preflight/evidence.py",
    "backend/real_host_preflight/integrity.py",
    "backend/real_host_preflight/mutation_gate.py",
    "backend/real_host_preflight/operator_entry.py",
    "backend/real_host_preflight/receipts.py",
    "backend/real_host_preflight/sandbox_state.py",
    "backend/real_host_preflight/sandbox_validation.py",
    "backend/real_host_preflight/topology.py",
    "backend/real_host_preflight/topology_evidence.py",
    "backend/real_host_preflight/windows_api.py",
    "backend/real_host_preflight/windows_chain.py",
    "backend/real_host_preflight/windows_observation.py",
    "backend/real_host_preflight/windows_paths.py",
    "backend/real_host_preflight/windows_projection.py",
    "backend/migration_evidence/__init__.py",
    "backend/migration_evidence/package.py",
    "backend/migration_evidence/review.py",
    "backend/migration_evidence/verification.py",
    "backend/reparenting_rehearsal/__init__.py",
    "backend/reparenting_rehearsal/rehearsal.py",
    "backend/runtime_activation_rehearsal/__init__.py",
    "backend/runtime_activation_rehearsal/rehearsal.py",
    "backend/runtime_activation_rehearsal/service_checks.py",
    "backend/mailbox" + "_ingest/governed_scan.py",
    "backend/mailbox" + "_ingest/sales_corpus_index.py",
    "backend/mailbox" + "_ingest/sales_message_policy.py",
    "backend/mailbox" + "_ingest/sales_policy_file.py",
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
    "backend/email_agent/managed_runtime.py",
    "backend/email_agent/managed_runtime_errors.py",
    "backend/email_agent/managed_runtime_validation.py",
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
    "docs/security/project_container_cutover_contracts.md",
    "docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md",
    "docs/decisions/0007-multimodal-current-email-analysis.md",
    "docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md",
    "docs/decisions/0009-project-container-and-repository-boundaries.md",
    "docs/operations/authorized_mailbox_ingest_task_brief.md",
    "docs/operations/bounded_corpus_runtime_handoffs_task_brief.md",
    "docs/operations/issue11_governed_sales_corpus_task_brief.md",
    "docs/operations/deepseek_analysis_contract_alignment_task_brief.md",
    "docs/operations/private_deepseek_evaluation_task_brief.md",
    "docs/operations/private_mailbox_rollout_closeout_task_brief.md",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "docs/operations/current_email_grounding_and_attachment_repair_task_brief.md",
    "docs/operations/issue32_managed_container_mode_task_brief.md",
    "docs/operations/issue35_migration_evidence_package_task_brief.md",
    "docs/operations/issue36_reparenting_rehearsal_task_brief.md",
    "docs/operations/issue37_managed_runtime_localdata_rehearsal_task_brief.md",
    "docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md",
    "docs/operations/issue52_crash_safe_journal_recovery_task_brief.md",
    "docs/operations/issue53_windows_real_host_preflight_task_brief.md",
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
    "tests/test_managed_container_mode.py",
    "tests/test_migration_evidence_no_clobber.py",
    "tests/test_migration_evidence_restore.py",
    "tests/test_migration_evidence_verification.py",
    "tests/test_reparenting_rehearsal_rollback.py",
    "tests/test_reparenting_rehearsal_safety.py",
    "tests/test_reparenting_rehearsal_success.py",
    "tests/test_runtime_activation_rehearsal_architecture.py",
    "tests/test_runtime_activation_rehearsal_integration.py",
    "tests/test_runtime_activation_rehearsal_service.py",
    "tests/cutover_contract_fixtures.py",
    "tests/test_cutover_authorization_contract.py",
    "tests/test_cutover_contract_architecture.py",
    "tests/test_cutover_profile_contract.py",
    "tests/test_cutover_receipt_contract.py",
    "tests/cutover_journal_fixtures.py",
    "tests/test_cutover_journal_architecture.py",
    "tests/test_cutover_journal_chain.py",
    "tests/test_cutover_journal_crash_matrix.py",
    "tests/test_cutover_journal_durability.py",
    "tests/test_cutover_journal_record_contract.py",
    "tests/test_cutover_journal_recovery.py",
    "tests/real_host_preflight_fixtures.py",
    "tests/test_real_host_preflight_architecture.py",
    "tests/test_real_host_preflight_baseline.py",
    "tests/test_real_host_preflight_composition.py",
    "tests/test_real_host_preflight_gate.py",
    "tests/test_real_host_preflight_leakage.py",
    "tests/test_real_host_preflight_portable.py",
    "tests/test_real_host_preflight_topology.py",
    "tests/test_real_host_preflight_windows.py",
    "tests/test_real_host_preflight_windows_composition.py",
    "tests/support.py",
    "tests/test_architecture_constraints.py",
    "tests/test_current_evidence_handoff.py",
    "tests/test_static_linter_constraints.py",
    "tests/test_mechanical_rule_constraints.py",
    "tests/test_mailbox_transport_constraints.py",
    "tests/test_mailbox_governed_scan.py",
    "tests/test_mailbox_sales_corpus_index.py",
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
    (
        "Bounded corpus-to-runtime handoffs",
        "docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md",
    ),
    (
        "Governed sales corpus bootstrap",
        "docs/operations/issue11_governed_sales_corpus_task_brief.md",
    ),
    (
        "No-clobber migration evidence package",
        "docs/operations/issue35_migration_evidence_package_task_brief.md",
    ),
    (
        "Synthetic repository reparenting rehearsal",
        "docs/operations/issue36_reparenting_rehearsal_task_brief.md",
    ),
    (
        "Synthetic Managed runtime activation rehearsal",
        "docs/operations/issue37_managed_runtime_localdata_rehearsal_task_brief.md",
    ),
    (
        "Locked cutover contracts",
        "docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md",
    ),
    (
        "Synthetic crash-safe journal and recovery classification",
        "docs/operations/issue52_crash_safe_journal_recovery_task_brief.md",
    ),
    (
        "Content-free Windows real-host preflight composition",
        "docs/operations/issue53_windows_real_host_preflight_task_brief.md",
    ),
    (
        "Project Container cutover contract security boundary",
        "docs/security/project_container_cutover_contracts.md",
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
    "真实 migration evidence package 必须先展示 exact target、content-free inclusion/exclusion manifest、reviewed local refs 和 worktree selection，并在单独确认前停止。",
    "Issue #36 只证明 temporary synthetic rehearsal；不得把它当作真实 migration、audit、worktree repair 或 cutover 授权。",
    "Issue #37 只证明 injected-adapter temporary synthetic activation rehearsal；不得把它当作真实 runtime、SQLite、artifact activation 或 cutover 授权。",
    "Issue #51 只建立 pure content-free contracts；四种 real-host authorization 只能验证外部 canonical values，不能 create、issue 或 mint，且默认 operator entry 保持 BLOCKED。",
    "Issue #52 只建立 pathless synthetic journal/recovery proof；pending/unbarriered record 不授权 effect，每次 owner claim 与 durable-intent permit 都是 exact synthetic capability，observed/pending/profile/identity/mapping fail closed，restart inspection 只读，且不得触碰真实 host 或 private capability。",
    "Issue #53 只建立 test-sandbox-owned Windows read-only observation 与窄 callback composition；真实 operator entry 继续 BLOCKED，不得把 receipt、test authorization 或 readiness 当作 mutation/cutover authority。",
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

Issue #11 governed sales-corpus bootstrap is offline implemented. `scan` requires a separately stored strict private sales policy, binds only keyed metadata to a fresh corpus index, deduplicates cross-folder messages and attachment blobs, and exposes only fixed aggregate counts. Only an exact external-customer request to a strictly later allowlisted reply becomes a governed pair; unpaired records are rejected before downstream staging or reviewed attachment acquisition. No live mailbox, provider, or real private vault was used for this implementation.

ADR 0008 ratifies a future manual incremental-sync boundary and a contract-only, write-only deidentified current-click evidence seam. Issue #10 adds no sync command or evidence inbox; those implementations remain in future issues #17 and #18. Normal runtime receives no mailbox, historical-store, authority-store, reader, search, path, key, repository, polling, or hot-reload capability.

The private-knowledge snapshot is verified and read-only; an invalid or missing private-knowledge snapshot returns generic rule fallback. Tasks 1-7 of the multimodal current-email route are offline implemented and review-clean. The route is one OpenAI multimodal primary call, at most one eligible DeepSeek text-only fallback, and deterministic rules last; all providers remain disabled by default. Its budget tuple is `60/55/35/10/12/8/5` seconds: 60-second POST wait, 55-second backend target, 35-second OpenAI cap, 10-second DeepSeek cap, 12-second fallback minimum, 8-second parser cap, and 5-second reserve. Browser media discovery remains a separate 20-second resource collection phase. Private evaluation is blocked by `human_judge_unavailable` by default and does not switch production models.

Current-message attachment acquisition recognizes only a verified legacy current-message control after Analyze and keeps automatic bytes in browser memory. The manual picker selection is inert until Analyze. Both paths share 5 files, 10 MiB per file, and 25 MiB total, add no download/storage/filesystem permission, and expose no local path. Backend request-local files are removed from request `finally`; the 24-hour mtime cleanup is crash recovery only, not normal retention or a scheduled job. Only `attachment_insights[].status=parsed` proves content parsing.

Prior Task 9 synthetic and current-clicked smokes remain valid acquisition, routing, status, and cleanup evidence only. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. Current/history evidence alignment, provider-visible attachment coverage, deterministic reconciliation safeguards, and the documented private human gold-standard method now pass the offline gate; the reviewed repair is integrated into the current release line. Any new live operation still requires fresh explicit authorization. All providers remain disabled by default.

Issue #32 Managed launcher is implemented for the exact `email_ai_assistant\\main` placement. It routes provider-disabled SQLite, attachment temp, logs, PID, runtime, artifact, worktree, and bounded non-secret Config paths to their approved zones while source and repository tooling remain at `main`. Synthetic loopback lifecycle verification passes, but no real Project Container migration or operational cutover has occurred.

Issue #34 manual content-free Container Audit is offline implemented behind seven injected read-only metadata adapters. Its exact nine-entry, ACL, volume, Git/worktree, runtime, SQLite, Config, Logs/Artifacts, and disabled-private-state contract fails closed and exposes only fixed status/counts. No real Container audit or host-security probe was run.

Issue #35 no-clobber migration evidence package is offline implemented as a manual internal Python contract. It binds exact reviewed local refs, branch-attached worktree identities, an allowlisted two-layer dirty-source snapshot, content-free Git/ACL/volume baselines, and every payload file with canonical SHA-256 evidence. Publication is external-target, create-only and fail-closed; verification restores Git objects, refs, dirty state and worktree identity in synthetic repositories. No real evidence package was created.

Issue #36 repository/worktree reparenting rehearsal is offline implemented as one pathless synthetic-only Python seam. It builds a temporary repository with a bound marker filesystem identity and a non-trivial Git baseline, creates and verifies one synthetic Issue #35 package, no-clobber moves the existing Git common directory and reviewed source into a synthetic `main`, applies injected repair/recreate worktree choices, verifies exact post-state and passes a synthetic ContainerAudit. All six publication-boundary failures verify rollback preservation; post-main failures preserve the complete Container at the single sibling rollback path. The public operation leaves the synthetic topology intact for independent caller observation. No real workspace, worktree, branch, directory, ACL, runtime, database or private data was touched; Issues #38 through #40 remain separate.

Issue #37 managed runtime and LocalData activation rehearsal is offline implemented behind exact five injected adapters and one pathless synthetic-only seam. Temporary synthetic sources prove a create-only pinned runtime, a Windows venv rebuilt from the exact dependency lock, `pre_publication` stopped-service create-only SQLite publication with identity/SHA-256/integrity/sidecar/count checks, reviewed-hash browser-extension publication, exact Managed writable roles, and one strict activation token across provider-disabled start, literal-loopback health, one persisted rule-fallback analysis and the same-service `post_activation` fresh-stop proof. Stale evidence and equality spoofing fail closed. The source database remains unchanged after success and every simulated race, reparse, existing-target, dependency, integrity or health failure. No real runtime, SQLite database, browser-extension artifact or migration evidence package was activated; Issues #38 through #40 remain separate.

Issue #51 locked Cutover Profile, authorization, and receipt contracts are offline implemented as a pure content-free Python contract layer. Immutable `CutoverProfileV1` values bind the reviewed cutover inputs without paths or host readers. The four distinct real-host authorization value types validate externally supplied canonical values and cannot create, issue, or mint authority. The strict canonical `ReceiptEnvelopeV1` values are duplicate/unknown rejecting, fingerprint-bound, and never accepted as authorization. `default_operator_entry()` remains fixed at `BLOCKED_NO_APPROVED_COMMAND`. Its approved consumers are the exact Issue #52 journal bridge and exact Issue #53 preflight contract bridges.

Issue #52 crash-safe journal and recovery classification are offline implemented in the pathless synthetic-only `backend.cutover_journal` package. Strict canonical create-only records bind sequence, previous/record hashes, fixed synthetic step/event/direction, operation/profile/authorization/owner fingerprints, and opaque observations. Every forward and reverse action uses durable `INTENT`, exact observed effect, and `COMMITTED`; each owner claim gets a distinct lease and each effect consumes a non-copyable, non-serializable single-use store permit bound to the exact active durable intent and durable journal head. The shared store-private issuance is atomically claimed; one synthetic medium operation gate serializes append, restart, permit mint/claim, and effect mutation; every namespace-published current head completes stable reread and full snapshot reverification before a successor append or permit. Stable-reread evidence is hash-bound, and head advance, pending state, or an observed fact invalidates stale permits. Pending or unbarriered records never authorize an effect; verified pending direction/event/outcome controls event-aware exact pending publication without effect replay or an extra action; durable observed facts are authoritative across fresh `RESUME_BOUND` renewal. Reverse steps are derived LIFO only from verified `COMMITTED/APPLIED` history. Exact Profile/master/operator, identity mapping, synthetic transition mapping, and post-effect observation all fail closed. Exact in-memory Windows/Linux traces prove file/namespace/stable-reread ordering without claiming real filesystem durability. Restart inspection is read-only, exact expected-post is never blindly repeated, and explicit resume/rollback fresh-validate phase-specific authorization including the pre-bound recovery fingerprint. Public results expose only fixed status, phase, receipt fingerprint, and allowlisted counts distinguishing `SAFE_ABORT`, `ROLLBACK_REQUIRED`, `INCIDENT_STOP`, and `CUTOVER_SUCCEEDED`. No real filesystem target, service, ACL, Git repository/worktree, Runtime, SQLite, provider, mailbox, vault, private data, preflight, migration, cutover, resume, or rollback was accessed or run; Issues #54 through #59 remain separate.

Issue #53 content-free Windows real-host preflight composition is offline implemented in `backend.real_host_preflight`. The package-private Windows observer opens every controlled path component without following reparse points and binds fixed-volume identity, 128-bit file identity, object type, parent identity, normalized-name fingerprint, attributes, reparse metadata, and exactly-one-link file alias evidence. Only exact, unexpired `TestSandboxAuthorizationV1` values plus a root/marker identity-bound atomically single-use permit can create test-owned temporary scopes; no real project path was observed. `CurrentTopologyPreflight` factory-reconstructs every callback value, binds source/parent/finance/target names to exact Profile role selections, and requires two complete identical seven-reader observations. `PreMutationGate` is short-lived, UUIDv4 nonce-bound, single-operation and single-use; each topology receipt can be atomically claimed by at most one gate, and trusted receipt/gate state is module-owned. `RealHostBaselineCollector` keeps source, parent, finance, volume, operator-SID, and three ACL roles separate while projecting the existing canonical `HostBaseline`. The unchanged nine-zone `ContainerAudit` receives exactly seven revalidated callbacks through a narrow bridge; final-audit readiness validates the identical bound readers without running or claiming a final-layout audit. The zero-argument operator entry remains fixed at `BLOCKED_NO_APPROVED_COMMAND` and cannot accept test authorization. Production code has no service-control, ACL-apply, rename, worktree mutation, Runtime build, database copy, artifact, Config, provider, mailbox, vault, private-data, or content-reading capability. Windows behavior was exercised only in test-owned temporary sandboxes, and portable tests make no NTFS or Windows ACL claim. Issues #54 through #59, Issues #38/#39, and parent Spec #50 remain separate and unchanged.

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
