---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Cleanup Agent

本文件定义后台清理 Agent 的职责、边界、定时运行方式和输出要求。

后台清理 Agent 的目的不是自动重构项目，而是定期扫描项目卫生问题，生成独立、可 review、可回滚的小修复任务。

## 1. 核心原则

Cleanup Agent 只能做低风险维护任务。它不得改变产品边界、不得接入真实邮箱、不得修改安全规则、不得自动发送邮件。

允许：

```text
扫描超长文件
扫描超长函数
扫描缺少测试的模块
扫描 TODO / FIXME
扫描过期 draft 文档
扫描缺少 YAML front matter 的 docs 文档
扫描疑似误提交的临时文件、缓存文件、数据库文件
生成清理报告
为每类问题提出独立修复建议
```

禁止：

```text
自动删除业务代码
自动删除 docs 正文
自动修改 Prompt 行为
自动放宽 linter 或架构约束
自动接入真实邮箱
自动发送、删除、归档邮件
自动提交或合并代码
把多个无关清理混成一个大 PR
```

## 2. 推荐运行频率

第一阶段建议每周一次。  
不建议每天运行，以免产生过多低价值噪声。

当前推荐使用 Codex 自动化任务运行，规范见：

```text
docs/operations/cleanup_agent_codex.md
docs/operations/codex_cleanup_task.md
```

如项目中存在 `.github/workflows/cleanup_agent.yml`，它只能作为可选报告通道或 CI 补充，不得改变本文件定义的只读扫描边界。

## 3. 标准执行流程

```text
1. 读取 AGENTS.md。
2. 读取 docs/constraints/ 下的约束文件。
3. 运行 scripts/maintenance_scan.py。
4. 运行 tests/ 下已有 guardrail 测试。
5. 根据扫描结果生成 cleanup report。
6. 将问题按类型拆分为小任务。
7. 对每个小任务填写 docs/templates/cleanup_task_template.md。
8. 如果需要修改代码，每个问题单独生成 PR 或单独提交。
```

## 4. 清理任务拆分规则

必须拆分：

```text
超长文件清理
超长函数拆分
缺失测试补充
过期文档处理
TODO/FIXME 处理
日志违规修复
静态约束失败修复
架构约束失败修复
```

不得把以上问题混在一个提交里。

## 5. 输出文件

Cleanup Agent 的报告建议输出到：

```text
outputs/cleanup_report.md
```

该文件属于本地临时输出，不应提交到版本库，除非用户明确要求保留历史报告。

## 6. PR 标题规范

```text
chore(cleanup): split oversized backend module
chore(cleanup): add missing tests for email cleaner
chore(cleanup): update stale draft docs
chore(cleanup): remove committed temporary files
```

## 7. 人工确认边界

以下情况必须人工确认：

```text
删除文件
删除文档段落
修改 Prompt
修改安全规则
修改 API contract
修改 database schema
修改前端邮箱接入逻辑
新增依赖
放宽任何测试或 linter 规则
```

## 8. 与机械规则的关系

如果 Cleanup Agent 连续 3 次发现同类问题，应把该问题登记到：

```text
docs/templates/code_review_rule_register.md
```

如果该问题可以机械化，应加入：

```text
docs/constraints/mechanical_rule_translation.md
tests/
.github/workflows/agent_guardrails.yml
```
