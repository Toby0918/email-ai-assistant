---
last_update: 2026-07-23
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Tooling Constraints and Package Responsibilities

本文件是项目的“约束层”。  
它告诉 Agent 当前项目允许使用哪些包、工具和目录结构，以及每个工具的正确用途。  
Agent 在新增功能、修改代码、调整 Prompt、修改数据结构或引入依赖前，必须先阅读本文件。

## 1. 约束层目标

本文件用于降低 Agent 犯错概率，尤其是以下错误：

- 把前端当作后端使用。
- 把 OpenAI API key 放进前端。
- 随意升级依赖版本。
- 为小功能随意引入新包。
- 用错误工具处理错误任务。
- 把真实邮件、真实密钥、真实客户信息写入日志、测试数据或文档。
- 未经确认就接入真实邮箱或自动发送邮件。
- 让 AI 输出自由文本，而不是结构化 JSON。

## 2. 规则优先级

当规则冲突时，按以下顺序执行：

```text
AGENTS.md
→ docs/constraints/tooling_constraints.md
→ docs/constraints/architecture_constraints.md
→ docs/security/*.md
→ docs/data/*.md
→ docs/api/*.md
→ docs/prompts/*.md
→ docs/knowledge_base/*.md
→ README.md
→ 代码注释
```

如果本文件与 `AGENTS.md` 冲突，以 `AGENTS.md` 为准。  
如果工具约束与可执行架构约束冲突，应先停止修改并同步更新两份约束文档和对应测试。  
如果业务文档与安全文档冲突，以安全文档为准。  
如果需求不清楚，Agent 必须先提出澄清问题，不得自行扩大范围。

## 3. 当前允许的后端技术栈

本项目后端技术栈固定如下。未经明确批准，不允许升级版本或替换工具。

| 工具 / 包 | 固定版本 | 主要用途 | 禁止用途 |
|---|---:|---|---|
| Python | 3.12.13 | 后端运行环境、业务逻辑、测试 | 不允许使用更高版本 |
| SQLite | 3.50.4 | 本地分析结果存储、调试缓存、轻量数据持久化 | 不作为企业级远程数据库；不存储真实敏感邮件全文，除非后续明确授权 |
| beautifulsoup4 | 4.15.0 | 清洗 HTML 邮件正文、去除标签和样式噪声 | 不用于业务规则判断；不用于解析 AI JSON |
| openpyxl | 3.1.5 | 导出本地调试或评估用 Excel 报表 | 不用于核心数据存储；不用于读取真实邮箱 |
| openai | 2.45.0 | 后端调用 AI 模型，生成结构化邮件分析结果 | 不允许在前端直接调用；不允许输出未经校验的自由文本 |
| python-dotenv | 1.2.2 | 本地加载 `.env` 中的后端环境变量 | 不允许把 `.env` 提交到版本库 |
| pypdf | 6.14.2 | 后端提取受限 PDF 文本 | 不解析加密、可执行或未知二进制内容 |
| python-docx | 1.2.0 | 后端提取受限 DOCX 段落和表格文本 | 不运行嵌入式活动内容 |
| Pillow | 12.3.0 | 后端检查图片并为 OCR 准备输入 | 不在前端处理图片内容 |
| pytesseract | 0.3.13 | 后端可选 OCR | Tesseract 缺失时仅降级 OCR，不能阻断规则兜底 |
| cryptography | 49.0.0 | 用于单独授权的项目外 vault/私有知识 AES-256-GCM、Ed25519，以及 startup-only 只读知识快照验证/解密 | 不用于请求期密钥或文件访问，不替代 BitLocker/DPAPI，不允许更高版本或其他 crypto package |

本地 Ollama/Qwen/Gemma 属于后端运行环境能力，不是新增 Python 依赖。`EMAIL_AGENT_OLLAMA_MODEL` 默认是 `qwen3.6:latest`，可选择 `gemma4`；调用失败或输出无效时必须回落到本地规则分析器。`EMAIL_AGENT_OLLAMA_BASE_URL` 只能使用 `localhost` 或字面 loopback IP，不得包含 userinfo，不得指向远程 HTTP(S) 主机；远程 provider 需要单独架构批准和隐私评审。

专用 DeepSeek provider 复用已固定版本的 OpenAI-compatible `openai==2.45.0` SDK，不新增 Python 依赖。禁止安装 third-party DeepSeek SDK，也禁止提供可配置的 arbitrary remote base URL；DeepSeek endpoint 必须由后端代码固定，密钥只允许通过后端 `DEEPSEEK_API_KEY` 提供。

显式 OpenAI 多模态路线同样复用 `openai==2.45.0`，模型 allowlist 只有 `gpt-5.6-sol`。OpenAI uses the fixed official endpoint；禁止 `EMAIL_AGENT_OPENAI_BASE_URL`、arbitrary remote base URL、前端 endpoint 或 SDK retry。安全配置默认是 `EMAIL_AGENT_LLM_PROVIDER=disabled`、`EMAIL_AGENT_OPENAI_MODEL=gpt-5.6-sol`、`EMAIL_AGENT_OPENAI_TIMEOUT_SECONDS=35` 和 `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled`；文本 fallback allowlist 只有 `disabled` 与 `deepseek`。

## Authorized mailbox transport policy

单独授权的 mailbox ingest 只允许标准库 `imaplib`、`ssl`、`email`、
`getpass`、`sqlite3`、`ctypes` 和 `hmac`。不引入第三方 IMAP SDK。只有
`scripts/manage_mailbox_vault.py` 可导入 `backend.mailbox_ingest`；该 CLI 只可
由管理员手动运行，处理一个授权账号、固定 `imap.exmail.qq.com:993` 和滚动
24 个日历月。There is no arbitrary IMAP command passthrough。

允许的 transport operation 只有：

```text
`LIST`
`EXAMINE`
`UID SEARCH`
`UID FETCH`
`BODY.PEEK`
```

`UID FETCH` 必须有界，并且 body section 必须使用 `BODY.PEEK`。禁止
`BODY[]` 以及任何可能设置 `\\Seen` 或改变 flags 的形式。

以下 operation 和 transport 在 isolated package、CLI 和所有 runtime code
中一律禁止：

```text
`STORE`
`APPEND`
`COPY`
`MOVE`
`EXPUNGE`
`CREATE`
`DELETE`
`RENAME`
`SUBSCRIBE`
`UNSUBSCRIBE`
`SMTP`
`BODY[]`
```

禁止 background polling、schedule、IDLE loop、任意 host/account/date range、
任意 command argument、password flag/env/`.env` source 和 mailbox mutation。
浏览器扩展、local debug、`backend.email_agent`、loopback API、cleanup agent
及定时 workflow 不得导入或调用 mailbox ingest。

Vault crypto 只可在 Task 2 dependency tests 先 RED 后加入精确
`cryptography==49.0.0` pin。Windows DPAPI/BitLocker 设施必须 lazy-load 并通过
injected probes 测试，使非 Windows CI import/collect 不访问 host。Recovery
rewrap 必须使用 crash-recoverable staged activation/reconciliation，不得声称
cross-volume atomicity。

私有知识 normal-service 例外仅限 startup-only read path：显式启用后由
`scripts/run_local_debug.py` 调用一次 fail-closed bootstrap，通过 CurrentUser DPAPI
短暂打开 authority envelope、验证并解密一个外部只读 snapshot。请求处理、health、
SQLite、frontend、diagnostics 和 background work 不得调用 crypto、DPAPI 或 snapshot
reader；不得 reload、poll、hot-update 或暴露 snapshot status。

ADR 0008 additionally permits a contract-only post-click ingress package,
`backend.current_evidence`. It validates `CurrentClickEvidenceV1` and accepts only
an opaque append capability. Normal runtime receives no read, get, list, search,
query, path, key, repository, raw-vault, authority-store, mailbox, polling, or
reload tool through this seam. The package performs no persistence itself and
does not change the HTTP or public SQLite schema. Future issue #18 owns any
orchestration and evidence-inbox implementation.

Future issue #17 may add administrator-triggered incremental synchronization to
the existing CLI only. Every run remains manual, read-only, fixed to
`imap.exmail.qq.com:993`, and gated by the exact current inventory fingerprint;
ADR 0008 and issue #10 add no `sync` command, scheduler, poller, browser route,
or normal API hook.

### Repository placement tooling boundary

`backend.project_layout` implements Issue #30 with Python standard-library
`dataclasses`, `enum`, `pathlib`, `stat`, and typing facilities only. It adds no
dependency. `RepositoryPlacement` validates stable, non-reparse directory identity,
the exact Managed Container `email_ai_assistant\main` relationship, or an explicit
Standalone Verification synthetic/temporary state root. `OperationalLayout`
returns only absolute ordinary runtime, data, temporary, log, artifact, worktree,
and non-secret configuration paths.

Issue #33 adds `ProtectedLocationPolicy` without adding a dependency or mutation
capability. The value has no public constructor for arbitrary roots. It is
derived only from freshly revalidated Managed/Standalone placement or the
separately validated flat-layout compatibility path. Managed policy keeps the
single Project Container root; it does not reconstruct a narrower set from the
seven ordinary layout paths. A path inside a Managed zone but outside exact
`main` fails closed instead of becoming a flat compatibility root.

The package may perform read-only path metadata inspection. It must not create,
write, move, copy, rename, replace, remove, or delete a path; call a mailbox or
provider; read a credential, key, raw vault, recovery store, private store, or
private content; change ACL/volume/host security; or expose such a capability in
its returned values. The flat-layout adapter is a temporary compatibility mapper,
not a third final placement mode. Only the reviewed private-knowledge storage and
snapshot policies, private-evaluation repository path policy, mailbox vault and
sales-policy location policies, and standalone verification module may import the
project-layout package. Public HTTP, browser, ordinary runtime, environment,
configuration, and CLI surfaces cannot supply `protected_roots` or
`project_container`. Launcher routing, container audit, migration, Issue #32,
and Issues #34 through #40 remain out of scope.

本地邮件分析 HTTP 服务沿用 Python 标准库 `ThreadingHTTPServer`，不得为 Host/Content-Type 门禁新增 HTTP 框架。服务 bind 只支持 `localhost` 或字面 IPv4 `127.0.0.0/8`；分析 POST 必须在读 body 前校验单一 loopback Host 和单一 JSON media type。

## 4. 依赖管理规则

1. 新增依赖前，必须先说明为什么现有工具不能满足需求。
2. 新增依赖必须更新 `requirements.txt`、相关 docs 和测试。
3. 不允许为单个小功能引入大型框架，除非已有明确架构决策记录。
4. 不允许在没有批准的情况下引入 ORM、任务队列、后台调度器、浏览器自动化工具或真实邮箱 SDK；上述管理员例外只使用标准库 `imaplib`，不得引入第三方邮箱 SDK。
5. 不允许混用多个功能重叠的包，例如同时引入多个 HTML parser、多个 Excel 库、多个 HTTP 框架。
6. 不允许绕过版本锁定安装最新版依赖。

## 5. 后端模块职责

后端目录建议为：

```text
backend/email_agent/
  __init__.py
  config.py
  logging_config.py
  email_cleaner.py
  analyzer.py
  llm_client.py
  database.py
  exporter.py
  api.py
```

### config.py

职责：

- 读取环境变量。
- 校验必要配置是否存在。
- 提供统一配置对象。

禁止：

- 不得硬编码 OpenAI API key。
- 不得读取前端文件中的密钥。
- 不得把密钥写入日志。

### logging_config.py

职责：

- 配置项目日志格式。
- 控制日志级别。
- 避免重复配置 logger。

禁止：

- 不得输出真实邮件正文。
- 不得输出 API key、OAuth token、邮箱凭据。
- 不得用裸 `print()` 作为业务日志。

### email_cleaner.py

职责：

- 清洗 HTML 邮件正文。
- 提取可读纯文本。
- 降低签名、引用历史、样式和无关链接噪声。

禁止：

- 不得判断最终业务优先级。
- 不得调用 OpenAI。
- 不得修改原始邮件语义。

### analyzer.py

职责：

- 组织邮件分析流程。
- 构造 AI 输入。
- 校验 AI 输出 JSON。
- 根据 docs 中的分类、优先级、风险规则约束输出。

禁止：

- 不得绕过 JSON 校验。
- 不得让邮件正文成为系统指令。
- 不得自动代表用户承诺价格、交期、付款、合同或法律事项。

### llm_client.py

职责：

- 封装后端 AI 调用，包括 OpenAI 或用户明确确认的本地 Ollama/Qwen。
- 控制模型参数。
- 处理 API 调用错误。

禁止：

- 不得从前端接收或暴露 OpenAI API key。
- 不得允许前端直接调用 Ollama、Qwen 或其他本地模型端点。
- 不得在异常信息中输出敏感内容。
- 不得返回未校验的自由文本给业务层。

### database.py

职责：

- 管理 SQLite 连接。
- 创建和维护本地数据表。
- 保存邮件分析结果和调试记录。

禁止：

- 不得保存未授权的真实邮箱数据。
- 不得把数据库文件提交到版本库。
- 不得在业务代码中散落 SQL；SQL 应集中在该模块或明确的数据访问层。

### exporter.py

职责：

- 使用 openpyxl 导出本地调试或评估用 Excel 报表。
- 将已保存的分析结果转换为人工可读表格。

禁止：

- 不得作为主数据存储。
- 不得导出真实敏感邮件内容，除非后续明确授权并经过脱敏。

### api.py

职责：

- 提供前端调用的本地后端接口。
- 接收当前邮件内容。
- 返回结构化分析结果。

禁止：

- 不得默认暴露公网访问。
- 不得接收或返回前端密钥。
- 不得加入自动发送、删除、归档邮件功能。

## 6. 前端工具边界

第一阶段前端路线必须明确选择一种：

```text
Outlook Add-in
Google Workspace Add-on
Chrome / Edge browser extension
local_debug_page
```

前端职责：

- 识别当前打开的邮件。
- 展示“分析此邮件”按钮。
- 将当前邮件必要字段发送给本地 Python 后端。
- 仅在“分析此邮件”点击路径中，传输当前打开邮件页面可见的受支持附件资源。
- 展示结构化分析结果。
- 允许用户复制或参考回复草稿。

前端禁止：

- 不得保存、硬编码或暴露 OpenAI API key。
- 不得直接调用 OpenAI API、Ollama API、Qwen 或任何本地模型端点。
- 不得自动发送邮件。
- 不得自动删除或归档邮件。
- 不得后台扫描整个邮箱。
- 不得默认读取真实邮箱账号，除非后续单独确认。
- 不得把邮件正文写入浏览器控制台日志。
- 不得在点击前收集资源、读取其他邮件或文件夹，或把附件二进制、私有下载 URL、cookie 或 token 传入 SQLite、日志或前端持久化存储。

## 7. docs/ 工具边界

`docs/` 是结构化知识库，不是垃圾箱。

允许存放：

- 产品范围。
- 邮件分类规则。
- 优先级规则。
- 风险标签。
- 回复规范。
- Prompt 规范。
- 数据结构。
- API 约定。
- 安全规则。
- ADR 技术决策。
- 测试和部署清单。

禁止存放：

- 真实客户邮件全文。
- OpenAI API key。
- 邮箱密码。
- OAuth token。
- 真实报价。
- 未脱敏合同。
- 未脱敏客户资料。
- 本地数据库文件。
- 大量临时输出。

## 8. 数据流约束

第一阶段标准数据流如下：

```text
当前打开邮件
→ 辅助窗口提取必要字段
→ 用户点击“分析此邮件”
→ 前端调用本地 Python 后端
→ 后端清洗正文
→ 后端调用 OpenAI 或后端本地 Ollama/Qwen（可选，默认关闭）
→ 后端校验结构化 JSON
→ 后端保存 SQLite
→ 可选内部 `CurrentClickEvidenceV1` 仅经 opaque append capability 单向提交
→ 前端展示结果
→ 用户人工确认后使用回复草稿
```

禁止数据流：

```text
前端 → OpenAI
前端 → Ollama/Qwen/local model endpoint
后台扫描全邮箱 → AI
AI 草稿 → 自动发送
真实邮件全文 → 日志
真实邮件全文 → docs/
真实密钥 → 前端
frontend/normal runtime → backend.mailbox_ingest
backend.email_agent → backend.mailbox_ingest
mailbox ingest → SMTP or write IMAP command
raw vault → Codex/DeepSeek/Git/log/public SQLite/docs/tests/status
normal runtime → evidence inbox read/search/list/query
normal runtime → evidence path/key/repository/raw-vault/authority capability
```

## 9. AI 输出约束

AI 分析结果必须是结构化 JSON。  
禁止只返回自由文本。

最低字段必须与 `docs/data/analysis_result_schema.md` 保持一致，建议结构如下：

```json
{
  "summary": "",
  "priority": "urgent | high | normal | low",
  "priority_reason": "",
  "category": "customer_inquiry | order_followup | payment | contract | complaint | new_product_development | internal | marketing | unknown",
  "tags": [],
  "decision_brief": {
    "one_line_conclusion": "",
    "requested_outcome": "",
    "next_steps": [],
    "key_facts": [],
    "must_check": [],
    "missing_info": [],
    "reply_recommendation": {
      "should_reply": true,
      "reply_type": "acknowledge | ask_clarification | provide_info | escalate_first | no_reply",
      "reason": ""
    },
    "confidence": "high | medium | low"
  },
  "risk_flags": [],
  "suggested_actions": [],
  "reply_draft": {
    "subject": "",
    "body": "",
    "needs_human_review": true,
    "review_reasons": []
  }
}
```

Agent 修改 AI 输出结构时，必须同步更新：

```text
docs/data/analysis_result_schema.md
docs/prompts/analyzer_prompt.md
docs/api/backend_api_contract.md
docs/constraints/architecture_constraints.md
tests/
```

## 10. 工具选择规则

### 清洗 HTML 邮件正文

使用：

```text
beautifulsoup4
```

不得使用：

```text
正则表达式硬解析复杂 HTML
OpenAI 直接清洗原始 HTML
前端 DOM 文本作为唯一可信结果
```

### 保存分析结果

使用：

```text
SQLite
```

不得使用：

```text
Excel 作为主数据库
JSON 文件作为长期主存储
浏览器 localStorage 保存敏感邮件内容
```

### 导出调试报表

使用：

```text
openpyxl
```

不得使用：

```text
手写 xlsx 二进制文件
把 Excel 当作核心业务数据库
```

### 读取配置

使用：

```text
python-dotenv
环境变量
```

不得使用：

```text
硬编码密钥
把密钥写进前端
把密钥写进 docs/
```

### 调用 AI

使用：

```text
openai 包
本地 Ollama HTTP API（仅 backend/email_agent/llm_client.py，且默认关闭）
后端封装 llm_client.py
```

不得使用：

```text
前端直接调用 OpenAI
前端直接调用 Ollama/Qwen
非正规 API 渠道
把邮件正文当作系统指令
```

## 11. 新增工具审批模板

如果 Agent 认为必须新增工具或依赖，必须先填写：

```text
工具名称：
用途：
为什么现有工具不够：
替代方案：
安全影响：
新增文件：
需要更新的 docs：
需要新增的测试：
是否影响部署：
```

未填写前，不得修改 `requirements.txt`。

## 12. 执行前检查

Agent 每次开始任务前，必须确认：

```text
[ ] 已阅读 AGENTS.md。
[ ] 已阅读本文件。
[ ] 已阅读相关 docs/ 文件。
[ ] 没有新增未批准依赖。
[ ] 没有把单独授权的管理员导入例外扩展到浏览器、正常后端、调度器、第二账号、任意 host 或任意时间范围。
[ ] 没有把密钥放进前端。
[ ] 没有把真实邮件写入日志、docs、tests 或 outputs。
[ ] 涉及 AI 输出时，已确认 JSON schema。
```

## 13. Remote provider outbound gate

- OpenAI multimodal and DeepSeek `conservative`/`model_led` requests must pass the same backend-only private outbound gate before any provider call. OpenAI media remains separately screened and is not represented as fully deidentified.
- The shared backend analysis target is exactly 55 seconds. OpenAI is capped at 35 seconds, DeepSeek at 10 seconds, and the explicit text fallback requires at least 12 seconds remaining immediately before its call. Parser/OCR keeps the hard 8-second deadline and response/persistence keeps a 5-second reserve.
- Browser extension and local debug analysis POST waits are exactly 60 seconds. Visible-resource collection remains a separate cumulative 20-second deadline. The separate private-evaluation dataset runner remains exactly 13 seconds.
- OpenAI uses only `gpt-5.6-sol` through the fixed official endpoint; no configurable OpenAI endpoint or base URL exists.
- The analyzer seam is keyword-only `runtime_cards=()`. It must be an immutable tuple, defaults empty, and accepts only verified `RuntimeKnowledgeCard` objects. It must not read environment variables, paths, keys, bootstrap state, vault state, DPAPI/BitLocker state, or frontend fields.
- Before either analyzer branch, the API must remove the exact reserved private-knowledge keys from the copied untrusted request. It must retain ordinary current-email fields, and only trusted startup state may supply the internal `runtime_cards=` keyword.
- Startup authority-envelope and snapshot reads use a bounded descriptor reader with original/resolved path, parent/target identity, pre-open/post-read `fstat`, reparse and exact-size checks. It performs no write and maps races to fixed fail-closed codes.
- Runtime snapshot bootstrap must pass both the original configured alias and its prevalidated target through the loader. The checked reader reruns the full snapshot-path validator on the alias before open and after read and requires exact target equality.
- Mutable `SecretBytes` are overwritten on key-context exit, but tooling must not claim all transient immutable bytes created by DPAPI, decoding, cryptography or Python are wipeable.
- Automated tests, the 50-case evaluator, static checks, and maintenance scan remain offline: no live provider, mailbox, vault, DPAPI, or BitLocker access.
- Task 5 must not regenerate `docs/operations/project_status_log.md`; that regeneration is reserved for the later integration task.

### Private evaluation tooling

- `backend/private_evaluation/` uses only the pinned project cryptography stack,
  standard-library JSON/path primitives, and existing production validation gates.
- The package must not add a mailbox, vault, SQLite, provider-SDK, IMAP, SMTP,
  DPAPI, BitLocker, browser, or HTTP dependency.
- `scripts/evaluate_private_deepseek.py` exposes only fixed `build`, `verify`, and
  `run` surfaces. `build` consumes only `EvaluationStageV1`; it may use the
  private-evaluation stage/final repositories, schema and selection code, but no
  provider, judge, network, mailbox, raw vault, SQLite, frontend or normal runtime.
  `verify` is local-only. `run` may lazily use the existing backend DeepSeek
  provider only after the explicit interactive flag, exact confirmation, real
  local TTY, fixed exact-y readiness acknowledgement, hidden key, dataset
  decrypt/schema/select, provider configuration and
  judge-availability gates pass.
- Tests use synthetic encrypted datasets and fake clients with
  `EMAIL_AGENT_LLM_PROVIDER=disabled`; they never load a real key, account, dataset,
  provider, external drive, or network service.
- Aggregate reports are JSON written by an allowlisted serializer with finite
  numbers and atomic same-directory replacement. They are not a sample export.
- The local-only `stage-evaluation` command is not in `NETWORK_COMMANDS`, requests
  no mailbox app password, and binds exactly 200 reviewed records from
  `StageEvaluationSelectionV1`. The manifest keeps authorization
  `scope_fingerprint` separate from reviewed `inventory_fingerprint`. An
  evaluation-only source validates the latter before plaintext release, performs
  no evidence accumulation, and retains no domain, message/thread ID, or other
  raw-derived identifier between records. It opens one record at a time, closes
  raw text and the restoration mapping before the next record, and writes only
  `.pkevalstage`.
- The staging/evaluation key is exactly 32 bytes decoded from hidden interactive
  base64 input. It has no flag, environment, `.env`, path, stdout, log, repr, or
  persistence surface, and mutable copies are wiped.
- `.pkevalstage` uses AES-256-GCM with distinct magic, purpose, and namespace from
  `.pkeval` and every private-knowledge/raw-vault store. It is bounded, atomically
  replaced, reparse-rejecting, and external to the complete Project Container
  protected root, OneDrive, temp, raw vault, and other stores. The same protected
  root applies to final `.pkeval`. Post-replacement validation excludes only the exact target
  from its descendant marker scan; sibling and descendant stores still fail
  closed. Success is only `evaluation_stage_complete` with 200/0 counts, while
  parse/local validation emits only `argument_invalid`.
- Final `build` uses the same operator-supplied 32-byte hidden key but generates a
  fresh UUIDv4 final namespace and a fresh random nonce under `.pkeval` magic and
  `private-evaluation-dataset/v1`. It revalidates exactly 200 unique cases, full
  production strata, current business/privacy approvals and at least 40 explicit
  Pro-pair approvals through `EvaluationDatasetV1` and deterministic selection.
  The target must be a separate external directory, create-only, non-reparse and
  race checked. Atomic no-clobber publication must not overwrite a post-validation
  racer. A successful publication-helper return is the final commit point; code
  never rolls back or unlinks the target by pathname. All validation and other
  reportable work precedes that point, while later internal-stage cleanup is
  best-effort and cannot change success. An existing target or pre-publication
  write failure leaves no partial final file, and the reviewed stage is never
  auto-deleted.
- `run --interactive-judge` is the only live judge surface. stdin and stdout must
  both be a real local TTY and complete one fixed exact-y readiness read before
  hidden key loading. The adapter receives only `UsefulnessJudgeView`, shows
  only deidentified subject/thread and production-gated public summary/category/
  risk/action/draft fields, rejects terminal control/format characters before
  rendering, and accepts one exact `y` or `n`. Invalid input, EOF or
  terminal failure becomes fixed `human_judge_failed` and stops before the next
  provider call. The program creates no transcript, prompt/output sample, cache,
  temp file or per-case persistence; it cannot prevent external terminal capture.
- Provider behavior remains sequential 20 Flash + 180 Flash and up to 40 approved
  Pro comparisons, zero retry, no automatic production model switch, and
  aggregate-only persistence.
- Task 9's `PrivateEvaluationCaseV2` is a documentation-only future contract. It
  adds no CLI flag, dataset reader, migration command, provider call, or real-data
  operation. Current tooling keeps V1 compatibility and must reject rather than
  reinterpret an unknown schema.
- A future V2 tool must consume ordered deidentified thread segments, reviewed attachment bindings,
  and an encrypted `StructuredHumanReferenceV2`. Strict
  candidate/reference separation requires the reference to be sealed before
  candidate generation under independent business/privacy approval. A blinded human judge
  performs the comparison without provider/model/route identity, and
  the workflow retains aggregate-only reporting.
- Tooling must never persist raw ChatGPT transcripts or perform automatic training,
  automatic upload of a dataset/reference as a training corpus, model self-grading,
  or an automatic production model switch.

## 14. 执行后检查

Agent 每次完成任务后，必须确认：

```text
[ ] 修改范围与任务模板一致。
[ ] 未新增未批准依赖。
[ ] 测试已补充或说明原因。
[ ] 相关 docs 已同步更新。
[ ] 没有提交 `.env`、数据库文件、真实邮件、密钥或 token。
[ ] 没有引入自动发送、删除、归档邮件功能。
```
