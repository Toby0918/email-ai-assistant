---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Review Checklist

本文件记录暂时不能完全机械化，但 code review 时必须人工检查的事项。

## 1. 产品边界

```text
[ ] 是否仍然符合第一阶段“用户点击按钮后分析当前邮件”的边界？
[ ] 是否没有引入自动发送、删除、归档邮件？
[ ] 是否没有默认接入真实邮箱？
```

## 2. AI 输出质量

```text
[ ] 摘要是否准确反映邮件内容？
[ ] 优先级是否符合 priority_rules.md？
[ ] 风险标签是否符合 risk_flags.md？
[ ] 建议动作是否没有越权承诺？
[ ] 回复草稿是否需要人工确认？
```

## 3. 安全边界

```text
[ ] 是否没有泄露密钥？
[ ] 是否没有把邮件正文写进日志？
[ ] 是否没有把真实邮件写进 docs 或 tests？
[ ] 是否正确防护 Prompt Injection？
```

## 4. 是否需要转成机械规则

每次 review 后都应判断：

```text
[ ] 这个问题是否重复出现？
[ ] 是否已经出现 3 次？
[ ] 是否可以变成 linter 规则？
[ ] 是否需要更新 docs/templates/code_review_rule_register.md？
```
