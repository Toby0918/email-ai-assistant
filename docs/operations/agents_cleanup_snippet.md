---
last_update: 2026-06-30
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# AGENTS Snippet: Cleanup Agent

本片段用于维护 `AGENTS.md` 中关于后台清理 Agent 的简短入口说明。完整规则不要复制到 `AGENTS.md`，应通过以下文件导航：

```text
通用规则：docs/operations/cleanup_agent.md
Codex 自动化：docs/operations/cleanup_agent_codex.md
任务 Prompt：docs/operations/codex_cleanup_task.md
清理模板：docs/templates/cleanup_task_template.md
只读脚本：scripts/maintenance_scan.py
```

## 推荐说明

```text
后台清理 Agent 是只读定时扫描；通用规则见 docs/operations/cleanup_agent.md，Codex 自动执行规范见 docs/operations/cleanup_agent_codex.md，任务 Prompt 源文件见 docs/operations/codex_cleanup_task.md，脚本见 scripts/maintenance_scan.py。不得自动删除、自动修复、自动提交或自动合并。
```

如保留 `.github/workflows/cleanup_agent.yml`，它只是可选报告通道或 CI 补充，不是主规则来源。
