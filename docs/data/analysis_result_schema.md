---
last_update: 2026-07-02
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
  "category": "customer_inquiry | order_followup | payment | contract | complaint | internal | marketing | unknown",
  "tags": [],
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
  }
}
```

## 校验规则

- 枚举值必须落在允许范围内。
- `reply_draft.needs_human_review` 必须为 `true`。
- 不能包含自动发送指令。

## 语言规则

- `summary`、`priority_reason`、`risk_flags.evidence`、`risk_flags.recommendation`、`suggested_actions.description` 和 `reply_draft.review_reasons` 面向用户展示，使用中文。
- `reply_draft.subject` 和 `reply_draft.body` 是用户审核后可复制的外部邮件草稿，保持英文。
- `priority`、`category`、`risk_flags.type`、`risk_flags.level` 和 `suggested_actions.type` 保持英文枚举值，由前端负责展示为中文标签。


