---
last_update: 2026-07-03
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: business_knowledge
---

# 邮件分类规则

## 目标

为当前邮件生成一个主分类和可选标签，帮助用户快速判断邮件性质。

## 主分类

- `customer_inquiry`：客户询盘、需求咨询、报价请求。
- `order_followup`：订单进度、交期、发货、收货确认。
- `payment`：付款、发票、账期、对账。
- `contract`：合同、协议、条款确认。
- `complaint`：投诉、质量异常、售后争议、缺陷、拒收、RCA 或纠正措施请求。
- `new_product_development`：新品开发、项目范围、成本目标、成本优化、样品/方案/可行性评估。
- `internal`：内部沟通、任务分配、审批。
- `marketing`：推广、展会、广告、无明确业务动作的信息。
- `unknown`：信息不足，无法判断。

## 第一版本地规则提示

- 内部审批、内部复核、内部审核类邮件优先归为 `internal`，除非同时触发 prompt injection、质量投诉或合同条款等更高风险分类。
- 展会资料、推广、广告、营销资料且没有明确业务动作的邮件归为 `marketing`。
- `marketing` 不应被默认当作客户询盘处理，避免生成不必要的业务承诺或报价动作。
- 新品开发或成本优化邮件即使提到质量标准，也不应仅凭 `quality` 单词归为 `complaint`；必须有投诉、缺陷、损坏、拒收、RCA、纠正措施等异常上下文才归入 `complaint`。

## 输出要求

- 只能选择一个主分类。
- 可以补充多个标签。
- 分类理由应简短，不能编造邮件中不存在的信息。


