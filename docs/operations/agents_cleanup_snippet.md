---
last_update: 2026-07-23
status: deprecated
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# AGENTS Snippet: Cleanup Agent

> Deprecated on 2026-07-23 after the operator deleted
> `weekly-cleanup-agent`. Do not copy the old scheduled-automation wording into
> `AGENTS.md`.

本片段用于维护 `AGENTS.md` 中关于后台清理 Agent 的简短入口说明。完整规则不要复制到 `AGENTS.md`，应通过以下文件导航：

```text
通用规则：docs/operations/cleanup_agent.md
Codex 自动化：docs/operations/cleanup_agent_codex.md
任务 Prompt：docs/operations/codex_cleanup_task.md
清理模板：docs/templates/cleanup_task_template.md
只读脚本：scripts/maintenance_scan.py
```

## Historical snippet status

```text
旧 Codex weekly-cleanup-agent 已删除，不得自动恢复。手动只读维护扫描规则见 docs/operations/cleanup_agent.md。
```

该历史片段不得再复制到 `AGENTS.md`。仓库仍包含单独的
`.github/workflows/cleanup_agent.yml` scheduled workflow definition，其处置必须
由单独 approved Issue 决定。
