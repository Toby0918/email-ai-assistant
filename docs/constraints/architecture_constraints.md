---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Executable Architecture Constraints

本文件定义本项目的可执行架构约束。这些约束不是普通建议，而是应通过测试或 CI 自动检查的工程边界。

本项目采用以下结构：

```text
frontend/
  outlook_addin/
  google_workspace_addon/
  browser_extension/
  local_debug_page/

backend/
  email_agent/
    config.py
    logging_config.py
    email_cleaner.py
    analyzer.py
    llm_client.py
    database.py
    exporter.py
    api.py
  mailbox_ingest/
    drive_policy.py
    key_envelopes.py
    vault.py
    imap_readonly.py
    inventory.py
    scan.py

docs/
tests/
```

## 1. 分层原则

项目分为四层：

```text
frontend layer
api layer
analysis layer
infrastructure layer
```

`frontend layer` 只负责当前邮件识别、按钮交互、在用户点击后收集当前页面可见的受支持资源、调用后端 API 和展示结果，包括展示后端返回的 Decision Brief。

`api layer` 只负责接收前端请求、调用分析服务、返回结构化 JSON。

`analysis layer` 负责邮件清洗、Prompt 编排、AI 输出校验、Decision Brief 生成和业务规则约束。

`infrastructure layer` 负责后端 AI 调用（后端 DeepSeek 专用 provider、OpenAI 占位能力或明确启用的本地 Ollama/Qwen/Gemma）、SQLite 存储、受限临时附件文件、Excel 导出、配置和日志。

单独授权的 `mailbox ingest layer` 是项目外 vault 和管理员 CLI 的离线基础设施，
不属于 frontend、loopback API 或正常 analysis runtime。它只处理一个授权账号、
固定 IMAPS endpoint 和滚动 24 个日历月；没有 schedule、background poller、
normal-runtime hook 或模型调用。

单独授权的 `private knowledge layer` 只接收 Task 4 staging boundary 写入的
deidentified candidate batch；它不枚举 mailbox，也不拥有 raw-vault reader。

## 2. 允许依赖方向

允许的核心依赖方向：

```text
frontend -> backend API
api.py -> analyzer.py
analyzer.py -> email_cleaner.py
analyzer.py -> llm_client.py
analyzer.py -> database.py
exporter.py -> database.py
llm_client.py -> config.py
database.py -> config.py
scripts/manage_mailbox_vault.py -> backend.mailbox_ingest
scripts/manage_mailbox_vault.py -> backend.private_knowledge
```

禁止反向依赖：

```text
backend -> frontend
email_cleaner.py -> llm_client.py
email_cleaner.py -> database.py
database.py -> llm_client.py
database.py -> openai
exporter.py -> llm_client.py
exporter.py -> openai
frontend -> OpenAI
frontend -> DeepSeek
frontend -> Ollama/Qwen/Gemma/local model endpoint
frontend -> .env
frontend -> local SQLite database
frontend -> backend.mailbox_ingest
backend.email_agent -> backend.mailbox_ingest
normal runtime -> backend.mailbox_ingest
backend.mailbox_ingest -> backend.email_agent
backend.mailbox_ingest -> DeepSeek/OpenAI/Ollama/local model endpoint
```

Only `scripts/manage_mailbox_vault.py` may import `backend.mailbox_ingest`.
其他 `scripts/*.py`、`frontend/`、`backend.email_agent`、local debug、server、
cleanup 和 scheduled workflow 不得引用该 isolated package。Package 内部只能
使用相对导入或自己的 namespace，不得反向依赖正常邮件 analyzer/provider。
The second CLI dependency above is permitted only for Task 4 `stage-knowledge`;
`backend.private_knowledge` must never import `backend.mailbox_ingest` or own a
raw-vault reader.

## Authorized mailbox transport policy

Importer endpoint 固定为 `imap.exmail.qq.com:993` 并验证 TLS certificate。
There is no arbitrary IMAP command passthrough。Public wrapper 只允许：

```text
`LIST`
`EXAMINE`
`UID SEARCH`
`UID FETCH`
`BODY.PEEK`
```

`EXAMINE` 必须保持 read-only；content fetch 只能是有界 `UID FETCH` 和
`BODY.PEEK`。Task 3 增加 runtime validator tests 之前，每个 target 必须是
finite single-UID decimal literal。Task 3 只可在 same change as its runtime tests
中加入 direct bare local、non-imported、non-reassigned expression
`validate_single_uid_fetch_target(uid)`；wildcard、range、sequence、dynamic 和
qualified target 继续 fail closed。以下 operation/transport 不得出现在
wrapper public interface、
CLI dispatch 或可执行调用路径：

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

`ReadOnlyImapSession` 只暴露 `list_folders`、`examine`、`uid_search`、
`uid_fetch_size`、`uid_fetch_bodystructure` 和 `uid_fetch_peek`。不得暴露 raw
client、arbitrary command、SMTP client、mailbox write、flag mutation 或 close
that may expunge。连接无法证明 read-only 状态时 fail closed。

Windows DPAPI/BitLocker dependency 只能在 vault policy call 内 lazy-load，并
由 injected probe 替换，使非 Windows CI 可 import/collect tests。External vault
index 保持 metadata-only。Recovery rewrap 使用 crash-recoverable staged
activation/reconciliation；架构不得假设 cross-volume atomic replacement。

`stage-knowledge` is a later Task 4 handoff command implemented only in the
administrator-only `scripts/manage_mailbox_vault.py`; the eight core vault
commands remain unchanged. It accepts only a reviewed manifest of approved
random record IDs, decrypts one record at a time, runs the local
private-knowledge deidentifier and residual scanner in memory, releases raw
plaintext and the ephemeral mapping before the next record, and writes only an
encrypted deidentified candidate batch under a separate knowledge namespace.
Its result and all output, logs, receipts, and errors contain only candidate
IDs, counts, and fixed codes, never raw record IDs, text, mapping,
paths, locators, or identifying values. `scripts/manage_private_knowledge.py`,
Codex, DeepSeek, normal runtime, and automated tests never import or read the raw
vault.

Task 4 creates `tests/test_manage_mailbox_vault_stage_knowledge.py` and tests the
following exact interface with synthetic injected readers and writers only:

```python
stage_knowledge(
    selection,
    *,
    read_one_record,
    deidentify,
    scan_residuals,
    write_encrypted_candidate_batch,
) -> StageKnowledgeResult
```

## 3. 模块职责约束

### frontend/

前端可以识别当前打开的邮件、展示“分析此邮件”按钮、调用本地后端 API、展示 AI 分析结果，并提供复制回复草稿功能。

前端禁止直接调用 DeepSeek API、OpenAI API、Ollama API、Qwen、Gemma 或任何本地模型端点，禁止保存或暴露 OpenAI/DeepSeek API key，禁止读取 `.env`，禁止连接 SQLite，禁止自动发送、删除、归档、移动、转发或回复邮件，禁止后台扫描整个邮箱，禁止在用户点击前收集资源，禁止把邮件正文写入 console 日志。

### api.py

`api.py` 可以接收当前邮件字段、调用 `analyzer.py`、返回结构化 JSON、做请求字段校验和错误处理。

`api.py` 禁止绕过 `llm_client.py` 直接调用 DeepSeek、OpenAI 或本地模型，禁止保存 OpenAI/DeepSeek API key，禁止自动发送、删除、归档邮件，禁止默认开放公网访问。

### analyzer.py

`analyzer.py` 可以调用 `email_cleaner.py`、`llm_client.py`、`database.py`，并负责校验 AI 输出 JSON。

`analyzer.py` 禁止接受不可解析的自由文本作为最终结果，禁止让邮件正文成为系统指令，禁止自动承诺价格、交期、付款、合同或法律责任。

### email_cleaner.py

`email_cleaner.py` 只负责邮件正文清洗。禁止调用 DeepSeek、OpenAI 或任何模型 provider，禁止调用 SQLite，禁止生成业务分类，禁止决定邮件优先级，禁止生成回复草稿。

### llm_client.py

`llm_client.py` 只负责后端 AI 调用封装。允许的 provider 是规则兜底、DeepSeek 专用 provider、OpenAI 占位能力，以及明确启用的本地 Ollama/Qwen/Gemma。DeepSeek 只能使用代码固定的后端端点，OpenAI/DeepSeek API key 只能来自后端环境；禁止读取前端密钥，禁止把 API key 或本地模型配置返回给任何调用方，禁止把原始异常中的敏感信息直接返回前端，禁止保存分析结果到数据库。

### database.py

`database.py` 只负责 SQLite 持久化。禁止调用 OpenAI，禁止调用前端代码，禁止生成 Prompt，禁止发送邮件，禁止把数据库文件提交到版本库。

### exporter.py

`exporter.py` 只负责基于已保存分析结果导出调试或评估用 Excel。禁止调用 OpenAI，禁止连接真实邮箱，禁止作为主数据存储，禁止导出未脱敏真实敏感邮件内容。

## 4. 可执行检查目标

以下内容必须通过自动化测试检查：

```text
frontend/ 不得包含 OpenAI/DeepSeek API key、DeepSeek/OpenAI 直接调用、Ollama/Qwen/Gemma 直接调用或本地模型端点痕迹。
frontend/ 不得包含自动发送、删除、归档、移动、转发或回复邮件的高风险调用。
backend/email_agent/email_cleaner.py 不得 import openai、llm_client、database、exporter、api。
backend/email_agent/database.py 不得 import openai、llm_client、frontend。
backend/email_agent/exporter.py 不得 import openai、llm_client、frontend。
backend/email_agent/llm_client.py 不得 import frontend、database、exporter。
backend/ 不得 import frontend。
frontend、backend/email_agent 和除 scripts/manage_mailbox_vault.py 之外的脚本不得引用 backend.mailbox_ingest。
mailbox ingest 不得 import analyzer、llm_client、provider client 或 frontend。
mailbox ingest 和 CLI 不得 import smtplib、构造 SMTP client、发出 write IMAP command 或使用 BODY[]。
docs/ 下 Markdown 文件必须包含 YAML front matter。
项目中不得提交 .env、数据库文件、密钥文件或真实 token 文件。
```

本地开发可能存在 `.env`、SQLite 数据库等已被 `.gitignore` 忽略的运行文件；自动化测试应允许这些已忽略文件存在，但禁止未被忽略的敏感文件进入项目。

## 5. 对应测试文件

可执行约束测试文件：

```text
tests/test_architecture_constraints.py
tests/test_mailbox_transport_constraints.py
```

推荐运行方式：

```bash
python -m unittest discover -s tests -p "test_architecture_constraints.py"
```

## 6. 修改规则

如果需要改变架构边界，必须同时修改：

```text
docs/constraints/architecture_constraints.md
docs/constraints/tooling_constraints.md
docs/templates/agent_task_brief_template.md
tests/test_architecture_constraints.py
```

如果只是业务功能变化，不得随意放宽架构约束。
