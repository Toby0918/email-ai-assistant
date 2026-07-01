---
last_update: 2026-06-29
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


