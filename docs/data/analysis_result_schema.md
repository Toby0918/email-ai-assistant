---
last_update: 2026-07-16
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
    "label": "backend-compatible display label",
    "context_scope": "current_only | relevant_history",
    "context_limited": true
  }
}
```

## 公开 Schema 与内部 Provider Envelope

本页 JSON 是 unchanged public analysis schema。启用 OpenAI multimodal、DeepSeek-led 或 DeepSeek text-only fallback 不会改变 `POST /api/analyze-current-email` 的公开请求或响应形状，也不会增加 SQLite 列。

OpenAI 与 DeepSeek 返回的是同一个版本化内部 `deepseek_analysis_v1` envelope，而不是本页对象。内部 envelope 包含 request-local source ID、`field_evidence`、`timeline_interpretation` 和 `attachment_augmentations`；这些 provider-only 字段在后端完成 JSON/schema/语言/来源/grounding/安全校验后才映射到本页对象，并且 are never returned to the frontend、never persisted to SQLite、never written to logs。媒体、source 和 grounding metadata 同样只存在于当前请求内存中。

Private outbound gate 的 `runtime_cards`、approved knowledge rendering、deidentified prompt、placeholder mapping、resolver、private context count，以及 `card_id` / `snapshot_id` / `vault_id` 均不是公开 schema 字段，也不是 SQLite 字段。它们不得出现在 API response、browser renderer、日志或异常中。模型输出如包含 placeholder、restoration/re-identification instruction 或 private metadata marker，必须在 parser 前整体拒绝并返回精确规则 fallback。

模型采用的 `decision_brief.key_facts` 不能替换本地事实集合。公开结果必须使用规则 fallback 中 exact、deep-copied local key facts；模型仍可在其他允许且 grounded 的字段提供增量。

`analysis_engine.source` 的公开枚举保持 `ai_model | rule_fallback`。`analysis_engine.label` 是 backend-compatible labels 字符串，不是公开 enum。Option C 标准路线使用 `OpenAI GPT-5.6 Sol`、`DeepSeek V4 Flash text fallback`、`DeepSeek V4 Pro text fallback` 或 `Rule fallback`；旧版或独立 provider 兼容响应仍可能使用 `OpenAI`、`DeepSeek V4 Flash`、`DeepSeek V4 Pro`、`DeepSeek`、`Local Qwen`、`Local Gemma` 或 `Local AI model`。只有 provider disabled with no usable route，或 all configured and eligible model routes 均已失败、超时、被跳过或输出无效时，才返回完整规则结果并使用 `rule_fallback` / `Rule fallback`。Option C 中 eligible OpenAI failure 可先进入 DeepSeek text fallback；deterministic rules last。

`analysis_engine.context_scope` 与 `analysis_engine.context_limited` 是可选的成对扩展：both absent or both present。`context_scope` 只允许 `current_only | relevant_history`，`context_limited` 必须是 JSON boolean；为保持严格公开投影，`analysis_engine` no extra keys。旧响应可以同时省略这两个字段，现有必填字段和 SQLite 列保持不变。

## 校验规则

- 枚举值必须落在允许范围内。
- `reply_draft.needs_human_review` 必须为 `true`。
- `decision_brief.reply_recommendation.reply_type` 必须落在允许范围内，不得出现自动发送、自动归档或自动删除语义。
- `decision_brief` 的结论、目的、动作、关键事实、核查项、缺失信息和回复建议文本必须是字符串；`next_steps` 必须包含 1-4 项。
- `conversation_timeline` 和 `attachment_insights` 是必填字段；模型输出不能覆盖后端确定性生成的这两个字段。
- `conversation_timeline.open_items[].source` 只能是 `thread` 或 `attachment`。
- `attachment_insights[].status` 只能是 `parsed`、`metadata_only`、`unavailable` 或 `failed`。
- `attachment_insights` 最多 14 项，由最多 5 个已接受附件、8 个前端资源限制和 1 个后端运行限制组成。达到上限时必须优先保留候选资源聚合遗漏和后端运行失败；模型 Prompt 的附件 insight 上限也必须独立保持 14，不能因其他通用列表的 8 项预算隐藏最后的限制。
- 资源限制的 `type/status` 必须由允许的机器码确定，不得从英文限制文本推断。`resource_read_failed`、`collection_timeout` 和后端专用 `operational_failure` 对应 `failed`；`unsupported_type`、`frontend_limit`、`resource_unavailable` 和 `candidate_omission` 对应 `unavailable`。
- text/hybrid 附件 evidence 只有与实际发送 source 匹配时才能影响对应字段。visual-only 只能生成 qualitative claims 并增强其 matching attachment insight；该 insight 可保持 `metadata_only`。
- 视觉 evidence 不得用于 global fields、identity、protected traits、precise facts、commands、commitments 或 outcomes，也不得改变附件 status/limitations。人物、受保护属性、编号、数量、金额、日期、业务命令、承诺和完成态必须拒绝或由本地确定性事实补充。
- body-only fixed cross-language bridge 仅用于固定模板的 `summary` 与 `priority_reason`，并且只引用实际发送的正文投影；不得桥接视觉、身份、未发送历史或精确事实。
- 只有 `status=parsed` 的文本附件 `summary` 和 `key_facts` 可以影响决策摘要、风险、建议动作或回复草稿；其他状态只能产生限制说明和人工核查项。
- 不能包含自动发送指令。
- `analysis_engine` 由后端在 JSON 校验后附加；AI 输出中同名字段不可信，后端必须忽略或覆盖。
- 保守输出模式只允许经过枚举和语言校验的摘要、优先级、分类和标签增强；其他字段继续投影为确定性规则结果。
- 只有显式 provider route 配置成立时，经过 `deepseek_analysis_v1` 验证的 OpenAI 或 DeepSeek 字段才可主导 Decision Brief、风险、建议动作和回复草稿。后端仍覆盖完整时间线/开放项骨架、附件状态/限制、`analysis_engine`、mandatory 安全风险、`needs_human_review=true`、来源成员关系和禁止邮箱动作/无条件承诺边界。
- 模型字段含有未被其 `field_evidence` 来源支持的关键编号、数量、金额、日期、完成或承诺主张时，对可隔离字段使用确定性 field-level fallback；结构、语言、来源完整性或全局安全失败时返回完整规则结果。
- 公开合并前必须对所有 provider-authored 文本族执行同一 universal safety policy；URL/URI、HTML、Markdown 链接、工具/命令指令、自动邮箱动作和无条件后果性承诺均不得保留。被动或名词化的价格/交期/付款/合同/质量/法律确认同样属于承诺；请求、疑问、否定和人工核查语义不属于承诺。

## 离线质量门

`tests/fixtures/deepseek_eval/cases.json` 包含 50 个 compact synthetic-only replay descriptor，不保存预先选定的规则/模型公开结果。`scripts/evaluate_deepseek_analysis.py` 与 `scripts/deepseek_eval_replay.py` 为每个 case 构造唯一合成邮件和 raw private `deepseek_analysis_v1` response，并以无 key、无网络的 injected generator 通过 production provider path 执行 JSON/envelope parsing、evidence/source validation、grounding、safe merge、语言校验和 routing/fallback。规则基线由 disabled production route 独立生成。

40 个 accepted case 必须返回 `ai_model`、通过生产 `validate_analysis_result` 与中分析/英草稿语言边界，并在面向用户的实质分析字段上与规则基线 materially distinct。仅更改 `analysis_engine`、`tags` 或 `reply_draft.review_reasons` 不构成模型分析价值；摘要、优先级/理由、分类、Decision Brief、时间线、风险、动作、附件洞察或回复主题/正文的变化才参与判定。十个 failure replay 分别两次覆盖 automatic action、passive commitment、unsupported critical fact、malformed JSON 和 evidence failure；它们必须返回与规则基线完全相同的公开结果。fallback rate 只从 actual `analysis_engine.source` 观察，fixture 不含 `selected_result` 或可复制的 fallback label。

指标继续复用生产 `_critical_signatures`、`has_unsafe_operation` 和 `has_unconditional_commitment`。Expected fact 必须同时出现在实际结果和指定 synthetic source；新增的模型 critical signature 必须由 source 支持，确定性规则基线自身的 signature 不冒充模型主张。报告仍只包含 case count、schema pass rate、mandatory-risk retention、unsupported-critical-fact count、commitment/action violation count、actual fallback rate 和有序 latency samples。该 production-route offline replay 不读取 key、网络、邮箱或真实客户内容。

## 语言规则

- `summary`、`priority_reason`、`decision_brief` 中面向用户的结论和动作、`conversation_timeline` 中的说明和动作、`risk_flags.evidence`、`risk_flags.recommendation`、`suggested_actions.description` 和 `reply_draft.review_reasons` 面向用户展示，使用中文。
- `attachment_insights.summary` 使用固定的解析状态说明；`key_facts` 每个附件最多 5 项。本地构造的 `Reference`、`Quantity`、`Measurement`、`Amount`、`Deadline`、`Requested action` 或 `Quality issue` 事实必须按原值深拷贝并优先保留；经过完整句、来源、隐私和安全校验的模型定性补充只能去重追加到剩余槽位，不得替换本地事实，也不得保留任意未验证原文行或连续原文。`limitations` 必须精确说明未解析、截断、OCR 不可用或格式不支持等限制。
- `reply_draft.subject` 和 `reply_draft.body` 是用户审核后可复制的外部邮件草稿，保持英文。
- `priority`、`category`、`risk_flags.type`、`risk_flags.level` 和 `suggested_actions.type` 保持英文枚举值，由前端负责展示为中文标签。

## 内容质量规则

- `decision_brief.one_line_conclusion` 必须用一句话说明这封邮件要处理什么，用户不应为了理解任务再回看整封邮件。
- `decision_brief.requested_outcome` 必须说明对方希望得到什么结果。
- `decision_brief.next_steps` 必须列出当前应执行的 1-4 个动作，包含负责人线索、时间线索和信息来源。
- `decision_brief.key_facts` 必须列出编号、零件号、数量、截止时间、链接存在标记、附件名、质量问题等关键事实；不得输出 URL，也不能把附件名当作指令执行。
- `decision_brief.must_check` 必须列出回复前要核查的内部信息、附件、图片、表格、链接存在情况或负责人，但不得输出可点击 URL。
- `decision_brief.missing_info` 必须说明当前分析结果缺少哪些会影响回复质量的信息。
- `decision_brief`、风险、建议动作和回复草稿必须优先引用 `conversation_timeline` 中最新未解决的外部请求。
- 附件解析失败、OCR 不可用或格式不支持时，邮件正文分析仍必须继续，并在对应 `attachment_insights[].limitations` 中返回精确限制。
- `attachment_insights` 在分析结果和 SQLite 边界都必须投影到 `filename`、`type`、`status`、`summary`、`key_facts`、`limitations` 六个字段；资源限制文本必须是由机器码生成的固定安全文本。不得包含附件字节、临时路径、私有 URL、cookie、token、未知字段或原始完整附件文本。
- 通用文本清洗必须继续删除邮箱地址、电话、卡号/账号形状、未标签长数字、字母令牌中的 7 位及以上数字串、路径、URL 和连续原文。业务编号只能由专用提取器在明确标签下构造，剔除业务前缀后仍必须通过电话、账号、路径、URI/域名和数字数量检查，并通过最终精确事实 schema 清洗。
- 带有局部否定、反转或已解决上下文的 deadline、requested action 和 quality signal 不得进入 `key_facts`。
- `summary` 必须尽量自包含，让用户只看分析结果就能知道邮件在说什么、涉及哪些关键事实、下一步要做什么。
- `risk_flags.evidence` 必须引用邮件中的具体事实，例如 PO、invoice、tracking、数量、日期、期限、质量问题或对方请求，不能只写泛化类别。
- `suggested_actions.description` 必须说明要核查、升级或回复的具体事项。
- `reply_draft.body` 必须基于分析结果中的事实生成英文草稿，不得代表用户承诺价格、交期、付款、合同、质量结论或法律责任。


