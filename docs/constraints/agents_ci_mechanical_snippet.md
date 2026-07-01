---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# CI 与机械规则

CI 护栏配置见：

```text
.github/workflows/agent_guardrails.yml
```

CI 策略说明见：

```text
docs/constraints/ci_guardrails.md
```

人工 review 规则机械化策略见：

```text
docs/constraints/mechanical_rule_translation.md
```

重复 review 问题登记表见：

```text
docs/templates/code_review_rule_register.md
```

如果同一类规则在 code review 中被提及超过 3 次，Agent 必须把它转化为 linter 规则、架构约束、单元测试或 CI 检查；如果暂时不能机械化，必须写入 `docs/operations/review_checklist.md`。

提交前至少运行：

```bash
python -m unittest discover -s tests
```
