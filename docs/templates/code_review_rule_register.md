---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Code Review Rule Register

本文件用于记录 code review 中反复出现的问题，并判断是否应转化为 linter 规则、架构约束或 CI 检查。

## 使用规则

如果同一类 review 评论累计出现超过 3 次，必须考虑将其机械化。

处理路径：

```text
observed
→ candidate
→ active
→ deprecated
```

## 规则登记表

| ID | Review 问题 | 出现次数 | 状态 | 是否可机械化 | 目标规则 | 对应文档 | 对应测试 | 最近一次出现日期 |
|---|---:|---:|---|---|---|---|---|---|
| CR-001 | 示例：函数过长 | 0 | observed | 是 | 单函数不超过 50 行 | `docs/constraints/mechanical_rule_translation.md` | `tests/test_mechanical_rule_constraints.py` | N/A |
| CR-002 | 示例：前端不应出现 OpenAI key | 0 | active | 是 | 前端禁止密钥和 OpenAI 直接调用 | `docs/constraints/linter_constraints.md` | `tests/test_static_linter_constraints.py` | N/A |

## 单条规则记录模板

```text
ID:
Review 问题：
第一次出现：
第二次出现：
第三次出现：
出现次数：
状态：observed | candidate | active | deprecated
是否可机械化：是 | 否 | 暂不确定
机械化规则：
涉及目录：
涉及文件：
对应 docs：
对应 tests：
CI 是否覆盖：
备注：
```
