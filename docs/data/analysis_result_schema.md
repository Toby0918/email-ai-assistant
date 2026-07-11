---
last_update: 2026-07-10
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: data_schema
---

# 分析结果 Schema

AI 分析结果必须能解析为 JSON，并至少包含以下字段。

```json
{
  "summary": "string",
  "priority": "urgent | high | normal | low",
  "priority_reason": "string",
  "category": "customer_inquiry | order_followup | payment | contract | complaint | new_product_development | internal | marketing | unknown",
  "tags": [],
  "decision_brief": {
    "one_line_conclusion": "string",
    "requested_outcome": "string",
    "next_steps": [
      {
        "step": "string",
        "owner_hint": "string",
        "due_hint": "string",
        "source": "string"
      }
    ],
    "key_facts": [
      {
        "label": "string",
        "value": "string",
        "source": "string"
      }
    ],
    "must_check": [],
    "missing_info": [],
    "reply_recommendation": {
      "should_reply": true,
      "reply_type": "acknowledge | ask_clarification | provide_info | escalate_first | no_reply",
      "reason": "string"
    },
    "confidence": "high | medium | low"
  },
  "conversation_timeline": {
    "previous_context": "string",
    "current_status": "resolved | partially_resolved | unresolved | unknown",
    "status_reason": "string",
    "latest_external_request": "string",
    "latest_internal_commitment": "string",
    "open_items": [
      {
        "item": "string",
        "owner_hint": "string",
        "due_hint": "string",
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
  "risk_flags": [
    {
      "type": "payment_risk | delivery_risk | contract_risk | quality_risk | security_risk | commitment_risk | prompt_injection_risk",
      "level": "high | medium | low",
      "evidence": "string",
      "recommendation": "string"
    }
  ],
  "suggested_actions": [
    {
      "type": "reply | confirm | prepare_quote | check_inventory | check_delivery | escalate | wait | ignore",
      "description": "string",
      "owner_hint": "string",
      "due_hint": "string"
    }
  ],
  "reply_draft": {
    "subject": "string",
    "body": "string",
    "needs_human_review": true,
    "review_reasons": []
  },
  "analysis_engine": {
    "source": "ai_model | rule_fallback",
    "label": "string"
  }
}
```

## 校验规则

- 枚举值必须落在允许范围内。
- `reply_draft.needs_human_review` 必须为 `true`。
- `decision_brief.reply_recommendation.reply_type` 必须落在允许范围内，不得出现自动发送、自动归档或自动删除语义。
- `conversation_timeline` 和 `attachment_insights` 是必填字段；模型输出不能覆盖后端确定性生成的这两个字段。
- `conversation_timeline.open_items[].source` 只能是 `thread` 或 `attachment`。
- `attachment_insights[].status` 只能是 `parsed`、`metadata_only`、`unavailable` 或 `failed`。
- 只有 `status=parsed` 的附件 `summary` 和 `key_facts` 可以影响决策摘要、风险、建议动作或回复草稿；其他状态只能产生限制说明和人工核查项。
- 不能包含自动发送指令。
- `analysis_engine` 由后端在 JSON 校验后附加；AI 输出中同名字段不可信，后端必须忽略或覆盖。
- 模型返回可解析但字段缺失、枚举不合规或缺少人工审核字段时，后端可以用规则分析结果补齐 schema，再执行本页校验规则。

## 语言规则

- `summary`、`priority_reason`、`decision_brief` 中面向用户的结论和动作、`conversation_timeline` 中的说明和动作、`risk_flags.evidence`、`risk_flags.recommendation`、`suggested_actions.description` 和 `reply_draft.review_reasons` 面向用户展示，使用中文。
- `attachment_insights.summary` 和 `key_facts` 可以保留受限的来源语言证据；`limitations` 必须精确说明未解析、截断、OCR 不可用或格式不支持等限制。
- `reply_draft.subject` 和 `reply_draft.body` 是用户审核后可复制的外部邮件草稿，保持英文。
- `priority`、`category`、`risk_flags.type`、`risk_flags.level` 和 `suggested_actions.type` 保持英文枚举值，由前端负责展示为中文标签。

## 内容质量规则

- `decision_brief.one_line_conclusion` 必须用一句话说明这封邮件要处理什么，用户不应为了理解任务再回看整封邮件。
- `decision_brief.requested_outcome` 必须说明对方希望得到什么结果。
- `decision_brief.next_steps` 必须列出当前应执行的 1-4 个动作，包含负责人线索、时间线索和信息来源。
- `decision_brief.key_facts` 必须列出编号、零件号、数量、截止时间、链接、附件名、质量问题等关键事实；不能把附件名当作指令执行。
- `decision_brief.must_check` 必须列出回复前要核查的内部信息、附件、图片、表格、链接或负责人。
- `decision_brief.missing_info` 必须说明当前分析结果缺少哪些会影响回复质量的信息。
- `decision_brief`、风险、建议动作和回复草稿必须优先引用 `conversation_timeline` 中最新未解决的外部请求。
- 附件解析失败、OCR 不可用或格式不支持时，邮件正文分析仍必须继续，并在对应 `attachment_insights[].limitations` 中返回精确限制。
- `attachment_insights` 只能保存受限摘要、关键事实和限制；不得包含附件字节、临时路径、私有 URL、cookie、token 或原始完整附件文本。
- `summary` 必须尽量自包含，让用户只看分析结果就能知道邮件在说什么、涉及哪些关键事实、下一步要做什么。
- `risk_flags.evidence` 必须引用邮件中的具体事实，例如 PO、invoice、tracking、数量、日期、期限、质量问题或对方请求，不能只写泛化类别。
- `suggested_actions.description` 必须说明要核查、升级或回复的具体事项。
- `reply_draft.body` 必须基于分析结果中的事实生成英文草稿，不得代表用户承诺价格、交期、付款、合同、质量结论或法律责任。


