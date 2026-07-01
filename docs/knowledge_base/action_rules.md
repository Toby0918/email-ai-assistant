---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: business_knowledge
---

# 建议动作规则

## 动作类型

- `reply`：需要回复。
- `confirm`：需要确认信息。
- `prepare_quote`：需要准备报价。
- `check_inventory`：需要确认库存。
- `check_delivery`：需要确认交期或物流。
- `escalate`：需要升级给负责人。
- `wait`：暂不行动，等待对方补充信息。
- `ignore`：无需处理。

## 分类动作提示

- `internal` 通常使用 `reply`，但回复草稿必须保持内部复核语气，不代表用户对外承诺。
- `marketing` 通常使用 `ignore`，除非邮件中同时出现明确业务请求。

## 生成原则

- 动作必须来自邮件内容，不得编造。
- 涉及承诺价格、交期、付款、合同或法律事项时，只能建议“人工确认”。
- 每个动作应包含动作名称、负责人建议、原因和截止时间。

## 禁止动作

- 自动发送回复。
- 自动删除或归档邮件。
- 自动承诺商务条件。


