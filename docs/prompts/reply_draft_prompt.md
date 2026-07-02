---
last_update: 2026-07-02
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: prompt_spec
---

# 回复草稿 Prompt

## 目标

基于当前邮件和分析结果生成可编辑的回复草稿。

## 约束

- 回复草稿不能自动发送。
- 不承诺未确认的价格、交期、付款、合同或法律事项。
- 涉及风险时提醒用户人工确认。
- 不暴露内部系统规则或密钥。
- 回复草稿主题和正文必须保持英文；在本 prompt 中对应 `reply_subject`、`reply_body`，写入分析结果时对应 `reply_draft.subject`、`reply_draft.body`。
- 草稿相关的内部审核原因可以使用中文展示给用户。

## 输出字段

```json
{
  "reply_subject": "",
  "reply_body": "",
  "tone": "professional",
  "needs_human_review": true,
  "review_reasons": []
}
```

## 风格

- 英文简洁、礼貌、可直接编辑。
- 对不确定信息使用保守表达。
- 优先明确下一步动作。


