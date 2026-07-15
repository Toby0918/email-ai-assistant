---
last_update: 2026-07-15
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

## 5. Authorized mailbox and vault review

```text
[ ] 管理员 CLI 是否仍默认关闭、无 schedule、无 browser/normal-backend hook？
[ ] 是否仍限制单一授权账号、固定 endpoint、24 calendar months 和 fingerprint-confirmed scan？
[ ] IMAP 是否只使用 LIST、只读 EXAMINE、UID SEARCH 和 BODY.PEEK？
[ ] attachment approval 是否双审、最多 50 个且不在首遍下载二进制？
[ ] vault 是否位于项目/OneDrive/temp 之外，并通过 NTFS + BitLocker 证据？
[ ] 索引、日志、状态和报告是否只含 content-free metadata/code/count？
[ ] 是否明确 raw snapshot is not a legal archive 且 no automatic second backup？
[ ] Windows namespace/path race 是否只声明 best-effort mitigation？
```

## 6. Private knowledge and evaluation review

```text
[ ] candidate 是否满足 3 conversations/2 counterparties、business/privacy dual approval 和必要的 owner approval？
[ ] rejected/expired/deprecated/revoked card 是否不会进入签名只读 snapshot？
[ ] snapshot 缺失、过期、签名错误或解密失败是否回退 generic rule fallback？
[ ] DeepSeek 是否只收本地脱敏当前可见内容和最多 8 张/4,000 字符批准卡片？
[ ] disclosure 是否没有 local-only 或 zero-retention 承诺？
[ ] 预算是否仍为 browser/backend/provider/minimum 15/13/10/5 秒且无 retry？
[ ] 私有评估是否默认 human_judge_unavailable 且 no automatic production model switch？
[ ] aggregate report 是否不含 case、prompt、provider output、path、ID 或 sample？
```

## 7. Incident stop and rollback review

遇到授权、fingerprint、UIDVALIDITY、flags、身份残留、密钥、签名、schema、
safety、grounding、延迟或泄漏异常时执行 `incident stop`，不得尝试扩大范围或
自动修复。确认 `EMAIL_AGENT_LLM_PROVIDER=disabled`，停止管理员 CLI，撤下
runtime snapshot 访问以恢复 generic rule fallback；revoke/rewrap 必须由现场
操作者明确确认，且永不修改源邮箱。
