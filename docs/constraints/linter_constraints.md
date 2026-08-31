---
last_update: 2026-08-30
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Static Linter Constraints

## Historical closure evidence rollover guards

- `backend/r2_closure_evidence_rollover` contains exactly five Python files and
  exports only the coordinator, candidate, receipt, fixed error and error code.
  The coordinator constructor and `prepare()` are parameterless; `execute()`
  accepts only `exact_candidate_fingerprint`.
- The package must not import Issue #39 orchestration, runtime, frontend,
  mailbox, provider, vault, SQLite, network or broad filesystem-copy modules.
  `repository.py` performs fixed Git observations and owns only the
  capability-free evidence-observation/cross-binding value; `storage.py` alone
  imports the closure storage's bounded native identity and commit primitives.
- The CLI exposes exactly `run`, reads no input, and forwards the candidate it
  just prepared. There is no path/ref/repository/command/environment selector.
- Storage contains no copy, replace, unlink, remove, rmdir, rmtree, cleanup,
  repair or overwrite call. Its sole `SetKernelObjectSecurity` use is the fixed
  source control-handle bridge between exact
  `D:P(A;;0x001200a9;;;WD)` and
  `D:P(A;;0x001200a9;;;WD)(A;;SD;;;OW)`; no named-path or Git-common parent DACL
  writer exists. It restores and verifies the original source DACL before the
  normal commit boundary, uses a same-parent no-replace handle rename, and
  compares exact payloads, streams, DACL and file identities before and after.
  Wall and monotonic time both enforce the half-open 300-second window.
- Candidate and receipt schemas are canonical, closed and content-free. Every
  approval, execution-authority and Issue #39 count remains zero; the receipt
  also fixes copy/deletion/overwrite/cleanup counts at zero.

## R2 Issue #110 Solo Maintainer Closure guards

- `backend/r2_solo_maintainer_closure/` must contain exactly ten Python
  files with an explicit public export set. Imports are limited to the standard
  library, internal package modules and exact approved seams: `repository.py`
  may use the read-only CI source/workflow and production-composition values;
  private `github_guardrail.py` may use only the code-fixed authenticated
  GitHub CLI GET adapter;
  `evidence.py` may use the V3 binding value; and private `local_evidence.py`
  may use pure CI-suite/runbook registries plus fixed read-only project-status,
  maintenance and leakage modules. `closure.py` owns the fixed terminal/clock
  ceremony, and `storage.py` alone publishes.
- Every closure JSON value uses strict canonical ASCII JSON: duplicate,
  unknown, missing, noncanonical, NaN, infinity, lone-surrogate, and bool-as-int
  inputs fail closed. Each fingerprint is the SHA-256 of its exact domain,
  a NUL byte, and the canonical body without its own fingerprint.
- Pin exactly five successful GitHub Actions hosted-check records, fourteen
  evidence records, eight dependency-ordered gap proofs, one exact active
  master-ruleset snapshot, and one same-binding manifest. Defect, skip,
  divergence, leakage, private-data, provider, host-operation, approval,
  execution, cleanup, and Issue #39 counters must all be zero.
- Hosted evidence is accepted only for `master` `push` runs at the exact frozen
  commit, with the five fixed check names and GitHub Actions app id `15368`.
  The four provenance checks share one run and attempt, and reconciliation
  depends on the other three verifier jobs. That metadata continues through the
  code-fixed anonymous public `https://api.github.com` endpoint.
- The guardrail snapshot requires exactly one active master ruleset, zero
  bypass actors, deletion and non-fast-forward protection, strict required
  status checks for those five app-bound contexts, the approved pull-request
  rule, and absent classic branch protection. A missing, layered, stale, or
  mismatched guardrail state blocks closure. Private `github_guardrail.py`
  alone may call absolute `C:\Program Files\GitHub CLI\gh.exe` with the existing
  active `Toby0918` `github.com` keyring identity, auth checks before/after,
  exactly three fixed GETs, and a sanitized allowlist environment that disables
  update checks and telemetry. Stdout/stderr are separately bounded; only the
  exact content-free classic 404 diagnostic may accompany HTTP 404 / exit 1.
  Python never reads or prints the token. `bypass_actors` must be explicitly `[]`;
  `required_reviewers` may only be absent or exactly `[]`, and only the empty
  wire default is removed. `require_extra_approval_for_unattributed_changes`
  may only be absent or exactly `true` when `required_approving_review_count`
  is the exact integer `0`; only that accepted value is removed before exact
  comparison with the unchanged 965-byte configuration and fingerprint
  `5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e`.
  `github_guardrail.py` is the only authenticated GitHub command Adapter. It
  uses the fixed absolute Windows GitHub CLI.
  There are two keyring-backed auth-status checks and three fixed GET-only requests.
  Python never reads or emits the GitHub token.
  The seam accepts no caller credential, URL, method, fallback, or cache.
  `required_reviewers` absent or exactly `[]`, plus absent or exact `true`
  `require_extra_approval_for_unattributed_changes` at exact integer zero
  approvals, are the only compatibility shapes; explicit `bypass_actors=[]`
  remains mandatory.
- The fixed no-argument verifier retains the Issue #102 safe-path and raw-Git
  chain, accepts only the new manifest and attestation files in the fixed Git
  common directory, and rejects every legacy V1 external/signature artifact,
  fallback, compatibility parser, or alternate trust model.
- Solo attestation records one operator and zero independent, external, and
  hosted-human reviewers. It is evidence, not Issue #38 approval, production
  authority, a ruleset mutation, Issue #39 authorization, or execution.

## R2 generated-runbook guards

- Require exactly ten unique catalog verbs covering every
  `ProductionCommandV2`; each dispatcher map is derived from the catalog.
- Require exact acknowledgement agreement, one-operation ceilings, closed
  effects, zero destructive capability, and rejection of every unknown or
  historical R1 alias.
- Generate `docs/operations/r2_final_operator_runbook.md` byte-for-byte from
  the catalog and state machine; hand-edited semantic drift fails tests.
- Receipt construction requires exact final commit/tree, runbook hash, source-
  package hash, current package-semantics fingerprint, and same-binding #98
  proof. Stale or mixed evidence fails closed.
- Require exactly fourteen decision rows and four R1 blocker-class completion
  rows; bind both registry fingerprints and reject omission or duplication.
- Retention reconciliation and human final review accept no command; the
  generated artifact, receipt, CI, and synthetic proof are not authority.

## R2 retention-ledger guards

- Require exact same-binding #94-#97 plan links and a journal extension of the
  rollback plan; reject caller-provided entries, counts, or artifact selectors.
- Track original, new, partial, failed Container, commit evidence, and every
  genesis/record journal artifact as unique content-free entries.
- Reconcile forward-committed, forward-recovery-required, rollback-pending,
  rollback-classified, rollback-in-progress, rollback-complete, and legacy-
  restored states without adding a parallel lifecycle head.
- Production-graph AST guards reject filesystem/process mutation imports and
  removal, unlink, directory removal, replacement, pruning, or expiry calls.
- Ledger and proof must report zero untracked artifacts, destructive/deletion/
  overwrite/prune/automatic-expiry capabilities, and private payload fields.

## R2 rollback recovery guards

- Derive the reverse plan only from the same-binding #94-#96 plan chain and
  exact durable forward commits; failed-Container preservation is always first.
- Require strict LIFO source transition order, a unique nonzero remaining-plan
  fingerprint per boundary, and fresh single-use ROLLBACK authority per intent.
- Effect evidence fixes retained failed/partial objects, one bounded reverse
  mutation, and zero destructive operations. PRE/POST/AMBIGUOUS follow the
  unified journal and never permit a blind repeat.
- The package stays pathless and dormant, with no executable, normal-runtime
  consumer, host adapter, issuer, cleanup, deletion, provider, mailbox, vault,
  or private-data capability.
- The only successful reverse terminal is `LEGACY_FLAT_LAYOUT_RESTORED`, after
  exact legacy and independent audit evidence, with zero terminal host effects.

## R2 two-start validation guards

- Require the exact seven-action lifecycle sequence after all eight managed
  commits; no caller selector may reorder or omit an action.
- Start A and Start B must have distinct run, nonce, and actor identities.
  Rules evidence requires one analysis, one row, and `provider_attempts=0`.
- Stopped and final audits require distinct independent actors and exact
  300-second windows containing the claim and final freshness time.
- Final seal requires fresh RESUME authority, `minimal_read_count=2`, zero host
  mutations, and no existing terminal record.

## R2 managed-unit publication guards

- Require Runtime, Database, CRX, and Config PREPARE then PUBLISH in that fixed
  order, with exactly eight unique transition instances.
- Effect evidence must bind exact identity, bytes, ACL, unit semantics, retained
  source/partial/failed state, one host mutation, and zero destructive actions.
- Recovery requires exact ACL and semantic proof. Database proof includes
  SQLite semantic conformance and sidecar state; a false or omitted check fails.
- POST permits one recovered commit and zero effect replay; PRE requires fresh
  resume authority; ambiguity incident-stops.

## R2 foundation publication guards

- The plan must contain exactly 17 transitions, exactly eleven worktree
  instances, the fixed owner sequence, unique instance fingerprints, and no
  caller-controlled selector.
- Only the next transition in the committed prefix may begin. Every authority,
  intent, effect, observation, and commit binds the same transition.
- PRE restart requires fresh resume authority and a new intent; POST restart
  permits a recovered commit without effect replay; ambiguity incident-stops.
- The package must remain pathless and content-free, with no filesystem,
  process, database, signer, issuer, cleanup, or private-data capability.

## R2 unified-journal guards

- The journal package must retain its exact closed record and effect vocabulary,
  canonical framing, one owner, one increasing sequence, and one predecessor
  head per append.
- Fresh reconstruction must reject an unknown type, duplicate/reordered record,
  owner/head drift, authority replay, noncanonical JSON, invalid frame length,
  extra bytes, and any torn tail.
- The package must not import path, operating-system, subprocess, database, or
  production process roots and must not gain reader, signer, issuer, mutation,
  cleanup, mailbox, provider, vault, or private-data capability.
- Inspection receipts must remain zero-mutation, zero-append evidence outside
  the real-authorization type registry.

## R2 Git-byte state guards

- Selected bytes must match the exact Git blob OID, checkout bytes, index OID,
  mode, stage zero, and false assume-unchanged/skip-worktree flags.
- Changes including same-size edits, EOL/filter drift, index-only or staged changes, ref drift,
  stable-common-state drift, and original/reconstructed administrative drift
  fail before a receipt exists.
- Counts are exact: fourteen refs, five stable common roles, eleven original
  and eleven reconstructed worktrees with eight embedded and three external.
- The pure package must not gain path, filesystem, Git runner, process,
  ignored/private content, cleanup, or authority capability.

## R2 execution-confirmed single-action guards

- The fixed command map contains exactly ten commands across the preflight,
  evidence, and transaction domains. There is no umbrella, path, selector,
  batch, force, shell, retry, direction, signer, key, or envelope input.
- An execution confirmation binds the V3 binding, closure manifest and solo
  attestation, exact command/action, prior journal head and next sequence,
  transition instance, remaining-plan fingerprint, and applicable reverse-plan
  fingerprint. Wrong or stale facts fail before any Adapter attempt.
- One append creates one journal claim; the first Adapter attempt consumes it.
  There is no replay, retry, second Adapter, process-local claimed set, or
  effect-before-append path.
- Production modules contain no private key, signature, issuer, delete,
  overwrite, repair, cleanup, provider, mailbox, vault, credential, or
  private-data capability.

## R2 execution-confirmed evidence and genesis guards

- Evidence publication retains exactly one fixed `publish` command and no
  path, target, profile, selector, force, shell, or arbitrary payload input.
- The exact completion binds the consumed execution-confirmation claim, review,
  evidence identity, package, and manifest before canonical genesis creation.
- Genesis reconstructs its embedded claim from canonical bytes and rejects
  mixed binding, closure, attestation, identity, prior head, sequence, replay,
  duplicate key, or fingerprint drift.
- These contracts are testable dormant primitives only; Issue #110 does not
  make the production process graph reachable.

## R2 execution-confirmed preflight guards

- The catalog retains exactly six fixed read-only preflight commands and one
  Adapter per matching command/domain after V3 and execution-confirmation
  validation.
- Wrong binding, closure, attestation, command, action, prior head, sequence,
  transition, remaining plan, reverse plan, acknowledgement, replay, or time
  facts fail before Adapter selection in focused contract tests.
- Production roots remain unconditionally `DORMANT_NO_ISSUE39_APPROVAL` before
  TTY, candidate, confirmation, and Adapter access. There is no live unlock in
  Issue #110.

## R2 production binding V3 guards

- The package may import only the standard library and the stable structural
  final-master value from `backend.r2_solo_maintainer_closure`.
- It must not contain key construction, signatures, envelopes, filesystem,
  database, process, network, provider, mailbox, vault, or host capability.
- Public signatures must not accept paths, shell commands, adapters, callbacks,
  keys, secrets, environment values, issuer objects, or arbitrary authority.
- The V3 binding pins four domains, ten commands, eighteen production roles,
  the final-master binding, and assurance counts `1/0/0`. Execution-confirmation
  claims carry durable single-use journal facts; there are no V2 aliases.

本文件定义项目的自定义静态检查规则。  
它的目的不是替代单元测试，而是把容易被 Agent 忽略的工程边界变成可执行检查。

本项目当前不引入额外 lint 依赖。第一阶段使用 Python 标准库 `unittest`、`ast`、`re` 实现静态检查。

## 1. 目标

静态检查必须覆盖以下风险：

- 后端业务代码使用裸 `print()`。
- 后端业务代码使用 `traceback.print_exc()`。
- 出现裸 `except:`。
- 前端出现 OpenAI/DeepSeek API key、DeepSeek/OpenAI 直接调用、Ollama/Qwen/Gemma 直接调用、本地模型端点或 `.env` 访问。
- 前端出现自动发送、删除、归档、移动、转发或回复邮件的高风险调用。
- 项目中出现疑似真实密钥、token 或数据库文件。
- `docs/` 下 Markdown 文件缺少 YAML front matter。
- 架构边界被破坏，例如 `email_cleaner.py` 调用 OpenAI 或数据库。
- 管理员 mailbox ingest 出现任意 IMAP passthrough、write/flag-mutation command、SMTP、非 PEEK body fetch，或被浏览器/正常 runtime 引用。
- `backend.container_audit` 获得 host/content/mutation capability，或被 normal runtime、cleanup、browser、root wrapper、workflow 调用。

## 2. Linter 报错格式

每一条自定义 linter 报错都必须尽量包含三类信息：

```text
❌ 什么错：说明具体违反了哪条规则。
✅ 怎么改：给出最小修复方式。
📖 去哪里看：指向对应 docs 文件。
```

示例：

```text
❌ 什么错：backend/email_agent/analyzer.py 使用了裸 print() 输出业务日志。
✅ 怎么改：改用 logging.getLogger(__name__)，并避免输出真实邮件正文。
📖 去哪里看：docs/conventions/logging.md
```

该格式的作用是把 linter 错误变成 Agent 可执行的修复提示。  
Agent 看到报错后，应按提示修复，而不是绕过测试或删除规则。

## 3. 禁止裸 print()

业务代码中禁止使用裸 `print()` 作为日志。  
应使用 Python 标准库 `logging`。

禁止：

```python
print("analysis result", result)
```

允许：

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Email analysis completed for email_id=%s", email_id)
```

注意：日志中不得输出真实邮件正文、API key、OAuth token、邮箱凭据、真实报价、未脱敏客户信息。

参考：

```text
docs/conventions/logging.md
```

## 4. 禁止 traceback.print_exc()

业务代码中禁止使用 `traceback.print_exc()`。  
异常必须通过 logger 记录，并保留上下文。

禁止：

```python
import traceback

try:
    run()
except Exception:
    traceback.print_exc()
```

允许：

```python
try:
    run()
except Exception:
    logger.exception("Failed to analyze email_id=%s", email_id)
    raise
```

## 5. 禁止裸 except

禁止：

```python
try:
    run()
except:
    pass
```

允许：

```python
try:
    run()
except ValueError as exc:
    logger.warning("Invalid AI response: %s", exc)
    raise
```

## 6. 前端禁止云端/本地模型 provider 直接调用

前端不得出现以下内容：

```text
OPENAI_API_KEY
DEEPSEEK_API_KEY
sk-
api.openai.com
api.deepseek.com
/v1/responses
/v1/chat/completions
new OpenAI(...)
require("openai")
from "openai"
require("deepseek")
from "deepseek"
127.0.0.1:11434
localhost:11434
/api/generate
/api/chat
ollama
qwen3.6
gemma4
process.env
.env
```

OpenAI/DeepSeek API key 和本地 Ollama/Qwen/Gemma 配置只能存在后端环境变量中，由后端 `llm_client.py` 使用。前端禁止引入 OpenAI 或 third-party DeepSeek SDK，也禁止配置或调用任何远程模型端点。

后端 OpenAI model allowlist 只有 `gpt-5.6-sol`，并 uses the fixed official endpoint。静态约束必须拒绝 `EMAIL_AGENT_OPENAI_BASE_URL` 或其他可配置 OpenAI remote base URL。分析 POST wait 必须在浏览器扩展和 local debug 中固定为 60 seconds；backend shared target 为 55 seconds、OpenAI cap 为 35 seconds、DeepSeek cap 为 10 秒、fallback minimum remainder 为 12 seconds、parser maximum 为 8 秒、response/persistence reserve 为 5 秒。

## 7. 前端禁止高风险邮箱动作

第一阶段前端不得出现自动发送、删除、归档邮件动作。

禁止高风险关键词包括：

```text
sendMail
gmail.users.messages.send
archiveMessage
deleteMessage
trashMessage
messages.trash
messages.modify
moveMessage
forwardMessage
```

如果未来确实要加入这些能力，必须先更新：

```text
AGENTS.md
docs/product/feature_scope.md
docs/security/email_data_handling.md
docs/constraints/architecture_constraints.md
docs/constraints/linter_constraints.md
tests/
```

并且必须经过人工确认。

## 8. 密钥和敏感文件检查

项目中不得提交：

```text
.env
*.db
*.sqlite
*.sqlite3
*.token
*.secret
```

文本文件中不得出现疑似密钥：

```text
sk-...
ya29....
password = "..."
```

如需测试，应使用明显的假值：

```text
OPENAI_API_KEY=your_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

## 9. 依赖精确版本冲突检查

`requirements.txt` 中同一个规范化包名不得同时出现不同的 `==` 版本。包名比较忽略大小写，并将 `-`、`_`和 `.` 视为等价分隔符。重复的相同版本可以解析，但任何冲突版本都必须使静态约束失败。

可执行实现位于 `scripts/repo_utils.py` 的 `parse_pinned_dependency_versions()`，并由 `tests/test_repo_utils.py` 的合成冲突用例和 `tests/test_static_linter_constraints.py` 的真实 `requirements.txt` 检查共同覆盖。

## 10. 文档元信息检查

`docs/` 下所有 Markdown 文件必须包含 YAML front matter：

```yaml
---
last_update: 2026-06-29
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---
```

## 11. Authorized mailbox transport policy

静态约束必须把 isolated mailbox import 视为一个窄 allowlist，而不是一般邮箱
SDK。Endpoint 固定为 `imap.exmail.qq.com:993`，且 there is no arbitrary IMAP command passthrough。唯一允许 import `backend.mailbox_ingest` 的外部文件是
`scripts/manage_mailbox_vault.py`；frontend、backend/email_agent、其他 scripts、
server、cleanup 和 scheduled workflow 都不得引用该 package。

允许的 transport token：

```text
`LIST`
`EXAMINE`
`UID SEARCH`
`UID FETCH`
`BODY.PEEK`
```

禁止的 transport token/operation：

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

Mechanical test 必须拒绝 `smtplib`、SMTP client/send method、non-PEEK
`BODY[]` 和 wrapper public interface 中不在 allowlist 的 method。它还必须证明
浏览器 manifest 仍只有 `activeTab`/`sidePanel` 和既有两个 host permission，
不得新增 mailbox/OAuth/background-enumeration permission。

Windows DPAPI/BitLocker module 必须 lazy-load behind injected probes；静态和
import tests 不得在 CI collection 时探测 host。Recovery rewrap code/documentation
不得声称 cross-volume atomicity。

## 12. 对应测试文件

自定义静态检查实现文件：

```text
tests/test_static_linter_constraints.py
tests/test_architecture_constraints.py
tests/test_mailbox_transport_constraints.py
```

运行方式：

```bash
python -m unittest discover -s tests -p "test_static_linter_constraints.py"
```

建议在提交前同时运行：

```bash
python -m unittest discover -s tests
```

## 13. Private context mechanical guards

Executable constraints must enforce all of the following:

- only `private_context_gate.py` may import Task 4 deidentification/residual-pattern modules from `backend.private_knowledge`;
- only `private_knowledge_context.py` may import `backend.private_knowledge.runtime_schema`;
- only `scripts/run_local_debug.py` may import `backend.private_knowledge.runtime_bootstrap`; the bootstrap must not import `backend.email_agent`, logging, SQLite, frontend, mailbox ingest, provider, polling, reload or write helpers;
- authority-envelope and runtime-snapshot reads must route through `backend.private_knowledge.checked_reader`; it may use descriptor read/open/stat/close operations but no write, replace, rename, unlink, remove or mkdir operation;
- descriptor reads must compare pre-open and post-read parent/target identity and revalidate original/resolved paths; race failures expose only fixed codes;
- private-knowledge configuration paths must remain backend-only and hidden from repr, HTTP, SQLite, frontend, logs, health/status and exceptions;
- runtime bootstrap occurs at most once before server start; request handlers may receive only the already-loaded immutable tuple and must never access DPAPI, keys, files, loaders or bootstrap state;
- every untrusted request payload must have the exact reserved private-knowledge field set removed before either injected or default analyzer dispatch; ordinary email-analysis fields remain, and only the trusted startup tuple may enter the default analyzer through `runtime_cards=`;
- runtime snapshot loading must preserve the configured alias and its prevalidated snapshot target, rerun the full snapshot-path policy on the original alias before open and after read, and fail closed unless both checks still resolve to that exact target;
- key-context cleanup means best-effort overwrite of mutable `SecretBytes`; guards and docs must not claim that DPAPI, cryptography or Python transient immutable bytes can all be wiped;
- no frontend source or browser renderer may reference `runtime_cards`, `private_context`, `placeholder_mapping`, `card_id`, `snapshot_id`, `vault_id`, or a deidentification placeholder;
- no public API or SQLite result may gain private context or knowledge-card fields;
- DeepSeek provider output containing a placeholder, restoration/re-identification instruction, or private metadata marker is rejected before either parser runs;
- `backend.exact_fact_patterns` is the canonical exact-fact recognizer for
  outbound deidentification, provider-output rejection, and grounding; all three
  boundaries must import it and parity tests must cover compact identifiers,
  `: # - / _ . = ( )` plus `number`/`no.`/`ID`/`ref.`/`reference` separated
  forms, supported numeric/Chinese/month-name calendar-date forms (including
  dotted abbreviations and `日`/`号`), and safe punctuated or bare
  count/section phrases;
- logs and exceptions remain content-free; the diagnostic field shape remains frozen,
  general privacy refusal uses `safety_rejected_all` / `safety` / `not_applicable`,
  and only placeholder echo may use the fixed
  `provider_output_placeholder_echo` / `safety` / `not_applicable` tuple;
- normal current-email budget constants are backend/OpenAI/DeepSeek/fallback minimum/response reserve = 55/35/10/12/5 seconds, parser maximum = 8 seconds, and both frontend analysis POST waits = 60 seconds;
- the private-evaluation dataset runner remains a separate 13-second budget;
- OpenAI model configuration remains exactly `gpt-5.6-sol` through the fixed official endpoint, with no configurable OpenAI base URL.

These guards belong in `tests/test_architecture_constraints.py`, the frontend static suites, and the public response/persistence canaries. They must run with synthetic data and no network.

### Current-click evidence mechanical guards

`backend.current_evidence` is a closed, contract-only package. Its public surface
is exactly `CurrentClickEvidenceV1` and `submit_current_click_evidence`. Only
`backend.current_evidence.contract` may import the pure private-knowledge entity
pattern and residual-scanner modules; no reader, path, key, repository, raw-vault,
or authority import is allowed anywhere in the package.

`backend.current_evidence.artifact_policy` may import only `re` and `unicodedata`,
export only its boolean predicate, and call only NFKC normalization, regex
compile/search, Unicode category inspection, plus `any`. All normalized `Cf` format
controls and `Cs` surrogate code points fail closed. Explicit default-ignorable
non-`Cf` ranges (joiners, variation selectors, fillers, tags, and reserved
default-ignorables) also fail closed without rejecting all combining marks. It may contain
forbidden metadata words solely as rejection patterns and must never expose a
match, matched text, capture, source, or capability.

`submit_current_click_evidence` may validate a mapping and invoke one injected
append callable. Exact import bindings and call-target allowlists cover every
package module. A complete binding inventory plus a forbidden-capability reference
scan rejects alias/rebinding and dynamic target construction; a fixed fingerprint
pins every binding name, kind, Store occurrence count, and non-name mutation target.
Covered forms include `for`, comprehension, `with`, exception, import,
default-argument, tuple, walrus, augmented assignment, type alias, global/nonlocal,
delete, attribute, and subscript forms.
Read/get/list/search/query/open/load, mailbox ingest, SQLite, provider, environment,
scheduler, polling, reload, and hot-update surfaces remain forbidden; only the named
pure regex predicates used for local artifact validation may call `search`. A
separate executable-source guard covers all
administrator scripts and wrappers plus normal API, cleanup, local-service,
browser, and scheduled-workflow surfaces. It scans path parts relative to the
explicit protected-surface root, executable docstrings, UTF-8 bytes literals,
multi-value/deep-chain constant propagation, constant-valued f-strings, literal
`join`/`format`/percent-format calls, folded single- or multiline Python/frontend
concatenations, JS constant array joins/templates, and bounded JS escape decoding;
legacy octal escapes fail closed.
Protected mailbox/account/folder
path context applies to plain synchronize/resynchronize commands, and compact
lowercase route/call compounds plus auto/re/sync morphology are rejected while
`async`, `fsync`, `synchronous`, and unrelated generic synchronization prose remain
allowed. Refresh/delta/pull/update are also rejected whenever the executable
fragment carries mailbox/account/IMAP context, or its protected relative path has
strong mailbox/account/folder/IMAP/inbox/vault context, without making the generic
`backend/email_agent` path reject unrelated update/refresh uses. The status
generator exception applies only at the canonical generator path, only to literal
prose in the direct `build_project_status` f-string result, only while the complete
generator AST matches its reviewed SHA-256 fingerprint, and only when its sole
call flows through the exact consecutive `Path` output binding, fixed parent
creation, and `output.write_text` statements in `main`. `output` must have exactly
one Store and no other binding or deletion. The complete `parse_args` and `main`
signatures and bodies are pinned, including the sole canonical `argparse` import.
The canonical `pathlib.Path` import and
`ROOT = Path(__file__).resolve().parents[1]` binding are unique and unrebound;
attribute mutations, protected subscript mutations, and custom `write_text`
definitions are rejected. Custom/rebound receivers, executable sinks, aliases,
higher-order references, and other strings remain guarded. The
administrator CLI command constants and mutation/binding inventory, sole
`commands.add_parser(command)` attribute reference, exact command-loop iterable,
complete `build_parser` AST fingerprint, computed reflection strings, and runtime
parser choices are frozen for issue #10; equivalent refresh/delta/pull/update
surfaces require a later approved issue. Contract and
append failures expose only fixed
`evidence_contract_invalid` or `evidence_append_failed` codes. Frontend, public
HTTP payloads, public SQLite rows, provider routing, and the startup-only snapshot
loader do not gain current-evidence fields or capabilities. Tests use synthetic
content with both remote provider routes disabled.

Before placeholder and residual-PII scanning, contract text is NFKC-normalized for
validation only. Fullwidth or compatibility-form email, phone, URL, and placeholder
text therefore fails, while the original bounded text is retained only after the
normalized view passes every check.

### Content-free ContainerAudit mechanical guards

`backend/container_audit/` must remain an exact pure-module allowlist. It may
import only its own modules plus `dataclasses`, `enum`, and typing support. AST
checks reject path/filesystem reads, host probes, Git or subprocess execution,
SQLite clients, ACL/volume clients, logging, content readers, mutation calls,
default adapters, CLI modules, and composition roots.

The audit package must remain a distinct module from repository leakage and
maintenance scanning. A recursive consumer guard scans all other backend
modules, `scripts/` (including cleanup and leakage tooling), root Python
wrappers, frontend/browser files, and workflows. Only Issue #36's exact
`backend/reparenting_rehearsal/audit_bridge.py` and Issue #53's exact
`backend/real_host_preflight/audit_bridge.py` may import the package and call
`run_container_audit`; every other consumer remains forbidden. The #53 bridge
may only bind the existing exact seven read-only callbacks and must not change
the final nine-zone policy or add a host import to the audit core. The exact
seven injected adapter fields and keyword-only no-default entrypoint are pinned
by contract tests.

Behavior tests use only frozen repr-redacted synthetic evidence. They cover the
exact nine-entry direct-child allowlist; alias/reparse/unreadable/incomplete and
two-pass drift failures; ACL/NTFS/Git/worktree/runtime/SQLite relationships;
bounded Config/Logs/Artifacts metadata; disabled private zones; adapter
exceptions; fixed status/count output; and first-failure short circuit. No test
runs a real Container audit or host-security probe.

### No-clobber migration evidence mechanical guards

`backend/migration_evidence/` has an exact module-file and import-root allowlist.
AST checks reject imports from normal runtime, mailbox/provider, SQLite,
private knowledge/evaluation, vault/private stores, frontend, cleanup,
scheduler, or network clients. Only the internal Git runner may access
`os.environ`, and it must construct a minimal sanitized child environment with
global/system config, fsmonitor, terminal prompting, and optional locks
disabled. Literal Git mutation/network verbs are forbidden.

A recursive consumer guard rejects migration-evidence imports or invocations
from every other backend module, scripts, frontend/browser files, and workflows
except Issue #36's exact
`backend/reparenting_rehearsal/evidence_bridge.py` and Issue #53's exact
`backend/real_host_preflight/baseline_bridge.py`. The #53 bridge may import only
the existing repr-redacted `HostBaseline` value for canonical projection; it
cannot review, create, publish, verify, read, or delete a migration-evidence
package. Issue #54 adds only the exact
`backend/migration_evidence_publication/review_bridge.py`,
`creator_bridge.py`, and
`backend/migration_evidence_verifier/bridge.py`; each may import and call only
its single reviewed prepare, create, or verify seam. The only additional
repository-tooling integration is the leakage scanner's fixed
`.migration-evidence.zip` suffix check; it classifies by name before file reads
and never imports or verifies the package. `.gitignore` reserves the same suffix,
and static linter tests fail if such an artifact appears inside the repository.

Behavior guards require exact local `refs/heads/*`, root worktree selection,
regular stage-zero index entries, separate index/worktree bytes, full
selection/snapshot cross-validation, strict canonical JSON, per-file SHA-256,
semantic Git/host/selection consistency, and independent bundle verification.
They reject ignored or explicitly approved forbidden categories before content
reads, special index flags, unsupported Git states, target/source reparse,
source drift, existing targets, partial writes, and commit races. Tests use only
`TemporaryDirectory` synthetic repositories and destinations.

### Synthetic reparenting rehearsal mechanical guards

`backend/reparenting_rehearsal/` has an exact module-file/import-root allowlist.
Only `git_runner.py` may import `subprocess`; only `audit_bridge.py`,
`evidence_bridge.py`, and `layout.py` may cross into ContainerAudit,
migration-evidence, and project-layout respectively. All other external backend
imports are rejected. No script, normal runtime, frontend, cleanup, leakage or
workflow consumer is allowlisted. The recursive consumer candidate set includes
all other backend modules, scripts, root Python and shell wrappers,
frontend/browser text files, and workflows; Python imports/calls and non-Python
text invocations are rejected.

AST checks pin the public seam to exactly two keyword-only no-default inputs and
reject a `Path` or ambient repository surface. Literal clone/fetch/pull/push/
prune/remove/clean/reset/restore/rm/checkout/merge/rebase/stash verbs,
`shell=True`, destructive filesystem calls, unreviewed subprocess imports, and
mutation calls outside the exact synthetic builder/publication/worktree files
fail the architecture suite.
Behavior guards also replace the marker with identical bytes and require
publication to fail on identity drift even when the identity reader is forced to
simulate inode reuse. They reject marker/anchor reparse state, reparse scope
components and a non-local remote both directly and at the orchestration/baseline boundary,
bind the captured remote fingerprint to the fixed local bare remote, pre-create
a recreate target and junction parent and require failure before any worktree
mutation, preserve the public sandbox after return, and independently observe
each failure topology rather than trusting its status value.

Behavior tests pin the non-trivial branch/ref/remote/ahead-behind baseline,
separate tracked/index/worktree and reviewed-untracked hashes, excluded-path
metadata-only handling, both reviewed linked-worktree strategies, exact common
directory identity, clean linked status, Managed relationship, actual
ContainerAudit pass, existing-target no-clobber, and a verified rollback at all
six fixed publication boundaries. They create no real evidence package or
Project Container and never accept the current Repository Root as input.

### Synthetic Managed runtime activation rehearsal mechanical guards

`backend/runtime_activation_rehearsal/` has an exact module-file allowlist and
may import only its own modules plus reviewed standard-library value helpers.
AST guards reject filesystem, SQLite, subprocess, network, provider, mailbox,
vault, private-store, credential, signing, ContainerAudit and migration-evidence
imports. They also reject destructive/cleanup capability names and any
normal-runtime, script, frontend, root-wrapper, cleanup, leakage or workflow
consumer, including direct calls and non-Python text references.

Contract guards pin one keyword-only no-default `adapters` parameter, exactly
five required adapter fields, frozen/slotted/repr-redacted evidence, and fixed
aggregate-only results. Validation uses exact types, so boolean schema versions
or counts cannot pass integer contracts. Runtime checks bind actual
runtime/venv/Scripts/executable parents, stable dependency-lock identity/hash,
exact pins, offline rebuild and untouched sources.

Behavior guards require phase-bound stop-plus-independent-probe before SQLite
work, create-only database/artifact publication, stable source re-observation,
pre-frozen reviewed artifact identity/hash, exact Managed resource roles, and
one activation token echoed by start, health, analysis and the
`post_activation` final stopped proof. Final proof must use a fresh stop token
for the same service. Temporary integration tests inject equality spoofing,
stale stop replay, runtime/database/artifact race, reparse, existing target,
dependency, integrity and health failure and independently assert
source/legacy/competitor preservation plus zero forbidden access before
caller-owned teardown.

### Locked Cutover contract mechanical guards

`backend/cutover_contracts/` has an exact module-file and public-export
allowlist. Recursive file enumeration rejects nested or non-source payloads
outside generated `__pycache__`. Absolute imports are limited to exact pure
standard-library modules and exact imported symbols; relative imports are
limited to exact sibling package modules. Parent-relative, unknown,
dotted-module, filesystem, process, SQLite, network, environment,
dynamic-import, logging, clock, random, stdin, host, forbidden builtin loads or
aliases, including `breakpoint`, `delattr`, and `setattr`, and ambient-authority
imports or calls fail AST checks.

The authorization module must remain parse-only for externally supplied
canonical values. Function-name and call guards reject real-authorization
`create`, `issue`, `mint`, `generate`, `sign`, `uuid4`, `now`, `utcnow`,
`time`, or token-generation surfaces across the whole package, except the
exact Profile, Receipt, and synthetic-test `create` methods. Exact-type
behavior tests require
mapping, receipt, duck-typed, subclassed, and
`TestSandboxAuthorizationV1` values to fail real-host validation.

A recursive consumer guard scans every other Python/JavaScript file under
`backend/`, `scripts/`, and `frontend/`. Python imports are parsed as AST so
direct, `from backend import ...`, and relative forms all reject
`cutover_contracts`; direct, attribute, imported, rebound, or chained aliases
of `__import__` and `importlib.import_module` are rejected at the call seam even
when their module target is dynamically bound. JavaScript retains fixed-token
rejection. The only allowlisted consumers are
`backend/cutover_journal/contracts_bridge.py` and Issue #53's exact
`backend/real_host_preflight/contracts_bridge.py`, plus Issue #54's exact
`backend/migration_evidence_publication/contracts_bridge.py`; each imported
symbol set is exact. The #53 bridge may only validate the exact
Profile/authorization values, construct the closed preflight receipt family,
and reuse fixed operator-entry values. The #54 bridge may only validate the
exact Profile and phase-specific review/publication/verification
authorizations. Neither can issue authorization or widen receipt schemas. The
package has no normal runtime, script, or frontend consumer.
`default_operator_entry()` is mechanically pinned to zero arguments and the
fixed `BLOCKED_NO_APPROVED_COMMAND`, `blocked=1`, `executed=0` result.

`tests/test_cutover_contract_architecture.py` owns the exact package/import/
consumer/mint/default-block checks. The profile, authorization, and receipt
test modules separately pin closed schemas, strict canonical JSON, deterministic
fingerprints, immutable/repr-redacted values, fixed status/count output, and
receipt-not-authorization behavior. All fixtures are synthetic and
content-free; no test may call a real host adapter or inspect Runtime, SQLite,
ACL, repository, worktree, mailbox, provider, vault, credential, or private
data.

### Synthetic cutover journal mechanical guards

`backend/cutover_journal/` has an exact flat module-file and exact public-export
allowlist. `tests/test_cutover_journal_architecture.py` permits only
`dataclasses`, `enum`, `hashlib`, `json`, `__future__`, exact sibling imports,
and the exact `contracts_bridge.py` symbol set. It rejects path/filesystem,
process, SQLite, network, environment, dynamic-import, logging, host I/O,
forbidden builtin loads, callback/`Protocol` surfaces, nested payloads, and
files/functions beyond 300/50 lines.

Public signature guards require inspection to accept an immutable snapshot, not
a medium/store, and require explicit resume/rollback to accept no step,
direction, before/after observation, path, command, callback, adapter, service,
repository, database, provider, mailbox, or vault argument. Recursive consumer
checks require zero references outside the package in `backend/`, `scripts/`,
and `frontend/`.

Behavior guards pin canonical duplicate/unknown rejection, exact sequence and
hash links, full barrier verification, per-claim owner lease,
non-copyable/non-serializable exact-head permit backed by a shared single-use
atomic-token issuance for the round-trip-validated active durable intent,
medium-gated append/restart/mint/claim/effect, stable-head completion before a
successor append or permit, candidate-transition validation before pending
write, exact lost-ack retry, forward/reverse
`INTENT -> EFFECT_OBSERVED -> COMMITTED`, LIFO reversal, fresh authorization
validation and `RESUME_BOUND` renewal, authoritative observed facts,
direction-aware pending recovery, exact Profile/identity/transition mapping,
no blind expected-post retry, inspection immutability, fixed public result
fields, and every transaction/durability crash boundary. All fixtures are
opaque in-memory values and may not access a real host or private capability.

### Windows real-host preflight mechanical guards

`backend/real_host_preflight/` is the Issue #53 read-only composition root. It
has an exact module-file/public-export/import allowlist. Only its Windows-native
observation modules may import `ctypes` or `pathlib`; only
`audit_bridge.py`, `baseline_bridge.py`, and `contracts_bridge.py` may cross
into ContainerAudit, migration-evidence, and cutover-contract packages. No
other package file may import a host core, and no normal runtime, script,
frontend, cleanup, leakage scanner, root wrapper, or workflow may consume this
package.

AST checks permit only reviewed read-only Windows handle, object-identity,
volume, reparse, and security-observation APIs. They reject service control,
ACL apply/setter APIs, rename/move/replace/delete, arbitrary process or command
execution, Git/worktree mutation, Runtime build, SQLite or database copy,
artifact or Config publication, environment/credential access, provider,
mailbox, vault, private-store/private-data, cleanup, scheduler, network, HTTP,
dynamic-import, and content-reader capabilities. Exceptions and native error
text may only collapse to fixed codes; production code may not print or format
paths, SIDs, SDDL, accounts, Git names, file IDs, commands, or callback/native
exceptions into public values or logs.

Portable contract tests pin frozen, slotted, repr-redacted handle observations
with volume identity, 128-bit file ID, exact object type, parent identity,
normalized-name fingerprint, attributes, and reparse metadata. Windows
integration is permitted only beneath a caller-owned `TemporaryDirectory`
validated by an exact in-memory `TestSandboxAuthorizationV1` and a
package-private root/marker identity-bound single-use permit; missing or
replaced markers, wrong phase, permit replay, absolute or parent-relative
escape, hard-link alias, reparse, unexpected volume/filesystem, unreadable
state, and identity drift fail closed. Scope/observer trusted bindings are
module-owned and are not package exports. Linux runs only portable
contract/composition tests and must not claim NTFS, Windows file-ID, Windows
ACL, or real-host evidence.

Behavior guards require `CurrentTopologyPreflight` to complete two full,
identical observations; `PreMutationGate` to repeat source, target-parent,
target-absence, reparse, Git, ACL, and volume checks with fresh UUIDv4 nonce,
short validity, one operation, and single-use state; and
`RealHostBaselineCollector` to preserve distinct source, parent, finance,
volume, operator-SID, and ACL evidence before projecting only a canonical
aggregate `HostBaseline`. Every evidence value must survive exact factory
reconstruction, topology/baseline names must match exact Profile role
selections, and a topology receipt may be atomically claimed by only one gate.
Receipt/gate trusted state is module-owned; public envelopes, caller attribute
mutation, copy, or serialization cannot mint or reset it. The final-audit readiness path may prove only that the
unchanged nine-zone policy and exact seven callbacks are composable. It must not
invoke the pre-cutover audit or claim a final-layout pass, and must revalidate
the identical readers captured by all seven bindings.

Windows sandbox tests cover stable file IDs, source/parent replacement, target
appearance, reparse insertion, expected-volume mismatch, complete-pass drift,
scope escape, marker/permit replay, outside hard-link alias, role-decoy
substitution, and hostile-output leakage. Architecture tests pin the exact
standard-library allowlist, including `threading` and `weakref` only for
module-owned registries, and require the real
operator entry to remain zero-capability and fixed at
`BLOCKED_NO_APPROVED_COMMAND`, with `blocked=1` and `executed=0`; an exact test
authorization cannot enter that seam. Issue #53 performs no real project,
service, ACL, repository/worktree, Runtime, database, artifact, Config,
provider, mailbox, vault, private-data, migration, cutover, or recovery
operation. Issues #57 through #59 remain separate.

### Reviewed Migration Evidence publication mechanical guards

`backend/migration_evidence_publication/` and
`backend/migration_evidence_verifier/` each have exact module-file,
public-export, absolute-import, and relative-import allowlists. Recursive
consumer guards reject both packages from normal runtime, scripts, frontend,
root wrappers, cleanup, leakage scanning, and workflows. The only cross-package
imports are the exact Issue #54 review/create/HostBaseline/contracts bridges,
the parent verification composition's verifier-process imports, and the
verifier's single exact-payload core verify bridge.

The only publication-package hard-link call is the exact
`os.link(marker, anchor, follow_symlinks=False)` in `synthetic_scope.py`.
It is reachable only from the `TemporaryDirectory`- and test-authorization-bound
selection binder. AST guards require the fixed target-parent anchor name,
regular non-reparse identities, exactly two links, and no hard-link call in
any other publication module.

AST capability guards require `creator_bridge.py` to import only the existing
create seam and forbid creator modules from importing or calling the
independent verifier. The verifier bridge may import only
`verify_migration_evidence_payload`, and the worker must pass it the exact bytes
from the first bounded descriptor read before requiring an identical target
reread. Verifier files may not import the publication package,
creator, or core publication modules. They reject package-target write modes,
create, mkdir, link, replace, rename, unlink, remove, rmtree, or deletion calls.
The verifier's only writes are the bounded parent stdin request and child stdout
response; package reads require `O_RDONLY` and a read-only ZIP.

Process guards pin one fixed `sys.executable -B -m
backend.migration_evidence_verifier.worker` launch with `shell=False`, a
sanitized allowlisted environment, fixed request/response byte ceilings,
timeout, stderr discard, strict canonical single response, and whole-process-
tree cleanup. Windows must assign the suspended child to a kill-on-close Job
before resume; POSIX must close the process group before parent reap.

Behavior tests pin the opaque profile-bound selection, exact
`EvidencePublicationAuthorizationV1` plus confirmed review fingerprint,
complete rediscovery and fresh HostBaseline comparison, absent-target
create-only publication, independent package/manifest hash recomputation, and
exact `MigrationEvidenceReviewReceiptV1`/
`MigrationEvidenceCreatedReceiptV1`/
`MigrationEvidenceVerifiedReceiptV1` agreement before
`MigrationEvidenceReceiptSetV1`. The complete review must not serialize or
persist as authority.

Locked-entry guards reject missing, wrong-phase, malformed, and
`TestSandboxAuthorizationV1` values before Issue #39. All package creation and
verification tests use test-owned temporary synthetic sandboxes. Leakage tests
reject path, ref, object ID, worktree name, command, content, native error, or
exception text in receipts, results, `repr`, stdout, stderr, and logs. The
packages expose no real host preflight, service, ACL apply, repository/worktree
move, Runtime build, database copy, provider, mailbox, vault, private-store, or
private-data capability; evidence is never treated as backup, Runtime artifact,
private-data container, or migration authorization.

### Private evaluation mechanical guards

Executable checks must enforce that `backend/private_evaluation/` cannot import
mailbox ingest, raw-vault/private-knowledge stores, SQLite, OpenAI SDK, IMAP, SMTP,
or frontend code. Normal runtime and frontend files cannot reference that package;
only `scripts/manage_mailbox_vault.py` and `scripts/evaluate_private_deepseek.py`
are allowlisted bridges. The mailbox CLI may import only the evaluation
`staging`, `staging_contract`, and `staging_repository` modules for local
`stage-evaluation`; it must not import the runner, provider, final-dataset reader,
metrics, reporting, or selection path.

Mechanical checks must keep `stage-evaluation` outside `NETWORK_COMMANDS`, require
exactly 200 unique reviewed record/case bindings, one record at a time cleanup,
hidden interactive base64 key input with no mailbox app password, and exact
`.pkevalstage` suffix. `scope_fingerprint` and `inventory_fingerprint` are separate
required fields; the evaluation-only source validates the latter before plaintext
release, performs no evidence accumulation, and retains no raw-derived identifier
between records. The real writer/validator test must prove post-replacement checks
exclude only the exact target while sibling and descendant stores remain rejected.
The stage frame has distinct magic, purpose, and namespace from `.pkeval`; public
success is only `evaluation_stage_complete` with 200/0 counts, parse/local failure
is only `argument_invalid`, and repr/errors/output contain no IDs, paths, text,
matches, keys, or exception detail.

Import checks must canonicalize every relative `ImportFrom.level` against the
containing package and apply a positive import allowlist to all modules, not only
`backend.*` names. Unlisted standard-library/network modules such as `ftplib` and
relative escapes into mailbox ingest must fail.

The evaluation CLI must expose only the fixed `build`, `verify`, and `run`
surfaces. It must not accept model, endpoint, key, key-file, namespace, prompt,
case-count, threshold, retry, stream, batch, force/overwrite, transcript,
export/save/output, or production-switch overrides. `--interactive-judge` is
valid only for `run`; without it the command returns fixed
`human_judge_unavailable`. Provider construction must remain a lazy function
reached only after exact confirmation, real local stdin/stdout TTY, fixed exact-y
readiness acknowledgement, hidden key,
dataset decrypt/schema/selection, local judge construction and provider
configuration. Static and unit tests must run offline with the provider disabled.

Mechanical tests must keep `dataset_builder.py` limited to `EvaluationStageV1`
and final schema construction, require a fresh UUIDv4 namespace, exact 200/full
strata/current dual approval/40 Pro validation, and exercise create-only target,
separate-directory, reparse, race and no-partial-write behavior. The same
operator-supplied 32-byte key may cross the stage/final handoff only in the
evaluator CLI; stage/final magic, purpose, namespace and nonce remain distinct.

`terminal_judge.py` must import only the fixed error, `UsefulnessJudgeView`, and
the pure terminal-text safety predicate. It must never reference
`EvaluationCaseV1`, case/actor/dataset IDs, raw
provider JSON, paths, keys, namespaces, approvals, mappings, JSON/filesystem/log
writers or transcript storage. ESC, C0/C1, bidi/format and other terminal controls
must fail before rendering. A fixed exact-y readiness read happens before the hidden
key and clients; the adapter then accepts one exact lowercase `y`/`n` per case;
invalid input, EOF or terminal failure stops before the next provider call with
fixed `human_judge_failed`.

The aggregate serializer must reject unknown keys/codes, boolean counts, non-finite
numbers, arbitrary strings, and nested sample-like fields. Errors, repr, stdout,
stderr, test output, and maintenance output must remain content-free.
The sole stdout exception is the explicit real local TTY judge display of the
already-deidentified input and production-gated public output. The program writes
no transcript and cannot prevent external terminal capture. Only the aggregate-only
report persists; exact 20 Flash + 180 Flash / 40 Pro, zero retry, and no automatic
production model switch remain mechanically pinned.

For the documentation-only V2 contract, focused documentation tests must pin
`PrivateEvaluationCaseV2`, ordered deidentified thread segments, reviewed attachment bindings,
`StructuredHumanReferenceV2`, candidate/reference separation,
a blinded human judge, aggregate-only reporting, and V1 compatibility. No runtime
V2 mechanical rule is activated in Task 9. A later approved implementation must add
schema/import/serialization guards before any V2 dataset can be created or opened,
and those guards must prohibit raw ChatGPT transcripts, automatic training,
automatic upload, model self-grading, and an automatic production model switch.

## Issue #55 static capability rules

Static checks reject command/process ACL surfaces, named-path ACL setters,
replayable descriptor setters, replace-capable move APIs, normal-runtime
consumers, non-fixed adapter methods, and any additional `SetSecurityInfo`
caller. The sole apply call must pass null owner/group/SACL pointers and the
exact DACL plus protected-DACL flags. Public contracts and results remain
repr-redacted and may expose only fixed enums, fingerprints, booleans, and
allowlisted counts. Static checks also require parent-handle-relative
`NtCreateFile` with `FILE_CREATE`, reject `CreateDirectoryW`, and pin the
protected construction guard to one non-inheritable operator ACE without
add-file, add-subdirectory, or delete-child rights.

## Issue #56 static capability rules

Static checks pin the exact `backend/cutover_repository_transaction/` file and
public-export allowlists. Public transaction signatures contain only opaque
scope, closed failure selector, and epoch. No normal runtime, script, frontend,
or workflow consumer is allowed. Only the exact internal bridges may import
`backend.cutover_host_mutation`; only `issue52_bridge.py` may import
`backend.cutover_journal`; only `container_audit_bridge.py` may import the
unchanged ContainerAudit filesystem/Git/worktree policy validators.

AST guards reject copy/clone, deletion, named replace/rename, fetch, reset,
stash, prune, worktree remove/repair, shell execution, arbitrary subprocess,
print, logging, and environment-driven command selection. The sole subprocess
module is the bounded scope-bound Git runner; it must use the reviewed
process-tree owner, fixed operation methods, hook suppression, unsafe-config
rejection, and repeated executable/sandbox identity checks.
Journal/result/repr/stdout/stderr
tests reject path, ref, object ID, worktree/admin name, Git command, opaque
administrative bytes, native error, and exception leakage.

## Issue #57 static capability rules

Static checks pin the exact `backend/cutover_managed_activation/` file and
public-export allowlists. Public APIs remain closed to the exact four adapters
and fixed review/receipt values. Static checks reject service,
repository/worktree, Git, ACL, browser, mailbox, provider, credential, vault,
private-data, cleanup, repair, overwrite, delete, sign, install, load, and
arbitrary-command seams.

AST guards reject pip/index use, `PATH` lookup, system-Python fallback,
environment/config/registry/credential/clipboard readers, socket-capable
builder code, SQLite checkpoint and application-row queries, sidecar deletion,
and replace-capable publication. Only the fixed Runtime subprocess surface may
exist; it uses the reviewed source/new Runtime executable,
`-X frozen_modules=on -I -B -S`,
sanitized environment, closed stdin, incrementally bounded stdout with
overflow termination, and no shell. Wheel
members named `.pth`, `sitecustomize.py`, or `usercustomize.py` are rejected.
The complete CPython source tree is canonical-manifest bound, reparse/ADS
checked, held against write/delete sharing, and recursively monitored before
execution. Source/wheel/lock capture uses held-handle size and
remaining-aggregate gates. EOCD and central-directory limits precede
`ZipFile`; wheelhouse and Runtime directory limits precede collection/sorting.
One bounded deterministic ZIP_STORED `managed-startup.zip` contains the complete
approved `Lib/encodings` package streamed from held source handles. Code-fixed
create-only `python312._pth` and `python._pth` sentinels order that immutable
archive before `Lib`/`DLLs`, omit `import site`, and are held before target
execution.
Exact package/export guards and the normal-runtime executable-import consumer
guard cover recursive payloads, equivalent imports, relative imports, dynamic
import aliases, and package/function size bounds. Runtime tree guards reject
junction/reparse members, alternate data streams, unsafe Windows components,
and every extra/missing/changed file or directory. Fixed archive/tree ceilings
and bounded streaming reject member-count, expanded-size, compression-ratio,
entry-count, file-size, total-byte, path, and depth exhaustion. The new
Runtime verifier may import only built-in `sys`, `nt`, `_sha2`, and `_imp`;
it must prove `_imp.is_frozen("codecs")` before its audit hook rejects every
later import. It hashes exact Python/SQLite/startup-ZIP/lock/import
files and parses bounded exact distribution metadata but never imports or
executes installed package code. A recursive Windows parent-directory change guard rejects even
transient child or root-stream mutation before a receipt can return. Result,
receipt, repr,
stdout, stderr, and error tests reject paths, filenames, domains, package
names, Config values, exception text, source bytes, and private data.

## Issue #58 static capability rules

Static checks pin the exact `backend/cutover_service_lifecycle/` adapter fields,
public exports, per-module import map, every `ImportFrom` module/symbol/alias,
module-size bound, and every non-package consumer under `backend/`, `scripts/`,
`frontend/`, and workflows. Nested, direct, aliased, rebound, and dynamic
import forms are covered. The legacy adapter must not expose analysis,
database-write, Config mutation, launcher selection, retry, provider,
environment, path, or command fields.

AST guards reject `os`, `pathlib`, `subprocess`, `socket`, `sqlite3`, `ctypes`,
network, logging, dynamic import, file-open, shell, service-discovery,
repository/worktree, and normal-runtime imports from the lifecycle package.
Only pure standard-library value helpers plus exact Cutover contracts and
Issue #57 receipt types are allowed.

Focused tests pin the complete Issue #57 operation/Profile/master/
authorization chain, every start/health identity field, provider-attempt
rejection, fresh UUIDv4 nonces, deterministic-rules-only activation, exact
matching row count, every reverse stage, immutable rollback-plan evidence,
unexpected-exception containment, fixed legacy failure, real-lock statuses,
and content-free repr/stdout/stderr/errors. Windows sandbox tests compose the
actual synthetic #56 forward/reverse seam, resume every committed reverse
boundary, reject failed-Container collision, and make no real-host claim.

## Issue #59 static composition rules

Static tests pin the exact file and public-export allowlists for
`backend.cutover_composition_contracts` and the three operator-root packages.
The roots may import only their own modules, the pure composition contracts,
and exact Issue #51 contract values. The roots cannot import one another;
preflight cannot import mutation packages; evidence cannot import unrelated
adapters.

The same guards require executable sandbox assembly to exist only under
`tests/`, normalize relative and `from backend import ...` forms, and reject
qualified dynamic capability lookup such as `builtins.getattr` in composition
code. Test-only assembly accepts no caller-selected root and becomes invalid
when its internally owned temporary scope closes. Scope closure first marks
an irreversible inactive state under one lock, then cleans all owned
directories; cleanup failure cannot reactivate it. Every role/journal callback
holds the same scope lease from liveness check through callback completion.

Recursive consumer guards scan normal runtime, frontend/browser, scripts,
cleanup, scheduler, and workflows. AST guards reject filesystem/path,
subprocess, shell, PowerShell, socket, SQLite, logging, dynamic import, and
arbitrary Git/command capability. Public entry signatures and exact nominal
role dataclasses reject source, target, worktree, database, Runtime, artifact,
Config, ACL, rollback, shell, PowerShell, Git command, varargs, kwargs,
mapping, subclass, duck-typed, or extra-field surfaces. Composition code cannot
use dynamic capability lookup.

Focused tests require exact phase authorization for every real constructor and
entry, reject `TestSandboxAuthorizationV1`, and pin valid pre-#39 results to
`BLOCKED_NO_APPROVED_COMMAND`. Receipt tests pin exact operation/Profile/
master/operator/authorization-sequence binding, approved partial prefixes,
predecessor and prior/current journal-head order, per-boundary freshness,
cross-composition gate claims, terminal receipt commitment,
terminal success/recovery shapes, closed counts, and content-free
serialization. Coverage guards retain the complete #53-#58 race,
crash-gap, and no-clobber owners.

The Windows E2E module is explicitly `win32`-gated, uses only caller-owned
temporary sandboxes, and routes forward ACL-through-activation roles through
transaction `execute()` before rollback. Portable tests are mechanically
barred from claiming
NTFS or Windows ACL proof. Leakage tests cover receipt/chain JSON and repr,
fixed exceptions, stdout, stderr, and logs.

## Issue #70 static contract rules

Static tests extend the exact `backend/cutover_composition_contracts` file
allowlist with only `approved_binding.py`, `r2_types.py`, and `r2_receipt.py`.
Focused behavior pins canonical round trips, duplicate/unknown-field rejection,
Profile-derived immutable binding, four nominal authorization domains, separate
managed PREPARE/PUBLISH boundaries, quiescence/audit/two-start/recovery vocabulary,
the exact pending-effect tri-state, exact terminal outcomes, content-free receipt
fields, and the absence of any receipt-to-authorization relationship.

The existing Issue #59 root export, import-isolation, public-signature,
consumer, dynamic-capability, real-lock, Windows-gating, and leakage guards remain
unchanged. Adding these pure contract files does not authorize a process, host
adapter, signer, issuer, path selector, or executable test binder.

## Issue #71 static process and authorization rules

Static checks pin the dedicated preflight package, exact six-verb catalog, fixed
result fields, and the absence of an option parser, umbrella selector,
subprocess, shell, PowerShell, filesystem selector, environment authorization
reader, or authorization-file reader. Its executable root remains physically
isolated from the evidence and transaction roots, and normal runtime, frontend,
scripts, cleanup, scheduler, and workflows must not consume it.

The historical operator-envelope surface is removed. Static guards reject V1
or V2 envelope, key, signature, issuer, compatibility, and fallback code. The
V3 binding and execution-confirmation values are capability-free. Issue #39
permits them only inside its fixed orchestrator graph; the three standalone
process roots remain dormant and cannot consume them.

Focused tests pin unconditional `DORMANT_NO_ISSUE39_APPROVAL` before TTY,
candidate, confirmation, Adapter, or callback access, fixed public fields, and
redirected-stream irrelevance. Windows console tests exercise only dormant
behavior; no Issue #110 test claims real execution authority.

## Issue #72 static evidence-process rules

Static guards pin the exact evidence package file set, the sole `publish` verb,
its one-argument signature, evidence-specific acknowledgement, fixed result
fields, and disjoint imports from preflight, transaction, and the verifier.
They reject target/source/path/Profile/review/journal/recovery/force selectors,
option parsers, arbitrary subprocess or filesystem calls, environment/file
authorization ingress, signing code, and any normal-runtime synthetic-binder
consumer.

Behavior tests retain pure execution-confirmation domain/type/operation,
closure, attestation, expiry, and replay contracts, but the production root
returns `DORMANT_NO_ISSUE39_APPROVAL` before capability acquisition. Portable
and Windows cases make no live publication or Issue #39 authority claim.

## Issue #73 static transaction-process rules

Static guards pin the exact third package and its `execute`, `resume`, and
`rollback` catalog verbs, reject all path/Profile/journal/recovery-target/
force/shell/PowerShell/Git inputs, and prove no preflight/evidence root import
or normal synthetic-binder consumer exists. The pure dormant confirmation
schema names the V3 binding, closure, attestation, current head, next sequence,
remaining plan, transition, reverse plan, and one action nonce.

Behavior tests cover structural execution/recovery domain separation and
replay/fingerprint blocks without invoking an Adapter. Production behavior is
exactly `DORMANT_NO_ISSUE39_APPROVAL`; no fresh-console case executes a host
action in Issue #110.

## Issue #74 static main-publication rules

Static guards pin the absence of a real entry, argv, subprocess, shell,
PowerShell, copy, replace, delete, cleanup, and any import from the three
operator roots. They permit the existing cutover contract, journal, and host
mutation packages only through exact reviewed files and keep the new testing
binder out of normal consumers.

AST inspection permits exactly one native DACL setter. Its Owner, Group, and
final arguments must be literal null values; source text may not name a
system-audit ACL information constant, named/tree security setter, or command
ACL tool. Backend module and function size checks continue to apply.

Behavior checks pin nominal construction, repr redaction, double-stable and
short-lived single-use readiness, closed restart/gap vocabularies, inherited
projection provenance, detection of preserved same-volume descriptors,
authoritative whole-tree conformance, exact Owner/Group equality, committed
`MAIN_PUBLISHED`, all 45 physical boundary/gap combinations, no-replace exact
rollback, collision incident stop, reparse rejection, and the unchanged real
operator locks.

## Issue #75 static manifest/worktree rules

Static guards allow the new package to consume only exact reviewed files from
the cutover host-mutation and repository-transaction packages. They reject an
executable entry, operator-process imports, subprocess, shell, arbitrary Git,
clone/copy/fetch/history-rewrite/stash/prune/repair/remove/delete/replace
markers, dynamic import, and any normal-runtime consumer. Existing #51/#52/#55/
#56 consumer allowlists are extended only for the named test-binder modules.

Contract tests pin the three positive manifest categories and closed directional
boundary/gap vocabulary. Windows behavior tests require exact selected/residue
partitioning, whole-versus-mixed directory handling, one Repository Root,
exactly eleven outside-root linked worktrees, preserved original physical/admin
identities, forward and reverse durable facts, failed-Container preservation,
all five crash gaps at manifest/worktree endpoints, resumable reverse gaps, and
the sole terminal reverse status `LEGACY_FLAT_LAYOUT_RESTORED`.

## Issue #76 static quiescence/database rules

Static guards pin the closed pathless exports, absence of a real entry and
normal-runtime consumer, exact four sidecar checkpoint names, and nominal
non-constructible stopped receipt and copy lease. They reject subprocess,
shell, PowerShell, SQLite checkpoint/truncation, cleanup/deletion, and adjacent
mail/private capabilities. Native inspection requires `FILE_SHARE_READ` and
forbids write/delete sharing constants. Backend module and function size limits
continue to apply.

## Issue #77 static Runtime-unit rules

Static guards pin the closed pathless exports and exact allowlist of reused #57
modules. They reject `pip check` as a second authority, network/index/cache,
system-Python/user-site/legacy-environment fallbacks, retry, cleanup, replace,
arbitrary process inputs, real entries, and normal-runtime test-binder
consumers. Module/function size rules continue to apply. Behavior tests cover
all eight PREPARE/PUBLISH gaps plus collision, source/dependency drift, reparse,
self-verification failure, content-free classifications, and exact recovery.

## Issue #78 static CRX-unit rules

Static guards pin the closed pathless package exports and its single reviewed
native-handle dependency. They reject archive/build, browser/profile,
signing/private-key, installer/loader, subprocess/shell, arbitrary entry,
overwrite, deletion, replacement, cleanup, and normal-runtime binder
consumers. Behavior tests pin exact CRX format/size/hash/identity, handle-held
write/delete denial, the durable four-fact chains, tri-state recovery, pending-
generation rejection, all crash gaps, and retained failure states.

## Issue #79 static Config-unit rules

Static guards pin the exact pathless exports and three reviewed dependencies:
the Managed Config builder, Managed settings reader, and fixed native handle.
They reject environment/`getenv`, dotenv loading, registry, clipboard,
credential/keyring/getpass, legacy Config, direct secret assignment,
subprocess/shell, arbitrary entry, replacement, deletion, cleanup, and normal-
runtime test-binder consumers. Behavior tests pin the exact two-line UTF-8/LF
document, hostile-environment independence, loader reconstruction, four-fact
journal boundaries, tri-state recovery, all gaps, and retained faults.

## Issue #80 static independent-audit rules

Static guards pin the five-file pathless package, exact nominal receipt
issuance inside the single-use sink, and absence of any transaction or normal-
runtime consumer. They reject path and arbitrary I/O capabilities, receipt
construction in the process, serialization/reset surfaces, subprocess/network,
provider, mailbox, vault, private-knowledge, migration-evidence, registry,
clipboard, credential, and database access. Behavior tests pin distinct fresh
process IDs, exact kind binding, one append, 300-second freshness, replay and
sink-swap incident stops, deterministic rollback classification, and complete
fresh invocation after expiry. Module/function size rules continue to apply.

## Issue #81 static validation-lifecycle rules

Static guards pin the four-file dormant package, exact approved-slice imports,
single-use eleven-boundary order, provider-disabled identities, and absence of
normal-runtime consumers or a real entry. They reject subprocess, SQLite,
filesystem, environment, network, provider, mailbox, vault, private-data,
arbitrary command, and cleanup capabilities in production modules. Behavior
tests pin exactly one `rule_fallback` result, one confirmation, one database
write/row, exact stop and final database proof, two distinct service starts,
two distinct fresh audit processes, no Start B analysis/write, and all 33
boundary fault classifications. Module/function size rules continue to apply.

## Issue #82 static cross-stage recovery rules

Static guards pin the four-file dormant package, the read-only inspection
method, fixed seven-boundary reverse order, exact five-callback adapter, no-
cleanup result, and #80/#81 contract dependencies. They reject subprocess,
filesystem, SQLite, environment, network, arbitrary journal, delete/replace/
cleanup, real entry, provider, mailbox, vault, and private-data capabilities.

Behavior tests pin double-read tri-state classification for pending and
committed facts, receipt predecessor/head validation, failed-Container-first
order, exact fresh authority and unique crash nonce at each boundary, skipped
already-observed reverse effects, all reverse crash positions, failed legacy
recovery incident-stop, sole rollback success status, audit/head/nonce/identity
freshness, one `CUTOVER_SUCCESS` append, zero final host mutations, and single-
use invocation. Module/function size rules continue to apply.

## Issue #83 static full-verification rules

Static guards pin the exact three-file `backend.r2_verification_evidence`
package, the fixed 70-case vocabulary, closed bundle fields, six distinct
fingerprints, and the no-argument verifier entry. They reject argv selectors,
external roots, environment authority, arbitrary commands, network/provider/
mailbox/vault/private-data access, cleanup/delete/replace, dynamic imports,
normal-runtime consumers, and public output beyond fixed status, hashes, and
allowlisted counts.

Obsolete-surface tests recursively reject R2 reachability of batched managed
publication, stale R1 verification, in-process-only operator substitution,
self-certified audit receipts, and any legacy R2 success terminal. Windows
behavior tests own every sandbox and require real TTY channels, distinct
test-worker success proofs, separately locked production entries, quiescence
before operational mutation, distinct service/audit processes, exact registered
nominal receipts, complete canonical receipt mappings, pre-lifecycle
predecessor/head recomputation, durable final-head re-observation, and transitive
hashing of every local verifier input. The
70-case count must be returned by executed semantic dispatch, never a verifier
literal. Portable tests explicitly make no native evidence claim. Existing
module/function bounds continue to apply.

## 14. 修改规则

## R2 Solo Maintainer Closure guards

Static and architecture checks must pin the exact ten-file
`backend/r2_solo_maintainer_closure/` inventory, explicit `__all__`, controlled
imports, and capability split. Canonical contracts remain pure; `repository.py`
alone uses fixed read-only Git/anonymous hosted acquisition and delegates protection
state only to private `github_guardrail.py`; `github_guardrail.py` alone owns fixed
authenticated GET-only observation, private `local_evidence.py` alone reruns
frozen-tree-bound status/maintenance/leakage observations, and `storage.py`
alone publishes the two code-fixed create-only files.
No module may gain provider, mailbox, vault, private-data, credential, signer,
private-key, cleanup, deletion, overwrite, Issue #38 approval, ruleset mutation,
or Issue #39 execution capability.

Mechanical checks pin five hosted checks, fourteen evidence kinds, eight
dependency-ordered gap proofs, the exact guardrail snapshot, and the manifest
and attestation schemas. All records must bind one commit, tree, source package,
runbook, workflow family, guardrail fingerprint, and V3 production binding.
Missing, duplicate, unknown, reordered, stale, mixed, skipped, leaking,
provider-active, host-active, approval-bearing, execution-bearing, or legacy V1
evidence fails closed.

The protected verifier must retain its fixed no-argument raw-Git trust chain.
It validates only the same new manifest and attestation files, rejects every
legacy V1 external/signature surface, and never converts evidence into an
authority, command, ticket, ruleset change, host effect, or cleanup action.

如果新增或修改 linter 规则，必须同步更新：

```text
docs/constraints/linter_constraints.md
docs/conventions/logging.md
tests/test_static_linter_constraints.py
```

如果 linter 规则会影响架构边界，还必须同步更新：

```text
docs/constraints/architecture_constraints.md
```
## Historical Issue #91 callback guards (superseded by Issue #104)

- The three `r2_*_process/__main__.py` files must import only their local
  `production_v2.main`; the historical V1 `entry.py` lock must not be on the
  executable production path.
- Production modules must not import a synthetic context, `testing.py`, a test
  binder, an issuer, or a private signing key.
- Default fixed-verb entry returns `DORMANT_NO_ISSUE39_APPROVAL` before any TTY
  read, candidate construction, acknowledgement parsing, Adapter lookup, or
  Adapter verification/invocation. No CLI argument, path, environment value,
  artifact, acknowledgement, bootstrap mapping, or synthetic marker can unlock
  this state.
- `ApprovedCutoverBindingV3` and the execution-confirmation contracts remain
  dormant primitives outside the production process graph. The Issue #39 code
  allowlist permits only the fixed orchestrator graph to validate a fresh
  confirmation and invoke its exact catalog-owned action. The historical
  standalone roots remain dormant. `main()` accepts no terminal or clock
  injection.
- Production role fingerprints must bind normalized top-level function code,
  defaults, keyword defaults, function state, recursively referenced globals and
  builtins, and exact command-parameter type surfaces. Closed semantic frames
  cover helper dependencies, referenced module non-dunder namespaces plus
  executable loaded globals, non-built-in MRO-owner executable surfaces,
  scalar/object constants, custom metaclass construction, object state, and
  exact parameter-method loaded globals. Tests must prove alias/branch/helper/
  container/cross-module, parameter helper/configuration, class-state,
  constructor, `JSONEncoder`, and default-encoder drift fail before invocation.
  Traversal-wide attribute closure must fail closed for accessed loaderful
  nested modules through alias/helper/container paths; exact `type` descriptors
  must bypass metaclass identity/namespace/MRO spoofing; module `__doc__` drift
  must bind. Custom instance `__dict__` descriptors and custom/nonempty
  dataclass metadata must be rejected without execution or iteration, dynamic
  private-attribute string adapters must fail, and `re.LOCALE` is forbidden.

## Issue #104 production Adapter guards

- The executable process graph must import Adapter bindings from
  `backend.r2_production_composition`; it must not expose or reconstruct the
  removed callable-role seam.
- The catalog must contain exactly ten command registrations grouped into three
  Adapter slots: six preflight, one evidence, and three transaction commands.
- Production Adapter identity must bind exact command, authority domain, type
  module/qualified name, and complete owning-module source. It must not include
  mutable Adapter instance state.
- Every process must verify authority, reverify the Adapter, invoke it, validate
  its underlying outcome, and only then invoke and validate the completion
  helper. A failure at any step must remain content-free and fail closed.
- Candidate construction accepts only the exact final-master binding and the
  closed V3 structural facts. It accepts no verification key, signature,
  envelope, path, environment, private-key, signer, issuer, credential, host,
  provider, vault, artifact, or arbitrary identity capability.
- Production bootstraps must reject the test-only synthetic marker. Production
  modules must not import their local `testing.py` modules.

## Issue #110 Solo Maintainer Closure and execution-confirmation guards

- `scripts/close_r2_final_master.py` exposes exactly `prepare` and `confirm`.
  `prepare` performs no TTY read and no write. `confirm` is Windows-only and
  requires real stdin/stdout/stderr consoles, stable `GetConsoleMode` handles,
  the exact manifest fingerprint, and the exact acknowledgement, each shown or
  read once within the half-open 300-second wall/monotonic window.
- The CLI has no repository, destination, endpoint, credential, key, signer,
  issuer, clipboard, cleanup, or arbitrary filename option. It must not claim
  to prevent operating-system paste or terminal capture. It has no clipboard API.
- Publication is limited to the exact manifest and attestation filenames under
  `<git-common-dir>/r2-solo-maintainer-closure-v1/`. Staging and final creation
  are no-replace and all-or-nothing; a collision or failure retains the stage
  and never overwrites, deletes, or cleans up an existing object.
- Static guards pin the final stable parent/child/DACL/oplock observation and
  immediately following exact-target no-replace rename as the publication
  linearization boundary. No guard may claim atomic arbitrary-sibling exclusion
  against an uncooperative writer. A legacy or other-stage sibling created
  strictly after that linearization is a
  subsequent incident rejected by the verifier.
  No Git-common DACL mutation, kernel filter, or volume lock is authorized.
- `ApprovedCutoverBindingV3` removes all signature/key/envelope semantics while
  preserving exact command, domain, production-role, Adapter, final-master, and
  assurance facts. `ExecutionConfirmationV1` binds the exact closure manifest,
  solo attestation, command/action, prior journal head and sequence, transition,
  remaining/reverse plan, same-real-TTY acknowledgement, and a 300-second
  validity window. Append is create-only, attempt consumes it, and replay fails.
- The old final-master closure, global-gate, external-artifact, signature,
  envelope, dormant-context, and process-entry surfaces must be recursively
  absent. No compatibility export, dual parser, fallback, or OR trust path is
  permitted.
- Static documentation guards preserve the separate approval boundaries:
  current ruleset `20601214` does not authorize closure; closure evidence does
  not approve Issue #38, create or approve another ruleset,
  authorize or execute Issue #39, mutate a host, access provider/mailbox/vault
  data, or perform cleanup. Live `prepare`, `confirm`, the protected verifier
  and any future Issue #39 code path each require separate approval.

## Issue #39 fixed orchestrator static boundary

The approved Issue #39 code allowlist permits only the fixed `backend.r2_issue39_orchestrator` composition root, `scripts/execute_project_container_cutover.py`, and its package-owned retained restart runner.

- The only executable production consumer of the reviewed cutover primitives is
  `backend.r2_issue39_orchestrator`, reached only through
  `scripts/execute_project_container_cutover.py`. Reject direct and indirect
  imports of the package or fixed script from normal runtime, frontend,
  workflows, mailbox, provider, vault, private-store, cleanup, and every other
  script. Pin the complete fixed script source and the actual retained
  `__main__.py` archive argument; an unused matching import or bytes constant is
  not sufficient.
- The script and CLI accept exactly `run`. Reject argparse/path/root/source/
  target/force/cleanup/adapter/callback/environment/endpoint/provider/mailbox/
  vault/credential/private-data surfaces and reject imports of those
  capabilities.
- Pin the initial launcher to
  `D:\Projects\email_ai_assistant\.worktrees\issue39-governed-enablement` and
  require its plain original/resolved root, current directory, and ordinary
  single-link script checks before the orchestrator import. Reject alternate,
  legacy-root, copied, environment-selected, or reparse launchers.
- Require every module that calls the generic V3 confirmation inside Issue 39
  to first display one strict `ISSUE39_CONFIRMATION_CONTEXT_V1` projection.
  Its phase/operation/command/direction/state/sequence vocabulary is closed,
  printable ASCII and content-free; reject path, free-form, newline, control,
  or caller-supplied values.
- The catalog values have module-owned constructors and exact phase-plus-name
  dispatch. Reject public registration, caller-created catalog values,
  prefix-only handler selection, dynamic import, `eval`, `exec`, shell strings,
  and arbitrary subprocess commands.
- Pin the incident binding to the exact retained
  `.r2-solo-maintainer-closure-v1.incident-794aea72b0012d1de728f3b87f7f25c2f7c9ae3ac8f66777845010635fc69721`
  leaf under the two fixed parents. Reject the obsolete `.stage-...` spelling,
  aliases, discovery, enumeration, caller paths, and alternate leaves.
- Pin archive-parent production code to the exact components
  `D:\IncidentArchives\email_ai_assistant\issue38` and parameterless observer/
  provisioner entries. Reject public paths, configurable components or DACLs,
  path-based `mkdir`, replace/open-if semantics, non-NTFS, reparses, inherited
  or extra ACEs, drive-root ACL changes, and automatic partial-state cleanup.
  Require the parent-state/presence/identity fingerprint before incident
  confirmation, exact reproduction before create, and held-chain revalidation
  through rename and artifact reread. Native tests stay under test-owned
  temporary Windows objects.
- Production dynamic-roster code is versioned separately from the historical
  fixed-eleven rehearsal contracts. Static checks must preserve the old exact
  assertions and require the new code to bind complete bounded discovery rather
  than a caller-supplied count or selection.
- Production repository review must bind every regular stage-zero index OID and
  the exact raw working-tree size/SHA-256 used by relocation. Permit only raw
  blob equality or the code-owned CRLF-to-LF projection with no NUL or remaining
  bare CR and exact projected index-OID equality. Unlock projection only for an
  include-free exact true repository/worktree mode or, absent that override,
  the fixed Git system true mode. Require filter-free HEAD-tree/index/ordinary-
  flag/untracked clean-state evidence and stable index/config/source-absence
  evidence before and after review. Reject tracked `.gitattributes`, fixed
  `.git/info/attributes`, repository/system `core.attributesFile`, `check-attr`,
  Git filter execution, encodings, normalizers, paths, hidden index flags,
  dirty state, or index/config/source drift.
- Real-console, incident, journal, evidence, native host, Runtime, database,
  service, and audit capabilities remain in their narrow owning modules. Test
  helpers may inject only closed synthetic values and test-owned temporary
  roots; no production entry imports `testing.py`.
- Public output is fixed and content-free. The success path contains exactly
  `PROJECT_CONTAINER_CUTOVER_SUCCEEDED` after terminal sealing, and exception,
  path, SID, DACL, command, PID, port, database row, provider, and private-data
  detail must not be rendered.
- Existing backend module and function size checks continue to apply. Any
  deliberate security-sensitive parser or native-adapter exception must remain
  locally documented and must not become a general size exemption.
