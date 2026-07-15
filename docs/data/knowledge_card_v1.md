---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: quarterly
source_type: data_schema
---

# KnowledgeCardV1 Schema

`KnowledgeCardV1` 是公司通用知识的权威审查记录。它只能由本地脱敏候选生成，
采用严格 exact-key 校验，拒绝未知字段、占位符、身份残留、来源定位信息和原文
重合内容。Git、文档和测试仅可保存重新创作的合成示例。

## 顶层字段

| 字段 | 约束 |
| --- | --- |
| `schema_version` | 固定为 `KnowledgeCardV1` |
| `card_id` | 随机 UUID v4，不得复用 raw-vault record ID |
| `version` | 正整数，审批记录必须绑定同一版本 |
| `rule_type` | `classification`、`priority`、`risk`、`action`、`reply_guidance` |
| `language` | `zh-CN` 或 `en` |
| `applicability` | exact keys: `accountability`、`direction`、`categories` |
| `generic_rule` | 最多 1,000 字符的通用规则，无占位符、身份、精确事实或原文 |
| `normalized_signals` | 至多 12 个固定信号枚举，不得重复 |
| `enum_mapping` | 映射到现有 priority/category/risk/action 枚举 |
| `safe_reply_guidance` | 最多 1,000 字符的安全回复指导，不得承诺业务事实 |
| `evidence` | 仅保存会话数和交易对手数区间，不保存来源 ID 或哈希 |
| `privacy_check` | exact keys: `status=passed`、`checked_at` |
| `review` | creator、business、privacy、owner 四个固定槽位 |
| `lifecycle` | status、created_at、expires_at、review_due_at |

## 适用范围与映射枚举

`applicability.accountability` 只能是 `general`、`price`、`payment`、
`contract`、`quality`、`legal`；`direction` 只能是 `any`、`inbound`、
`outbound`、`thread`。`categories` 与 `enum_mapping` 必须复用分析结果合同中的
既有枚举，不得创建客户或员工专属分类。

`normalized_signals` 只允许以下值:

```text
quote_request, delivery_status, payment_terms, contract_language,
quality_issue, security_instruction, reply_requested, deadline_signal,
inventory_request, product_specification, complaint_signal
```

## 证据与审批

`conversation_bucket` 只能是 `1`、`2`、`3-5`、`6-10`、`11+`；
`counterparty_bucket` 只能是 `1`、`2-3`、`4-10`、`11+`。批准默认要求至少
`3-5` 会话区间和 `2-3` 交易对手区间。每个区间必须绑定到该规则实际复核的
`support_texts` 集合，不能继承批次内其他候选的汇总证据。一个经复核的支持集合
只生成一个候选；区间由本地 staging 对该集合计算，CLI 不接受操作者输入的证据
计数或阈值覆盖。`validate_non_verbatim` 必须检查同一个支持集合。

每个审批 exact keys 为 `actor_ref`、`role`、`approved_at`、`card_version`。
creator、business、privacy 必须由不同 actor 完成；price、payment、contract、
quality、legal 还要求独立 accountable owner。审批角色和 `card_version` 必须与
卡片绑定，schema 与 publisher 都会重新校验这些跨字段不变量、最低证据区间和
不超过 90 天的复核期限。候选及其加密支持材料从原 staging 时间起最多保留 30
天；`create` 不得重置到期时间。deprecated 或 revoked 卡片不得进入运行时快照。

## 禁止内容

卡片不得包含真实姓名、公司、域名、地址、电话、URL、文件名、路径、
Message-ID、订单/发票/追踪/物料/交易编号、精确金额、精确日期、来源哈希、
raw-vault ID、来源定位、恢复映射、prompt injection、客户/员工画像或原句。
`validate_non_verbatim` 会拒绝与脱敏候选共享的长拉丁词组、中文片段或规范化
连续片段。

## 运行时投影

发布时仅将批准且未到期的卡片投影为 `RuntimeKnowledgeCardV1`。运行时投影只含
card ID/version、规则类型、语言、适用范围、通用规则、规范化信号、枚举映射和
安全回复指导；不含证据、审批人、隐私检查、生命周期或任何 authority 写句柄。
