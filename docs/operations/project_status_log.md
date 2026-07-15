---
last_update: 2026-07-15
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
| Generated on | 2026-07-15 |
| Current stage | authorized_private_analysis_offline_ready |
| Git branch | codex/authorized-mailbox-ingest |
| Git HEAD reference | Run `git rev-parse --short HEAD` in this workspace |
| Working tree status | Run `git status --short --ignored` in this workspace |

## Project Summary

本项目是企业邮箱中的 AI 辅助窗口。正常产品只做“用户点击按钮后分析当前打开邮件”，不做全邮箱扫描、不自动发送邮件、不删除邮件或归档邮件。

Separately authorized exception: the `administrator-only CLI remains default-off` and may import one authorized account within a rolling 24-month window only after explicit inventory fingerprint confirmation. The browser extension and normal runtime remain click-only and cannot scan a mailbox. The exception has no schedule, browser hook, normal-backend route, or automatic model call.

The private-knowledge snapshot is verified and read-only; an invalid or missing private-knowledge snapshot returns generic rule fallback. DeepSeek outbound content remains locally deidentified with browser/backend/provider/minimum budgets of `15/13/10/5` seconds. Private evaluation is blocked by `human_judge_unavailable` by default and does not switch production models.

The selected daily frontend remains the Tencent Exmail Chrome / Edge 浏览器扩展, with current-message collection only after an explicit user click.

## Guardrails Established

| File | Exists |
|---|---|
| `Project entry rules: AGENTS.md` | yes |
| `Tooling constraints: docs/constraints/tooling_constraints.md` | yes |
| `Architecture constraints: docs/constraints/architecture_constraints.md` | yes |
| `Static linter constraints: docs/constraints/linter_constraints.md` | yes |
| `Mechanical rule translation: docs/constraints/mechanical_rule_translation.md` | yes |
| `CI guardrails: .github/workflows/agent_guardrails.yml` | yes |
| `Cleanup automation: docs/operations/cleanup_agent_codex.md` | yes |
| `Maintenance scan: scripts/maintenance_scan.py` | yes |
| `Repository leakage scan: scripts/repository_leakage_scan.py` | yes |
| `Agent task brief: docs/templates/agent_task_brief_template.md` | yes |
| `Authorized mailbox ingest boundary: docs/operations/authorized_mailbox_ingest_task_brief.md` | yes |

## Key File Status

| File | Exists |
|---|---|
| `AGENTS.md` | yes |
| `README.md` | yes |
| `.env.example` | yes |
| `requirements.txt` | yes |
| `.gitignore` | yes |
| `.github/workflows/agent_guardrails.yml` | yes |
| `.github/workflows/cleanup_agent.yml` | yes |
| `backend/email_agent/__init__.py` | yes |
| `backend/email_agent/analysis_schema.py` | yes |
| `backend/email_agent/config.py` | yes |
| `backend/email_agent/logging_config.py` | yes |
| `backend/email_agent/email_cleaner.py` | yes |
| `backend/email_agent/analyzer.py` | yes |
| `backend/email_agent/rule_analyzer.py` | yes |
| `backend/email_agent/llm_client.py` | yes |
| `backend/email_agent/database.py` | yes |
| `backend/email_agent/exporter.py` | yes |
| `backend/email_agent/api.py` | yes |
| `backend/email_agent/server.py` | yes |
| `backend/email_agent/private_context_gate.py` | yes |
| `frontend/local_debug_page/index.html` | yes |
| `frontend/local_debug_page/app.js` | yes |
| `frontend/local_debug_page/styles.css` | yes |
| `frontend/browser_extension/manifest.json` | yes |
| `frontend/browser_extension/popup.html` | yes |
| `frontend/browser_extension/popup.css` | yes |
| `frontend/browser_extension/popup.js` | yes |
| `frontend/browser_extension/content/exmail_adapter.js` | yes |
| `frontend/browser_extension/shared/api_client.js` | yes |
| `frontend/browser_extension/shared/render_analysis.js` | yes |
| `docs/constraints/tooling_constraints.md` | yes |
| `docs/constraints/architecture_constraints.md` | yes |
| `docs/constraints/linter_constraints.md` | yes |
| `docs/constraints/mechanical_rule_translation.md` | yes |
| `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md` | yes |
| `docs/operations/authorized_mailbox_ingest_task_brief.md` | yes |
| `docs/operations/deepseek_analysis_contract_alignment_task_brief.md` | yes |
| `docs/operations/private_deepseek_evaluation_task_brief.md` | yes |
| `docs/operations/private_mailbox_rollout_closeout_task_brief.md` | yes |
| `docs/operations/project_status_log.md` | yes |
| `docs/operations/project_status_log_guide.md` | yes |
| `docs/operations/agents_project_status_snippet.md` | yes |
| `docs/operations/cleanup_agent.md` | yes |
| `docs/operations/cleanup_agent_codex.md` | yes |
| `docs/operations/codex_cleanup_task.md` | yes |
| `docs/operations/documentation_rules.md` | yes |
| `docs/operations/first_version_task_brief.md` | yes |
| `docs/operations/tencent_exmail_browser_extension_task_brief.md` | yes |
| `docs/superpowers/plans/2026-07-14-authorized-mailbox-ingest-knowledge-deepseek.md` | yes |
| `docs/superpowers/plans/2026-07-14-mailbox-vault.md` | yes |
| `docs/superpowers/plans/2026-07-14-private-knowledge.md` | yes |
| `docs/superpowers/plans/2026-07-14-private-deepseek-evaluation.md` | yes |
| `docs/templates/agent_task_brief_template.md` | yes |
| `docs/templates/cleanup_task_template.md` | yes |
| `scripts/repo_utils.py` | yes |
| `scripts/maintenance_scan.py` | yes |
| `scripts/repository_leakage_scan.py` | yes |
| `scripts/generate_project_status.py` | yes |
| `scripts/run_local_debug.py` | yes |
| `scripts/manage_local_service.py` | yes |
| `scripts/manage_mailbox_vault.py` | yes |
| `scripts/evaluate_private_deepseek.py` | yes |
| `start_local_service.cmd` | yes |
| `stop_local_service.cmd` | yes |
| `restart_local_service.cmd` | yes |
| `status_local_service.cmd` | yes |
| `tests/fixtures/sample_emails.json` | yes |
| `tests/test_analysis_schema.py` | yes |
| `tests/test_golden_email_analysis.py` | yes |
| `tests/test_rule_analyzer.py` | yes |
| `tests/test_database.py` | yes |
| `tests/test_server.py` | yes |
| `tests/test_frontend_local_debug.py` | yes |
| `tests/test_repo_utils.py` | yes |
| `tests/test_config.py` | yes |
| `tests/test_run_local_debug.py` | yes |
| `tests/test_manage_local_service.py` | yes |
| `tests/support.py` | yes |
| `tests/test_architecture_constraints.py` | yes |
| `tests/test_static_linter_constraints.py` | yes |
| `tests/test_mechanical_rule_constraints.py` | yes |
| `tests/test_mailbox_transport_constraints.py` | yes |
| `tests/test_maintenance_scan.py` | yes |
| `tests/test_generate_project_status.py` | yes |
| `tests/test_repository_leakage_scan.py` | yes |
| `tests/test_rollout_closeout_contracts.py` | yes |
| `tests/test_email_cleaner.py` | yes |
| `tests/test_analyzer.py` | yes |
| `tests/test_api.py` | yes |
| `tests/test_browser_extension_manifest.py` | yes |
| `tests/test_browser_extension_static.py` | yes |
| `tests/test_browser_extension_behavior.py` | yes |

## docs Directory Status

| File | Exists |
|---|---|
| `docs/product` | yes |
| `docs/knowledge_base` | yes |
| `docs/prompts` | yes |
| `docs/data` | yes |
| `docs/api` | yes |
| `docs/security` | yes |
| `docs/constraints` | yes |
| `docs/conventions` | yes |
| `docs/decisions` | yes |
| `docs/operations` | yes |
| `docs/templates` | yes |

## docs Metadata Summary

| Status | Count |
|---|---:|
| active | 89 |
| draft | 24 |
| deprecated | 0 |
| missing_front_matter | 0 |

## Recommended Next Steps

1. Keep `EMAIL_AGENT_LLM_PROVIDER=disabled`; offline completion does not authorize live operation.
2. Do not connect to a mailbox or run DeepSeek without a separate operator authorization after offline gates pass.
3. Keep private evaluation blocked by default with `human_judge_unavailable`; the evaluator does not switch production models.
4. If the signed private-knowledge snapshot is missing or invalid, preserve generic rule fallback.
5. Run the content-free repository leakage scan and complete local human review before any release.

## Do Not Touch Boundaries

- 浏览器扩展和正常运行时不接入真实邮箱账号；唯一例外是管理员手动运行的单账户只读导入 CLI。
- 浏览器扩展和正常运行时不读取真实邮箱数据；管理员 CLI 只处理授权范围并先确认 inventory fingerprint。
- 不自动发送邮件。
- 不自动删除邮件。
- 不自动归档邮件。
- 浏览器扩展和正常运行时不自动扫描所有邮件；管理员 CLI 没有 schedule、后台轮询或自动模型推理。
- 不把 OpenAI API key 放入前端。
- 不新增依赖，除非先更新约束文档并获得确认。
- 不放宽任何测试、linter 或架构约束。

## Notes for Agent

- 先读 `AGENTS.md`，再读本文件。
- 涉及工具、架构、linter、机械规则、安全边界时，继续读 `docs/constraints/`。
- 涉及任务执行前规划时，填写 `docs/templates/agent_task_brief_template.md`。
- 不要把项目进度流水账写入 `AGENTS.md`。
