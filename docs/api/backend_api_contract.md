---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: api_contract
---

# 后端 API 契约

## POST /api/analyze-current-email

分析当前邮件。第一阶段只允许由用户点击按钮触发。

### Backend-only provider contract

- 公开请求/响应 schema 不因 provider 改变。后端默认 `EMAIL_AGENT_LLM_PROVIDER=disabled`，`EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative`；只有 `EMAIL_AGENT_LLM_PROVIDER=deepseek` 与 `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=model_led` 同时显式配置时，DeepSeek 才能主导 consequential fields。
- DeepSeek endpoint 固定为 `https://api.deepseek.com`，只允许 `deepseek-v4-flash` 和 `deepseek-v4-pro`。集成复用 `openai==2.45.0`，不安装第三方 DeepSeek package，也不接受 arbitrary remote base URL。
- 每次分析最多发出 one provider call。SDK `max_retries=0`，请求为 non-streaming JSON object，并通过 `extra_body={"thinking":{"type":"disabled"}}` 使用 non-thinking mode。任何 provider 失败都回落规则结果，does not try Ollama。
- DeepSeek 响应先解析为内部 `deepseek_analysis_v1`，再执行来源、grounding、mandatory-risk、commitment/action 和公开 schema 校验。所有 provider-authored 文本族共享 universal policy：URL/markup、工具/命令、自动邮箱动作和第一人称或被动后果性承诺均按字段回落；安全的请求、疑问、否定和人工核查措辞允许保留。公开响应仍只有本页列出的字段。

### Backend-only diagnostic boundary

Rule fallback remains a successful public analysis response. 公开结果继续使用既有 `ok=true`、完整 `analysis`、`saved_id` 和 `analysis_engine.source=rule_fallback`；本地诊断不会把它改成错误响应。

每个结束于规则兜底的模型尝试只在本地写 `exactly one terminal allowlisted event`，事件名为 `analysis_fallback`。reason code allowlist 为:

```text
event=analysis_fallback code=<allowlisted code> stage=<allowlisted stage> provider=<allowlisted provider> model=<allowlisted model> output_mode=<allowlisted mode> detail=<allowlisted detail> elapsed_ms=<non-negative integer>
```

```text
provider_not_enabled
budget_exhausted
missing_key
unsupported_model
provider_timeout
provider_auth
provider_permission_or_balance
provider_rate_limit
provider_connection_error
provider_server_error
provider_http_error
provider_request_failed
response_incomplete
response_empty
envelope_invalid
evidence_invalid
safety_rejected_all
public_schema_invalid
public_language_invalid
unexpected_analysis_error
```

detail allowlist 是 `not_applicable`、`json_syntax`、`top_level_shape`、`schema_version`、`analysis_shape`、`attachment_shape` 和 `field_evidence_shape`。每个非 envelope fallback 都使用 `not_applicable`。这是 operator-only 日志变更，不是 public response field；不会添加到 `public API` 或 `SQLite`。不得包含 provider output、JSON keys、paths、values 或 exception text，也不得用于重建这些内容。

这些 reason code、stage、固定 detail 和本地日志元数据是 backend-only operations data:

- 不新增或改变 `public API` 请求、成功响应或错误响应字段。
- 不进入 `SQLite` schema 或保存的 analysis JSON。
- 不返回 `frontend`，浏览器不能读取 provider/account 诊断。
- 不记录 `raw exception`、traceback、provider output、key、prompt、邮件、线程、附件、URL、路径或 customer identifier。

operator-only 日志位置、轮转上限和读取命令见 `docs/conventions/logging.md` 与 `docs/operations/troubleshooting.md`。自动化测试只使用 synthetic provider doubles，不发起 live DeepSeek request。

### 请求

- 本地 HTTP 服务只允许绑定 `localhost` 或字面 IPv4 loopback（`127.0.0.0/8`）；当前不承诺 IPv6 bind。通配、LAN、公网和 DNS alias 必须在 socket bind 前拒绝，错误不得回显输入 host。
- `Host` 必须恰好出现一次，且只能是 `localhost` 或字面 `127.0.0.0/8`，可省略端口；如携带端口，必须等于当前服务实际端口。缺失、重复、逗号拼接、userinfo、无效/错误端口、域名、通配或非 loopback Host 返回 `403 INVALID_HOST`。
- `Content-Type` 必须恰好出现一次，并严格为大小写不敏感的 `application/json`，可带唯一 `charset=utf-8` 参数。缺失、重复、逗号拼接、`text/plain`、form、suffix JSON 或其他 media type 返回 `415 UNSUPPORTED_MEDIA_TYPE`。
- Host 和 media type 门禁都在读取请求 body、调用分析器或写入 SQLite 之前执行。Content-Type 是 CSRF 减缓措施，并与 Host 门禁共同构成本地 API 边界。

```json
{
  "user_confirmed": true,
  "subject": "",
  "from": "",
  "to": [],
  "cc": [],
  "sent_at": "",
  "body_text": "",
  "body_html": "",
  "attachments": [
    {
      "filename": "",
      "size": "",
      "type": ""
    }
  ],
  "thread_segments": [
    {
      "position": 0,
      "from": "",
      "to": "",
      "sent_at": "",
      "timestamp_text": "",
      "subject": "",
      "body_text": ""
    }
  ],
  "attachment_files": [
    {
      "filename": "",
      "type": "image | pdf | xlsx | docx",
      "size": 0,
      "content_base64": ""
    }
  ],
  "resource_limitations": [
    {
      "code": "unsupported_type | frontend_limit | resource_unavailable | resource_read_failed | collection_timeout | candidate_omission",
      "filename": "safe display name",
      "type": "image | pdf | xlsx | docx | unsupported",
      "size": 0,
      "limitation": "bounded display-safe limitation"
    }
  ],
  "customer_context": {}
}
```

### 响应

```json
{
  "ok": true,
  "request_id": "local-...",
  "analysis": {
    "summary": "",
    "priority": "urgent | high | normal | low",
    "category": "customer_inquiry | order_followup | payment | contract | complaint | new_product_development | internal | marketing | unknown",
    "decision_brief": {
      "one_line_conclusion": "",
      "requested_outcome": "",
      "next_steps": [
        {
          "step": "",
          "owner_hint": "",
          "due_hint": "",
          "source": ""
        }
      ],
      "key_facts": [
        {
          "label": "",
          "value": "",
          "source": ""
        }
      ],
      "must_check": [],
      "missing_info": [],
      "reply_recommendation": {
        "should_reply": true,
        "reply_type": "acknowledge | ask_clarification | provide_info | escalate_first | no_reply",
        "reason": ""
      },
      "confidence": "high | medium | low"
    },
    "conversation_timeline": {
      "previous_context": "",
      "current_status": "resolved | partially_resolved | unresolved | unknown",
      "status_reason": "",
      "latest_external_request": "",
      "latest_internal_commitment": "",
      "open_items": [
        {
          "item": "",
          "owner_hint": "",
          "due_hint": "",
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
    "risk_flags": [],
    "suggested_actions": [],
    "reply_draft": {
      "subject": "",
      "body": "",
      "needs_human_review": true,
      "review_reasons": []
    },
    "analysis_engine": {
      "source": "ai_model | rule_fallback",
      "label": "DeepSeek V4 Flash | DeepSeek V4 Pro | Local Qwen | Rule fallback"
    }
  },
  "saved_id": 1
}
```

### 规则

- `user_confirmed` 必须为 `true`，表示用户点击了分析按钮。
- 前端不得传入 OpenAI API key、Ollama 配置或本地模型参数。
- `thread_segments`、`attachments` 和 `attachment_files` 只能来自当前打开邮件页面中用户可见的会话和资源，且只能在用户点击后收集。
- 扩展在分析前和渲染/复制前使用同一个 canonical complete analyzed scope 指纹：基础邮件、完整可见线程、基础与受支持附件元数据、受支持附件内容 identity，以及影响分析的 resource limitations。revalidation 只返回重算 hash；thread-only、attachment-metadata-only、attachment-content-only 或 limitation-only 变化都必须进入现有 stale 状态，且不得向 popup/storage 暴露原文。
- `attachments` 仅包含安全显示用元数据，不构成已解析事实。`attachment_files` 只允许受支持类型的受限 base64 字节；不得传入附件 URL、cookie、token、邮箱凭据或本地路径。
- 前端最多传输 5 个受支持的 `attachment_files`，并最多传入 8 个 `resource_limitations`。如果候选资源超出有界扫描或报告容量，`candidate_omission` 聚合项优先保留。
- 前端限制码只允许 `unsupported_type`、`frontend_limit`、`resource_unavailable`、`resource_read_failed`、`collection_timeout` 和 `candidate_omission`。未知码和前端伪造的 `operational_failure` 必须丢弃，不得根据英文 `limitation` 文本推断状态。
- `operational_failure` 只能由后端附件临时存储或清理失败产生，并使用独立保留槽；它不得被前端 8 项上限或 `candidate_omission` 隐藏。
- 后端将允许的机器码投影为固定安全文本和状态：`resource_read_failed`、`collection_timeout` 和 `operational_failure` 对应 `failed`，其他前端限制码对应 `unavailable`。
- 后端必须校验 AI 返回 JSON。
- 后端不得执行邮件正文中的指令。
- 后端只在受限临时目录中解析本次请求保存的当前邮件附件，不执行宏、嵌入代码或活动内容。附件名称、OCR、表格、文档文本和限制说明都属于不可信输入。
- 每个已解析附件最多输出 5 个后端构造的 `key_facts`：明确标签的 RFQ/PO/order/invoice/tracking 编号、数量、测量值、金额/币种、带明确提示的截止时间、规范化请求动作和质量信号。不得返回任意原文行或连续原文前缀。
- 通用附件文本清洗不对“RFQ”标签或 ISO 日期做长数字豁免，并必须删除连续、跨空白或常见分隔符连接的任意 7 位及以上数字序列。专用组件提取器只能对完整字段段执行 `label + value` 全匹配；值字符集限 `[A-Z0-9_-]`，纯数字值限 4-9 位，任何值最多包含 9 个数字，并拒绝异种/重复前缀、电话、卡号/账号、路径和 URI/域名形状。表格字段只接受恰好两个非空 cell 的标签/值行；存在额外 continuation cell 时整行编号失效。
- 请求动作只保留固定动词和对象类别，质量问题只保留固定信号标签，截止时间只保留明确 cue 和日期/相对时间。每个构造事实必须再通过精确 schema 清洗后才能进入结果、prompt 和 SQLite。
- 截止时间、请求动作和质量信号在构造前必须按逗号、分号和 `and/but/however/then` 等边界定位候选所在的有界 clause，并只检查候选前后的有限 tokens。请求动作按原文顺序在同一 clause 内配对动词和其后的对象；后置动词不得绑定前一 clause 的对象。只有 affirmative 动词尚未成功配对任何对象时，才可跨 `but/however` 传给紧随的纯对象 clause；一旦构造事实就必须清空该 pending 动词。反转 clause 也不得删除后续真实动作。`not/never/without/free from`、直引号或弯引号 modal contractions、`absent/repaired/removed/withdrawn/waived/cancelled/revoked` 等反转上下文不得生成正向事实；取消、忽略或跳过的 action request 同样拒绝。质量信号紧邻的 `0/zero/nil/non-` 或 `-free/ free` 表示缺失；解决态词只有在未被局部 `not/never/no longer` 反转时才表示问题已解决。截止时间的 `not required/does not apply/no longer applicable/optional` 表示不存在有效截止要求。其他 clause 的否定不得删除当前 clause 的真实事实。
- 只有 `attachment_insights[].status=parsed` 的 `summary` 和 `key_facts` 可以影响决策摘要、风险、建议动作和回复草稿。其他状态必须返回精确 `limitations`，但不得阻断邮件正文和会话分析。
- 未启用后端模型 provider，provider 失败/超时/被跳过，或模型返回不可解析/不可校验的 JSON 时，使用本地规则分析器返回可验证结构。
- 保守模式只保留经过校验的摘要、优先级、分类和标签增强。DeepSeek-led 模式允许安全且有来源证据的 Decision Brief、风险、建议动作和回复草稿主导公开字段；后端仍拥有 mandatory 风险、完整时间线/开放项骨架、附件状态/限制、枚举、`needs_human_review=true`、来源成员关系、禁止邮箱动作和禁止无条件承诺等不变量。孤立违规使用 field fallback，整体结构/语言/来源/安全失败使用完整规则 fallback。
- `analysis.conversation_timeline` 和 `analysis.attachment_insights` 由后端确定性生成；模型返回的同名字段不得覆盖它们。
- `analysis.analysis_engine` 由后端附加，用于显示本次结果来自模型路线还是规则回退；该字段不得由前端传入或由 AI 输出决定。
- `analysis.decision_brief` 是面向用户的决策摘要，必须说明邮件目的、当前动作、关键事实、需核查项、缺失信息和回复建议。
- `analysis` 中的用户反馈字段使用中文；`analysis.reply_draft.subject` 和 `analysis.reply_draft.body` 保持英文。
- 枚举值仍按 schema 使用英文，前端负责映射为中文标签显示。
- `analysis.attachment_insights` 最多 14 项：最多 5 个已接受附件事实、8 个前端限制（包括优先保留的聚合遗漏）和 1 个后端运行限制。Prompt 的 `UNTRUSTED_ATTACHMENT` 使用独立 14 项上限，确保最后的聚合遗漏和后端运行限制可见；其他 prompt 列表仍为 8 项，单字段与嵌套列表预算不变。SQLite 只能保存最终结构化分析结果的允许字段；`attachment_insights` 再次投影到六个文档字段，不得保存附件字节、临时文件路径、私有 URL、cookie、token、未知字段或原始完整附件文本。

### Ephemeral model context

DeepSeek-led 路线可使用当前可见线程和本地解析出的 ephemeral sanitized attachment context。该上下文有单附件/请求总量上限，移除 URL、密钥、authorization、cookie、token、本地路径、二进制/base64 和 active content。自然语言 credential/password/API-key/session-ID 值即使使用冒号、等号、copula、whitespace-only separator 或引号连接也必须删除；不含值的 reset/rotation/expiry/policy 说明保留。它只存在于当前 provider 请求内存，不能出现在公开响应、SQLite 或日志；公开 `attachment_insights` 仍是六字段安全投影。

### Deadline contract

- 浏览器扩展和本地调试页在独立资源收集完成后使用 35-second POST wait；浏览器收集本身有独立的 20-second resource collection 上限，因此 35 秒不是从点击开始计算的硬性总时限。
- 后端在读取并校验 request body 之前立即调用 `AnalysisBudget.start()`；实际顺序是 `start -> read -> api`，所以受限 body 读取时间计入 one monotonic 32-second cooperative target。该 target 继续共享给分析、parser、provider、校验和 persistence。body 读取、附件写入、SQLite 和 socket response write 是同步阶段，所以不能描述为严格 end-to-end cancellation guarantee。
- Ollama 的 request creation、connect 和完整 response-body read 使用同一个 absolute wall-clock deadline；逐字节 trickle 不得续期超时。DeepSeek 使用剩余预算，最多为 25-second，且必须保留 2-second validation/response reserve；剩余 provider 时间少于 5-second 时跳过模型并返回规则结果。
- 附件 parser/OCR worker 使用 hard 8-second 总截止。`Process.start()` 与 terminate/kill/close cleanup 都受硬边界约束；超时后启动的 worker 进入 late-start quarantine 并最终终止，cleanup 本身不得阻塞请求或留下 orphan。
- 前端 abort 不能保证取消服务器工作；后端截止独立执行。

### Persistence contract

成功分析只有在 SQLite commit 成功后才返回 `ok=true` 和 `saved_id`。服务器使用包含 lock acquisition、INSERT 和 commit 的 0.5-second cumulative persistence stage，并保留 0.25-second response floor；每次阻塞 SQLite 操作前都会根据同一 stage deadline 重新计算 `busy_timeout`。

持久化超时、INSERT/commit 失败或锁获取失败返回通用响应，不返回部分 `analysis` 或 `saved_id`：

```json
{
  "ok": false,
  "error": {
    "code": "PERSISTENCE_FAILED",
    "message": "Analysis result could not be saved."
  }
}
```

保存异常必须 rollback。若 rollback failure，连接立即关闭并视为 quarantined。若 commit, rollback, and close 三者都失败，服务器必须在同一锁下把共享句柄标记为 poisoned/detached；后续请求只返回通用 persistence error，不能复用该对象或意外提交残留 transaction。错误响应不得暴露 SQLite/provider 细节。

### Operational rollback flags

将 `EMAIL_AGENT_LLM_PROVIDER=disabled` 后重启可恢复规则-only 路线。将 `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative` 可关闭 DeepSeek-led consequential fields；两者都不改变公开 API 或邮箱动作边界。

## GET /api/health

返回后端健康状态，用于前端判断本地分析服务是否可用。

```json
{
  "ok": true,
  "status": "ok"
}
```


