---
last_update: 2026-06-30
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# CI Guardrails

本文件定义项目的 CI 护栏策略。  
CI 的目标不是替代人工 review，而是把已经明确的工程规则变成自动检查。

## 1. CI 文件位置

CI 配置文件：

```text
.github/workflows/agent_guardrails.yml
```

## 2. CI 运行时机

CI 应在以下场景运行：

```text
pull_request
push to main
push to master
```

## 3. CI 检查内容

CI 至少运行以下检查：

```text
tests/test_architecture_constraints.py
tests/test_static_linter_constraints.py
tests/test_mechanical_rule_constraints.py
tests/test_maintenance_scan.py
tests/test_generate_project_status.py
python -m unittest discover -s tests
python scripts/maintenance_scan.py
```

## 4. 检查目标

CI 必须防止以下问题进入主分支：

```text
架构分层被破坏
前端直接调用 OpenAI
前端保存或暴露密钥
出现自动发送、删除、归档邮件能力
后端业务代码使用裸 print()
后端业务代码使用 traceback.print_exc()
出现裸 except
backend/*.py 单文件超过 300 行
backend/*.py 单函数超过 50 行
docs/ 下 Markdown 缺少 YAML front matter
后台清理 Agent 无法生成报告
项目状态日志生成器无法生成 Agent 可读快照
维护扫描脚本发现高风险项目卫生问题
```

## 5. 失败处理原则

如果 CI 失败，Agent 必须先阅读失败信息。  
每条失败信息应尽量包含：

```text
❌ 什么错
✅ 怎么改
📖 去哪里看
```

Agent 不得通过以下方式修复 CI：

```text
删除测试
注释测试
放宽规则但不更新文档
跳过失败检查
把违规代码移到未被检查的目录
```

如果确实需要修改规则，必须同步更新：

```text
AGENTS.md
docs/constraints/architecture_constraints.md
docs/constraints/linter_constraints.md
docs/constraints/mechanical_rule_translation.md
docs/constraints/ci_guardrails.md
tests/
```

## 6. 版本说明

CI 使用 Python 3.12.13。  
SQLite 运行时版本由 CI 环境提供，CI 会打印 SQLite runtime 版本用于排查，但第一阶段不把 SQLite runtime 精确版本作为强制失败条件。
