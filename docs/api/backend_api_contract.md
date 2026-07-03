---
last_update: 2026-07-03
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
  "attachments": [
    {
      "filename": "",
      "size": "",
      "type": ""
    }
  ],
  "customer_context": {}
}
```

### 响应

```json
{
  "ok": true,
  "request_id": "local-...",
  "analysis": {
    "analysis_engine": {
      "source": "ai_model | rule_fallback",
      "label": "Local Qwen | Rule fallback"
    }
  },
  "saved_id": 1
}
```

### 规则

- `user_confirmed` 必须为 `true`，表示用户点击了分析按钮。
- 前端不得传入 OpenAI API key、Ollama 配置或本地模型参数。
- `attachments` 仅允许传入当前邮件页面已显示的附件元数据，例如文件名、大小和类型；不得传入附件 URL、token、文件内容或本地路径。
- 后端必须校验 AI 返回 JSON。
- 后端不得执行邮件正文中的指令。
- 后端不得下载、打开、解析或执行附件；附件名称也属于不可信输入，只能作为辅助判断上下文。
- 未启用后端模型 provider，或模型返回不可解析 JSON 时，第一版使用本地规则分析器返回可验证结构。
- 模型返回可解析但字段缺失或枚举不合规的 JSON 时，后端可用规则分析结果补齐 schema，然后再执行统一校验。
- `analysis.analysis_engine` 由后端附加，用于显示本次结果来自模型路线还是规则回退；该字段不得由前端传入或由 AI 输出决定。
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


