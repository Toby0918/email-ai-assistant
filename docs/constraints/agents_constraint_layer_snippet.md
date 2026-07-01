---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 约束层导航

Agent 在开始任何任务前，必须阅读并遵守工具与包约束层：

```text
docs/constraints/tooling_constraints.md
```

该文件定义当前允许使用的包、工具、模块职责、数据流边界、AI 输出约束和新增依赖审批规则。

如果任务涉及新增依赖、修改数据流、调整 AI 输出 JSON、接入真实邮箱、修改前端工具或改变安全边界，Agent 必须先填写：

```text
docs/templates/agent_task_brief_template.md
```

未经明确批准，不允许新增依赖、升级依赖、把 OpenAI API key 放入前端、直接连接真实邮箱、自动发送邮件、自动删除邮件或自动归档邮件。
