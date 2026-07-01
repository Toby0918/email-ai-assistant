---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: api_contract
---

# 前后端流程

## 点击分析流程

1. 前端检测当前邮件是否可读取。
2. 用户点击“分析此邮件”。
3. 前端整理当前邮件字段：`subject`、`from`、`to`、`sent_at`、`body_text` 或 `body_html`。
4. 前端调用 `POST /api/analyze-current-email`。
5. 后端清洗正文；如后端 AI 未配置，第一版使用本地规则分析器。
6. 后端校验 JSON schema。
7. 后端保存分析结果到 SQLite。
8. 前端展示结果。

## 密钥边界

- OpenAI API key 只存在于 Python 后端环境变量。
- 前端不保存、不显示、不转发 API key。

## 错误处理

- 后端不可用：提示启动本地服务。
- 邮件为空：提示无法分析空邮件。
- JSON 校验失败：提示分析失败，可重试。
- 触发安全规则：展示人工审核提示。


