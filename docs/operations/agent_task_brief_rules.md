---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Agent 执行前任务模板规则

## 适用范围

任何新增功能、修复、重构、文档变更、Prompt 调整或安全规则调整开始前，Agent 必须先填写任务模板：

```text
docs/templates/agent_task_brief_template.md
```

## 执行要求

如果任务目标、非目标、涉及范围、安全边界或验收标准不清楚，Agent 必须先提出澄清问题，不得直接修改代码或文档。

任务模板只用于规划和约束执行，不得用于存放真实邮件正文、API key、OAuth token、邮箱凭据、真实报价、未脱敏合同或其他敏感资料。
