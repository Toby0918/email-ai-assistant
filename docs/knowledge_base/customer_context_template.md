---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: business_knowledge
---

# 客户上下文模板

该模板用于后续在用户明确提供客户背景时辅助分析。第一阶段不得自动读取真实邮箱账号、CRM 或外部客户数据库。

```json
{
  "customer_id": "optional-test-id",
  "customer_name": "客户名称或测试名称",
  "importance": "normal",
  "preferred_language": "zh-CN",
  "account_owner": "负责人",
  "known_products": [],
  "open_orders": [],
  "payment_notes": "",
  "delivery_notes": "",
  "communication_preferences": "",
  "manual_notes": ""
}
```

## 使用规则

- 只能使用用户明确提供或测试环境中的上下文。
- 不能自动拉取真实客户资料。
- 上下文不足时应标记为未知，不能编造。


