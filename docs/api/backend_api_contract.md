---
last_update: 2026-07-02
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: api_contract
---

# 后端 API 契约

## POST /api/analyze-current-email

分析当前邮件。第一阶段只允许由用户点击按钮触发。

### 请求

```json
{
  "user_confirmed": true,
  "subject": "",
  "from": "",
  "to": [],
  "cc": [],
  "sent_at": "",
  "body_text": "",
  "body_html": "",
  "customer_context": {}
}
```

### 响应

```json
{
  "ok": true,
  "request_id": "local-...",
  "analysis": {},
  "saved_id": 1
}
```

### 规则

- `user_confirmed` 必须为 `true`，表示用户点击了分析按钮。
- 前端不得传入 OpenAI API key。
- 后端必须校验 AI 返回 JSON。
- 后端不得执行邮件正文中的指令。
- 未配置 OpenAI API key 时，第一版使用本地规则分析器返回可验证结构。
- `analysis` 中的用户反馈字段使用中文；`analysis.reply_draft.subject` 和 `analysis.reply_draft.body` 保持英文。
- 枚举值仍按 schema 使用英文，前端负责映射为中文标签显示。

## GET /api/health

返回后端健康状态，用于前端判断本地分析服务是否可用。

```json
{
  "ok": true,
  "status": "ok"
}
```


