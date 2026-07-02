---
last_update: 2026-07-02
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
| Generated on | 2026-07-02 |
| Current stage | local_eval_mvp |
| Git branch | codex/tencent-exmail-extension-design |
| Git HEAD reference | Run `git rev-parse --short HEAD` in this workspace |
| Working tree status | Run `git status --short --ignored` in this workspace |

## Project Summary

本项目是企业邮箱中的 AI 辅助窗口。第一阶段只做“用户点击按钮后分析当前打开邮件”，不做全邮箱扫描、不自动发送邮件、不删除邮件、不归档邮件、不接入真实邮箱账号。

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
| `Agent task brief: docs/templates/agent_task_brief_template.md` | yes |

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
| `docs/operations/project_status_log.md` | yes |
| `docs/operations/project_status_log_guide.md` | yes |
| `docs/operations/agents_project_status_snippet.md` | yes |
| `docs/operations/cleanup_agent.md` | yes |
| `docs/operations/cleanup_agent_codex.md` | yes |
| `docs/operations/codex_cleanup_task.md` | yes |
| `docs/operations/documentation_rules.md` | yes |
| `docs/operations/first_version_task_brief.md` | yes |
| `docs/operations/tencent_exmail_browser_extension_task_brief.md` | yes |
| `docs/templates/agent_task_brief_template.md` | yes |
| `docs/templates/cleanup_task_template.md` | yes |
| `scripts/repo_utils.py` | yes |
| `scripts/maintenance_scan.py` | yes |
| `scripts/generate_project_status.py` | yes |
| `scripts/run_local_debug.py` | yes |
| `scripts/manage_local_service.py` | yes |
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
| `tests/test_maintenance_scan.py` | yes |
| `tests/test_generate_project_status.py` | yes |
| `tests/test_email_cleaner.py` | yes |
| `tests/test_analyzer.py` | yes |
| `tests/test_api.py` | yes |
| `tests/test_browser_extension_manifest.py` | yes |
| `tests/test_browser_extension_static.py` | yes |

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
| active | 48 |
| draft | 29 |
| deprecated | 0 |
| missing_front_matter | 0 |

## Recommended Next Steps

1. 运行完整测试和维护扫描。
2. 用虚构样例手动试用本地调试页面。
3. 提供 GitHub 远程地址后推送第一阶段项目。
4. 继续验证 Tencent Exmail Chrome / Edge 浏览器扩展原型；Outlook Add-in 和 Google Workspace Add-on 保持后续单独确认。

## Do Not Touch Boundaries

- 不接入真实邮箱账号。
- 不读取真实邮箱数据。
- 不自动发送邮件。
- 不自动删除邮件。
- 不自动归档邮件。
- 不自动扫描所有邮件。
- 不把 OpenAI API key 放入前端。
- 不新增依赖，除非先更新约束文档并获得确认。
- 不放宽任何测试、linter 或架构约束。

## Notes for Agent

- 先读 `AGENTS.md`，再读本文件。
- 涉及工具、架构、linter、机械规则、安全边界时，继续读 `docs/constraints/`。
- 涉及任务执行前规划时，填写 `docs/templates/agent_task_brief_template.md`。
- 不要把项目进度流水账写入 `AGENTS.md`。
