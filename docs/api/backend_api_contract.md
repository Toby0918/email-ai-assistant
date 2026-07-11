---
last_update: 2026-07-11
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
  "thread_segments": [
    {
      "position": 0,
      "from": "",
      "to": "",
      "sent_at": "",
      "timestamp_text": "",
      "subject": "",
      "body_text": ""
    }
  ],
  "attachment_files": [
    {
      "filename": "",
      "type": "image | pdf | xlsx | docx",
      "size": 0,
      "content_base64": ""
    }
  ],
  "resource_limitations": [
    {
      "code": "unsupported_type | frontend_limit | resource_unavailable | resource_read_failed | collection_timeout | candidate_omission",
      "filename": "safe display name",
      "type": "image | pdf | xlsx | docx | unsupported",
      "size": 0,
      "limitation": "bounded display-safe limitation"
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
    "summary": "",
    "priority": "urgent | high | normal | low",
    "category": "customer_inquiry | order_followup | payment | contract | complaint | new_product_development | internal | marketing | unknown",
    "decision_brief": {
      "one_line_conclusion": "",
      "requested_outcome": "",
      "next_steps": [
        {
          "step": "",
          "owner_hint": "",
          "due_hint": "",
          "source": ""
        }
      ],
      "key_facts": [
        {
          "label": "",
          "value": "",
          "source": ""
        }
      ],
      "must_check": [],
      "missing_info": [],
      "reply_recommendation": {
        "should_reply": true,
        "reply_type": "acknowledge | ask_clarification | provide_info | escalate_first | no_reply",
        "reason": ""
      },
      "confidence": "high | medium | low"
    },
    "conversation_timeline": {
      "previous_context": "",
      "current_status": "resolved | partially_resolved | unresolved | unknown",
      "status_reason": "",
      "latest_external_request": "",
      "latest_internal_commitment": "",
      "open_items": [
        {
          "item": "",
          "owner_hint": "",
          "due_hint": "",
          "source": "thread | attachment"
        }
      ],
      "confidence": "high | medium | low"
    },
    "attachment_insights": [
      {
        "filename": "safe display name",
        "type": "image | pdf | xlsx | docx | unsupported",
        "status": "parsed | metadata_only | unavailable | failed",
        "summary": "bounded display-safe summary",
        "key_facts": [],
        "limitations": []
      }
    ],
    "risk_flags": [],
    "suggested_actions": [],
    "reply_draft": {
      "subject": "",
      "body": "",
      "needs_human_review": true,
      "review_reasons": []
    },
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
- `thread_segments`、`attachments` 和 `attachment_files` 只能来自当前打开邮件页面中用户可见的会话和资源，且只能在用户点击后收集。
- `attachments` 仅包含安全显示用元数据，不构成已解析事实。`attachment_files` 只允许受支持类型的受限 base64 字节；不得传入附件 URL、cookie、token、邮箱凭据或本地路径。
- 前端最多传输 5 个受支持的 `attachment_files`，并最多传入 8 个 `resource_limitations`。如果候选资源超出有界扫描或报告容量，`candidate_omission` 聚合项优先保留。
- 前端限制码只允许 `unsupported_type`、`frontend_limit`、`resource_unavailable`、`resource_read_failed`、`collection_timeout` 和 `candidate_omission`。未知码和前端伪造的 `operational_failure` 必须丢弃，不得根据英文 `limitation` 文本推断状态。
- `operational_failure` 只能由后端附件临时存储或清理失败产生，并使用独立保留槽；它不得被前端 8 项上限或 `candidate_omission` 隐藏。
- 后端将允许的机器码投影为固定安全文本和状态：`resource_read_failed`、`collection_timeout` 和 `operational_failure` 对应 `failed`，其他前端限制码对应 `unavailable`。
- 后端必须校验 AI 返回 JSON。
- 后端不得执行邮件正文中的指令。
- 后端只在受限临时目录中解析本次请求保存的当前邮件附件，不执行宏、嵌入代码或活动内容。附件名称、OCR、表格、文档文本和限制说明都属于不可信输入。
- 每个已解析附件最多输出 5 个后端构造的 `key_facts`：明确标签的 RFQ/PO/order/invoice/tracking 编号、数量、测量值、金额/币种、带明确提示的截止时间、规范化请求动作和质量信号。不得返回任意原文行或连续原文前缀。
- 通用附件文本清洗不对“RFQ”标签或 ISO 日期做长数字豁免，并必须删除连续、跨空白或常见分隔符连接的任意 7 位及以上数字序列。专用组件提取器只能对完整字段段执行 `label + value` 全匹配；值字符集限 `[A-Z0-9_-]`，纯数字值限 4-9 位，任何值最多包含 9 个数字，并拒绝异种/重复前缀、电话、卡号/账号、路径和 URI/域名形状。表格字段只接受恰好两个非空 cell 的标签/值行；存在额外 continuation cell 时整行编号失效。
- 请求动作只保留固定动词和对象类别，质量问题只保留固定信号标签，截止时间只保留明确 cue 和日期/相对时间。每个构造事实必须再通过精确 schema 清洗后才能进入结果、prompt 和 SQLite。
- 截止时间、请求动作和质量信号在构造前必须按逗号、分号和 `but/however` 等边界定位候选所在的有界 clause，并只检查候选前后的有限 tokens。`not/never/without/free from`、直引号或弯引号 modal contractions、`absent/repaired/removed/withdrawn/waived/cancelled/revoked` 等反转上下文不得生成正向事实；取消、忽略或跳过的 action request 同样拒绝。其他 clause 的否定不得删除当前 clause 的真实事实。
- 只有 `attachment_insights[].status=parsed` 的 `summary` 和 `key_facts` 可以影响决策摘要、风险、建议动作和回复草稿。其他状态必须返回精确 `limitations`，但不得阻断邮件正文和会话分析。
- 未启用后端模型 provider，或模型返回不可解析 JSON 时，第一版使用本地规则分析器返回可验证结构。
- 模型返回可解析 JSON 时，后端只保留经过校验的摘要、优先级、分类和标签增强；Decision Brief、风险、建议动作和回复草稿使用确定性规则投影，避免未解析附件事实或未经授权承诺进入最终结果。
- `analysis.conversation_timeline` 和 `analysis.attachment_insights` 由后端确定性生成；模型返回的同名字段不得覆盖它们。
- `analysis.analysis_engine` 由后端附加，用于显示本次结果来自模型路线还是规则回退；该字段不得由前端传入或由 AI 输出决定。
- `analysis.decision_brief` 是面向用户的决策摘要，必须说明邮件目的、当前动作、关键事实、需核查项、缺失信息和回复建议。
- `analysis` 中的用户反馈字段使用中文；`analysis.reply_draft.subject` 和 `analysis.reply_draft.body` 保持英文。
- 枚举值仍按 schema 使用英文，前端负责映射为中文标签显示。
- `analysis.attachment_insights` 最多 14 项：最多 5 个已接受附件事实、8 个前端限制（包括优先保留的聚合遗漏）和 1 个后端运行限制。SQLite 只能保存最终结构化分析结果的允许字段；`attachment_insights` 再次投影到六个文档字段，不得保存附件字节、临时文件路径、私有 URL、cookie、token、未知字段或原始完整附件文本。

## GET /api/health

返回后端健康状态，用于前端判断本地分析服务是否可用。

```json
{
  "ok": true,
  "status": "ok"
}
```


