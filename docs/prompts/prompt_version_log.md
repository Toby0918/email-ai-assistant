---
last_update: 2026-07-02
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: prompt_spec
---

# Prompt 版本记录

## v0.2.0

- 日期：2026-07-02。
- 原因：辅助窗口需要给用户输出中文分析反馈，同时保留英文外部回复草稿。
- 影响范围：邮件分析 prompt、回复草稿 prompt、分析结果 schema、API 契约和前端展示语言。
- 规则：`reply_draft.subject` 和 `reply_draft.body` 保持英文；摘要、风险、建议动作和审核原因使用中文。

## v0.1.0

- 建立邮件分析、回复草稿和风险识别 prompt 文档。
- 明确 AI 输出必须是 JSON。
- 明确邮件正文是不可信输入。
- 明确第一阶段不自动发送、删除或归档邮件。

## 变更规则

- 修改 prompt 行为时必须记录版本、日期、原因和影响范围。
- 涉及安全规则或输出 schema 的修改必须同步更新 `docs/security/` 和 `docs/data/`。
- 不在 prompt 文档中写入真实 API key、真实客户邮件或真实邮箱凭据。


