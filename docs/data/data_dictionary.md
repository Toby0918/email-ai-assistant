---
last_update: 2026-07-02
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: data_schema
---

# 数据字典

## EmailInput

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `subject` | string | 邮件主题 |
| `from` | string | 发件人 |
| `to` | string[] | 收件人 |
| `cc` | string[] | 抄送人 |
| `sent_at` | string | 发送时间，建议 ISO 8601 |
| `body_text` | string | 纯文本正文 |
| `body_html` | string | HTML 正文，可为空 |

## AnalysisResult

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `summary` | string | 邮件摘要 |
| `priority` | string | 优先级 |
| `category` | string | 主分类 |
| `risk_flags` | array | 风险点 |
| `suggested_actions` | array | 建议动作 |
| `reply_draft` | object | 回复草稿 |
| `needs_human_review` | boolean | 是否需要人工审核 |

## 语言约定

- 分析反馈字段使用中文，包含摘要、优先级原因、风险证据、风险建议、建议动作说明和人工审核原因。
- 回复草稿字段 `reply_draft.subject` 和 `reply_draft.body` 保持英文。
- 枚举字段保持英文值，前端显示时映射为中文标签。


