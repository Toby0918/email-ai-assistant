---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: data_schema
---

# 样例邮件格式

第一阶段使用模拟邮件输入验证流程，不接入真实邮箱账号。

```json
{
  "subject": "Request for quotation",
  "from": "customer@example.test",
  "to": ["sales@example.test"],
  "cc": [],
  "sent_at": "2026-06-29T10:00:00Z",
  "body_text": "Hello, please quote 100 units and confirm delivery time.",
  "body_html": "",
  "customer_context": {}
}
```

## 样例规则

- 使用 `.test` 域名或明显虚构数据。
- 不使用真实客户姓名、邮箱、电话、地址或订单号。
- 真实邮件样本必须先脱敏，且经过单独确认后才能进入测试。

## Golden 样例集

本地评估样例保存在：

```text
tests/fixtures/sample_emails.json
```

该文件只允许存放虚构或脱敏后的邮件样例。每个样例包含：

```json
{
  "id": "delivery_followup",
  "email": {
    "subject": "Delivery date confirmation",
    "from": "customer@example.test",
    "body_text": "Please confirm delivery date for this order."
  },
  "expected": {
    "category": "order_followup",
    "priority": "normal",
    "risk_flags": ["delivery_risk"],
    "action_types": ["check_delivery"]
  }
}
```

对应测试文件：

```text
tests/test_golden_email_analysis.py
```

新增或修改分析规则时，应先更新 golden 样例或测试，再修改实现。


