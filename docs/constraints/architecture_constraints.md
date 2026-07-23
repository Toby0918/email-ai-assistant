---
last_update: 2026-07-23
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
  current_evidence/
    artifact_policy.py
    contract.py
    handoff.py
  project_layout/
    identity.py
    placement.py
    operational.py
    transition.py
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

`infrastructure layer` 负责后端 AI 调用（显式启用的 OpenAI `gpt-5.6-sol` 多模态主路线、DeepSeek 文本路线或明确启用的本地 Ollama/Qwen/Gemma）、SQLite 存储、受限临时附件文件、Excel 导出、配置和日志。

OpenAI uses the fixed official endpoint；`EMAIL_AGENT_OPENAI_BASE_URL` 和其他 arbitrary remote base URL 均不存在。provider 默认关闭，OpenAI model allowlist 只有 `gpt-5.6-sol`，DeepSeek text fallback allowlist 只有 `disabled` 和 `deepseek`。前端和公开请求不得选择 model、endpoint、timeout 或 fallback。

正常点击分析的机械预算是：frontend POST wait 60 seconds、backend shared target 55 seconds、OpenAI cap 35 seconds、DeepSeek cap 10 seconds、fallback minimum remainder 12 seconds、parser maximum 8 seconds、response/persistence reserve 5 seconds。可见资源收集继续使用独立 20 秒期限；`backend.private_evaluation.runner` 的 dataset budget 继续保持独立 13 秒，不受本路线修改。

单独授权的 `mailbox ingest layer` 是项目外 vault 和管理员 CLI 的离线基础设施，
不属于 frontend、loopback API 或正常 analysis runtime。它只处理一个授权账号、
固定 IMAPS endpoint 和滚动 24 个日历月；没有 schedule、background poller、
normal-runtime hook 或模型调用。

单独授权的 `private knowledge layer` 只接收 Task 4 staging boundary 写入的
deidentified candidate batch；它不枚举 mailbox，也不拥有 raw-vault reader。

The `current evidence handoff layer` is contract-only. It validates one bounded
deidentified projection derived from an explicit current-message click and exposes
one append-only callback seam. It owns no mailbox, filesystem, key, store reader,
authority lifecycle, provider, background worker, or public endpoint.

The `project layout layer` is a pure compatibility and protected-root contract.
It validates Repository Root, optional Project Container, standalone state,
protected roots, and stable directory identity, then resolves absolute ordinary
operational locations. `ProtectedLocationPolicy` is derived only from freshly
revalidated placement evidence or the bounded flat-layout compatibility path;
callers cannot construct it with a narrower root tuple. Managed mode preserves
the single Project Container root, covering the container, every named zone, and
all descendants. The layer owns no directory mutation, launcher routing,
container audit, mailbox, provider, credential, key, vault, recovery,
private-store, ACL, volume, or host-security capability. Returned values contain
only path metadata.

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
scripts/manage_mailbox_vault.py -> backend.private_evaluation staging only
normal runtime -> backend.current_evidence append-only contract
future launcher -> backend.project_layout validated path values
reviewed private location policies -> backend.project_layout protected path value
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
backend.current_evidence -> backend.mailbox_ingest/raw vault/authority repository
backend.project_layout -> backend.email_agent/mailbox_ingest/private knowledge/private evaluation
public request/config/frontend/CLI -> protected roots or Project Container override
```

`backend/project_layout/` may import only its own modules plus the reviewed
standard-library path/value modules. Placement validates identity twice and fails
closed on missing/unreadable evidence, reparse components, alias drift, wrong
names, wrong parents, or identity change. Managed placement is exactly
`email_ai_assistant\main`. Standalone placement requires a separate explicit
synthetic or temporary state root and never infers a Project Container.
`OperationalLayout` accepts only a validated `RepositoryPlacement`. The
flat-layout transition adapter cannot add a third placement mode.
`ProtectedLocationPolicy` fails closed for partial Managed placement and checks
both original and resolved candidate views. Exact AST guards allow the policy
only in the reviewed private-knowledge storage/snapshot, private-evaluation
repository-path, mailbox vault/sales-policy, and standalone verification
modules. Public request payloads remove `protected_roots` and
`project_container`, and no environment, config, frontend, ordinary runtime, or
CLI option may provide them.

Only `scripts/manage_mailbox_vault.py` may import `backend.mailbox_ingest`.
其他 `scripts/*.py`、`frontend/`、`backend.email_agent`、local debug、server、
cleanup 和 scheduled workflow 不得引用该 isolated package。Package 内部只能
使用相对导入或自己的 namespace，不得反向依赖正常邮件 analyzer/provider。
The second CLI dependency above is permitted only for Task 4 `stage-knowledge`;
`backend.private_knowledge` must never import `backend.mailbox_ingest` or own a
raw-vault reader.

The executable form of this boundary is: backend.private_knowledge must not import backend.mailbox_ingest,
`backend.email_agent`, IMAP/SMTP clients, or any model provider. Conversely,
`backend.mailbox_ingest` must not import `backend.private_knowledge`. Only
`scripts/manage_mailbox_vault.py` may bridge both namespaces for the explicit,
local `stage-knowledge` command. `scripts/manage_private_knowledge.py` receives
only an encrypted deidentified candidate batch and must never import or open the
raw vault.

Private candidate, authority, and runtime-snapshot data use separate keys,
magic values, HKDF purposes, namespaces, and project-external paths. The
project-external decision rejects the complete Project Container protected root,
not only the Repository Root. The protected roots are derived internally and
cannot be supplied through a snapshot `forbidden_roots` tuple or public surface.
selection manifest binds immutable vault ID, authorization scope fingerprint,
time window, dual reviewers, approved random record IDs, and a maximum 24-hour
review deadline. No CLI accepts raw text, mapping, evidence counter, threshold,
bulk/force override, key, password, vault locator, or raw record ID.

The private-knowledge runtime loader is read-only. It may depend only on the
bounded read-only file reader, snapshot path/codec, immutable runtime schema,
fixed errors, and cryptographic verification. It must not import authority
repository, lifecycle review, candidate store, deidentifier, key store,
publisher, CLI service, SQLite, or any write helper. Failure returns an empty
immutable card set so normal generic rules continue.

Both the authority envelope and runtime snapshot use pre-open and post-read
descriptor identity checks. The shared reader validates the original and
resolved paths, rejects reparse components, captures parent and target identity,
opens with `O_RDONLY | O_BINARY | O_NOFOLLOW` where available, compares `fstat`
with the pre-open target, performs one bounded descriptor read, then repeats
descriptor, original/resolved-path, parent and target checks. A swap, append,
size change, reparse point, non-regular file or short/oversized read fails closed
with a fixed code. These checks narrow same-user namespace races but do not claim
an absolute namespace lock on every supported filesystem.

The startup bootstrap must preserve both the configured snapshot path and its
policy-validated resolved target. The runtime loader and checked reader bind the
original configured snapshot alias against the prevalidated target, rerun the
full snapshot-path policy on that original alias before descriptor open and
after the bounded read, and require the result to remain exactly equal to the
prevalidated target. Alias replacement, reparse insertion, or target drift
returns the empty immutable card tuple through the fixed fail-closed path.

The only normal-service key bridge is the `startup-only runtime bootstrap` in
`backend.private_knowledge.runtime_bootstrap`, imported only by
`scripts/run_local_debug.py`. Startup loads configuration, configures logging,
attempts one fail-closed DPAPI/key/snapshot load, and injects the resulting
immutable tuple into the server. There is `no reload, polling, hot update, or status endpoint`.
Request handlers, `backend.email_agent`, frontend code, SQLite and public HTTP
must never read the authority repository, paths, keys, snapshot metadata, or
bootstrap status. Any bootstrap failure produces `()` with no content-bearing
log or exception detail.

The current-click evidence exception is one-way and authority-free: normal runtime
receives only an opaque append capability for CurrentClickEvidenceV1. The validated
contract and fixed content-free receipt provide no read, get, list, search, query,
path, key, repository, raw-vault, or authority capability. `backend.current_evidence`
may import only the pure placeholder/residual predicates required to reject unsafe
text; it must not import mailbox ingest, private repositories or lifecycle services,
filesystem/environment helpers, SQLite, crypto/key stores, snapshots, providers,
polling, scheduling, or reload code. No frontend or public request field may supply
the callback or a prebuilt contract.

`backend.current_evidence.artifact_policy` is the only exception to the package's
forbidden-token text scan: it may name those tokens solely in compiled rejection
patterns and may import only `re`. It returns one boolean and exposes no match,
value, reader, source, path, key, store, provider, or authority object.

ADR 0008 authorizes a future administrator-triggered incremental synchronization
seam but issue #10 adds no command. Future issue #17 must keep it in
`scripts/manage_mailbox_vault.py`, reuse the exact current inventory fingerprint,
fixed account/endpoint/window and read-only transport gates, and expose no browser,
normal API, cleanup, scheduled, polling, or background trigger.

Mutable `SecretBytes` key buffers are wiped when their shortest-lived context
closes. DPAPI, envelope decoding, cryptography and Python may still create
transient immutable plaintext bytes that cannot be overwritten in place; the
bootstrap therefore promises no all-copy or physical-memory secure erase and
must not add an extra immutable signing-seed copy.

The private evaluation package is offline and aggregate-only. It is a separate
administrator domain that reads an independently encrypted, project-external
`.pkevalstage` only through its stage repository and reads the resulting final
`.pkeval` through its final repository. Both path decisions reject the complete
Project Container root through the exact pure `backend.project_layout` import.
It must not import mailbox ingest, the raw vault, private
knowledge repositories or review/key/snapshot services, frontend code, SQLite,
OpenAI SDK, IMAP, or SMTP. Normal backend runtime, frontend code, local servers,
cleanup jobs, and scheduled workflows must not import it.

`staging_values.py` owns the pure `EvaluationStageV1` value contract.
`dataset_builder.py` is a one-way pure projection from that exact value to
`EvaluationDatasetV1`; it generates a fresh UUIDv4 final namespace and has no
path, key, repository, provider or judge dependency. `terminal_judge.py` imports
only the fixed evaluation error, `UsefulnessJudgeView`, and the pure terminal-text
safety predicate; it must not import schema/case types, paths, JSON, logging,
provider or persistence code.

Only `scripts/manage_mailbox_vault.py` and `scripts/evaluate_private_deepseek.py`
may bridge the private evaluation package. The mailbox CLI bridge is limited to
the local `stage-evaluation` contract/repository: a strict
`StageEvaluationSelectionV1` binds exactly 200 reviewed raw record IDs to unique
case IDs and separately binds authorization `scope_fingerprint` plus reviewed
`inventory_fingerprint`. The evaluation-only source validates each record's
inventory fingerprint before plaintext release, performs no evidence accumulation,
and retains no raw-derived identifier between records. It processes one record at
a time, releases raw text and mapping before the next record, and writes only
external `.pkevalstage` with distinct magic, purpose, and namespace. Atomic
post-replacement validation excludes only that exact target while sibling and
descendant stores remain rejected. It is not a provider bridge, is not in
`NETWORK_COMMANDS`, requests no mailbox app password, and returns only fixed
codes/counts including `evaluation_stage_complete` and parse/local
`argument_invalid`.

The private-evaluation import guard canonicalizes relative imports against each
module package and uses a positive import allowlist for the exact standard-library,
cryptography, internal evaluation, deidentification, and pure analysis modules in
use. Any unlisted network, provider, mailbox, store, runtime, frontend, or relative
escape import fails the mechanical guard.

The evaluator exposes only fixed `build`, `verify`, and `run` commands. `build`
uses the same operator-supplied 32-byte hidden key to decrypt one validated stage
and create one fresh, create-only final dataset in a separate external directory.
Create-only publication uses an atomic no-clobber same-directory link. The
publication helper's successful return is the final commit point; code never rolls
back or unlinks the target by pathname, and only best-effort internal-stage cleanup
may follow. Before that point it revalidates exactly 200 cases, required strata/dual
approvals and at least 40 Pro approvals through final schema and selection, creates
no provider or judge, and never deletes the reviewed stage. `verify` is strictly
local and never imports or creates a provider client.

The `run` bridge to the existing backend DeepSeek provider is lazy. Its exact gate
order is: parse -> interactive flag -> exact confirmation -> TTY -> readiness -> hidden key -> dataset -> provider configuration -> client construction -> calls. stdin and stdout
must both remain a real local TTY; the adapter receives only `UsefulnessJudgeView`.
One fixed exact-y readiness acknowledgement rejects EOF/cancel/invalid input before
key loading or client construction. ESC, C0/C1, bidi/format and other terminal
controls are rejected before any untrusted text is rendered. Invalid per-case input,
EOF or terminal failure maps to `human_judge_failed` and prevents
the next provider call. Automated tests use injected fake clients, keep the provider
disabled, and perform no network, mailbox, vault, DPAPI, BitLocker, or external-drive
operation. Evaluation reports contain only the fixed aggregate schema and fixed
error codes; they never contain cases, prompts, responses, identifiers, paths,
timestamps, sources, samples, or matched text.

Neither build nor run creates a transcript, per-case file, prompt/output export,
cache, log or resume state. Only the aggregate report persists. External terminal
capture cannot be prevented by the program. Runner behavior remains sequential
20 Flash + 180 Flash / 40 Pro, zero retry, and no automatic production model switch.

The planned private-evaluation V2 boundary is documentation-only in Task 9.
`PrivateEvaluationCaseV2` will bind ordered deidentified thread segments and
reviewed attachment bindings plus an encrypted `StructuredHumanReferenceV2`.
Strict candidate/reference separation requires the human reference to be sealed
before candidate generation with independent business/privacy approval; the interactive
surface uses a blinded human judge and aggregate-only reporting. V1 compatibility
is mandatory, with version dispatch and no in-place migration. No current package,
CLI, repository, or runner may claim V2 support until a separate approved
implementation adds strict schemas and offline tests.

Every future V2 implementation must prohibit raw ChatGPT transcripts, automatic training,
automatic upload of a dataset or reference, model self-grading, and an
automatic production model switch. These are architectural prohibitions, not
optional operator settings.

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
One reviewed support set becomes one candidate with evidence bound to that exact
set. Its result and all output, logs, receipts, and errors contain only candidate
IDs, counts, and fixed codes within candidate output; the same content-free
receipt also carries the random batch ID required by the next explicit command.
They never contain raw record IDs, text, mapping,
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

`llm_client.py` 只负责后端 AI 调用封装。允许的 provider 是规则兜底、固定 `gpt-5.6-sol` 的 OpenAI 多模态主路线、DeepSeek 文本路线，以及明确启用的本地 Ollama/Qwen/Gemma。OpenAI 和 DeepSeek 只能使用代码固定的后端端点，OpenAI/DeepSeek API key 只能来自后端环境；禁止读取前端密钥，禁止把 API key 或本地模型配置返回给任何调用方，禁止把原始异常中的敏感信息直接返回前端，禁止保存分析结果到数据库。

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

## 6. Private knowledge to analysis boundary

The normal runtime bridge is intentionally narrow:

```text
backend.email_agent.private_context_gate -> backend.private_knowledge.deidentifier
backend.email_agent.private_context_gate -> backend.private_knowledge.entity_patterns
backend.email_agent.private_context_gate -> backend.private_knowledge.residual_scanner
backend.email_agent.private_knowledge_context -> backend.private_knowledge.runtime_schema
```

No other `backend.email_agent` module may import `backend.private_knowledge`. The renderer may import only `runtime_schema`; it must not import the repository, loader, vault, mailbox ingest, key store, snapshot, CLI, review, candidate-import, filesystem, or environment layers.

`runtime_cards=()` is an immutable backend-only seam. The private context, deidentified prompt, resolver/mapping, card identifiers, selection metadata, and card count are transient implementation details. They must never change the public API, SQLite schema or stored JSON, browser renderer, log record, exception, or fallback diagnostics schema.

The startup script may pass only the already-loaded tuple through
`run_server`/`create_server`/`EmailAssistantServer`/API to that seam. Payload
fields cannot supply or replace runtime cards, and no request may call DPAPI,
open a snapshot, or invoke the runtime loader.

The API copies only ordinary email-analysis input after removing all reserved
private-knowledge payload fields before either analyzer branch. The reserved
set is `runtime_cards`, `private_context`, `knowledge_cards`,
`placeholder_mapping`, `card_id`, `snapshot_id`, `vault_id`,
`private_knowledge_enabled`, `private_knowledge_authority_root`, and
`private_knowledge_snapshot_path`. Legitimate current-email fields remain
available to the injected or default analyzer; only the trusted startup tuple is
added internally to the default analyzer through its keyword-only seam.

`backend.exact_fact_patterns` is the canonical exact-fact recognizer for the
outbound deidentifier, provider-authored output gate, and grounding validator.
Those three boundaries must import the same identifier/date families and retain
parity tests for compact forms plus `: # - / _ . = ( )` separators and
`number`/`no.`/`ID`/`ref.`/`reference` labels. Ambiguous punctuation and bare numeric forms must
retain count/section negative cases. Exact identifiers and calendar dates remain backend-owned; safe
generic count or section phrases such as `order 2 samples` and `part 2` must not
be classified as identifiers.

General privacy refusal maps to the existing `safety_rejected_all` / `safety` /
`not_applicable` diagnostic tuple. The only allowlisted privacy subreason is the
fixed `provider_output_placeholder_echo` / `safety` / `not_applicable` tuple when
the bounded provider output echoes a deidentification placeholder. It carries no
matched text, placeholder value, prompt, response, exception, or dynamic detail.
Deadline refusal maps to the existing `budget_exhausted` / `budget` /
`not_applicable` tuple. The public field set and diagnostic field shape remain frozen.

## 7. 修改规则

如果需要改变架构边界，必须同时修改：

```text
docs/constraints/architecture_constraints.md
docs/constraints/tooling_constraints.md
docs/templates/agent_task_brief_template.md
tests/test_architecture_constraints.py
```

如果只是业务功能变化，不得随意放宽架构约束。
