---
last_update: 2026-07-21
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Cleanup Agent for Codex Automation

本文件只定义后台清理 Agent 在 Codex 自动化任务中的配置入口和执行关系。通用清理边界以 `docs/operations/cleanup_agent.md` 为准，完整任务 Prompt 以 `docs/operations/codex_cleanup_task.md` 为准。

为避免重复维护，本文件不重新抄写允许行为、禁止行为、命令列表和报告模板；修改这些细节时，应优先更新 `docs/operations/codex_cleanup_task.md`。

## 1. 当前任务配置

```text
Task name: Weekly Cleanup Agent
Automation id: weekly-cleanup-agent
Schedule: Every Monday at 09:00
Timezone: America/New_York
Workspace: D:\Projects\email-ai-assistant
Prompt source: docs/operations/codex_cleanup_task.md
```

迁移说明（2026-07-21）：自动任务已临时暂停，因为 Codex 项目 ID 仍绑定旧的
C 盘工作区。用户在 Codex 中重新打开 `D:\Projects\email-ai-assistant` 后，必须将
`weekly-cleanup-agent` 重新绑定到新项目 ID，核对 Workspace 后再恢复为 `ACTIVE`。

Codex 本地配置文件通常位于：

```text
C:\Users\33506\.codex\automations\weekly-cleanup-agent\automation.toml
```

如果本地配置文件不存在，应在清理报告中标记为 `not found`，不要自行创建新的自动化任务，除非用户明确要求。

## 2. 执行前必须读取

```text
AGENTS.md
docs/constraints/tooling_constraints.md
docs/constraints/architecture_constraints.md
docs/constraints/linter_constraints.md
docs/constraints/mechanical_rule_translation.md
docs/operations/cleanup_agent.md
docs/operations/cleanup_agent_codex.md
docs/operations/codex_cleanup_task.md
```

如果某个文件不存在，必须在报告中标记为 `not found`。缺失文件本身可以作为发现项，但不得因此扩大任务范围或创建无关文件。

## 3. 执行规则来源

```text
项目边界：AGENTS.md
通用 cleanup 规则：docs/operations/cleanup_agent.md
Codex 自动化配置：docs/operations/cleanup_agent_codex.md
完整任务 Prompt：docs/operations/codex_cleanup_task.md
清理任务模板：docs/templates/cleanup_task_template.md
```

如果上述文件之间出现冲突，按以下顺序处理：

```text
1. AGENTS.md
2. docs/operations/cleanup_agent.md
3. docs/operations/codex_cleanup_task.md
4. docs/operations/cleanup_agent_codex.md
```

## 4. 推荐执行方式

Codex automation 启动后应读取 `docs/operations/codex_cleanup_task.md`，并按其中 Task Prompt 执行。该 Prompt 已包含：

必读文件
扫描目标
允许行为
禁止行为
推荐命令
输出格式
问题拆分格式
人工确认边界
```

如果 Codex 自动化环境不允许写入 `outputs/cleanup_report.md`，应直接在任务结果中输出完整 Markdown 报告。

## 5. 与 GitHub Actions 的关系

```text
Codex Cleanup Automation:
定期扫描当前工作区，读取项目文档和约束，生成清理报告，并提出小任务建议。

GitHub Cleanup Workflow:
如存在，仅用于在 GitHub 环境中运行同类只读扫描并上传报告。

CI Guardrails:
在 push 或 pull request 时运行测试，阻止违反约束的变更进入主分支。
```

任何自动化入口都必须遵守 `AGENTS.md` 和 `docs/operations/cleanup_agent.md`，不得自动修复、自动删除、自动提交或自动合并。

## 6. 维护要求

更新 Codex 自动任务规则时，优先修改 `docs/operations/codex_cleanup_task.md`，然后同步更新 Codex automation 的简短启动 Prompt，使其仍指向该源文件。

不要在 `AGENTS.md`、README 或本文件中复制完整任务 Prompt。入口文档只保留导航和红线。
