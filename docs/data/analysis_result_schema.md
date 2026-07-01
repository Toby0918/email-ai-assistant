---
last_update: 2026-07-01
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


