---
last_update: 2026-07-23
status: deprecated
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Retired Codex Cleanup Automation

本文件只保留已删除 Codex cleanup automation 的历史配置和安全合同。它不再是
active automation 入口，不得据此创建、恢复或重新绑定任务。

手动只读维护扫描仍以 `docs/operations/cleanup_agent.md` 和
`scripts/maintenance_scan.py` 为准。历史 Prompt 保留在
`docs/operations/codex_cleanup_task.md`，其状态同样是 deprecated。

## 1. Retirement record

```text
Task name: Weekly Cleanup Agent
Automation id: weekly-cleanup-agent
State: deleted by the operator
Recorded on: 2026-07-23
Replacement: none
```

删除状态是操作员确认事实。Agent 不再搜索、创建或恢复该 automation，也不再把
缺少本地 automation config 报告为项目问题。全局 Codex automation 配置继续位于
项目外，不得复制进仓库。

## 2. Historical contract

历史任务只允许 read-only scan and report，并禁止自动修复、删除、提交、push、
创建 PR 或合并。该合同不授权新的 automation。

## 3. Non-normative future-work pointer

未来 weekly code-review automation 不属于本 deprecated 文档。本文件不为任何
新 automation 提供开发依据或授权。当前 active planning pointer 是
`docs/operations/project_container_migration_task_brief.md` 的 8.11 节；实施前仍须
建立独立 task brief、Issue、名称、schedule 和安全合同。

仓库中的 `.github/workflows/cleanup_agent.yml` 是另一个 scheduled GitHub Actions
workflow definition，不因 Codex automation 被删除而自动停用。本文件不决定其
remote state 或后续处置。
