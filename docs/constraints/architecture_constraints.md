---
last_update: 2026-07-27
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
all descendants. An explicit trusted Standalone placement preserves both its
Repository Root and state root; the context is not accepted from a public,
environment, config, browser, or CLI surface. The layer owns no directory
mutation, launcher routing, container audit, mailbox, provider, credential, key,
vault, recovery, private-store, ACL, volume, or host-security capability.
Returned values contain only path metadata.

The `Managed runtime adapter` is a separate normal-service launcher boundary in
`backend.email_agent.managed_runtime`. It consumes validated placement/layout
values, validates pre-existing ordinary zones and writable targets, performs one
bounded descriptor-bound read of an exact non-secret Config allowlist, and
creates only the request attachment subdirectory. It returns a provider-disabled
`AppConfig` plus absolute ordinary paths. It owns no arbitrary-root input,
mailbox, provider, credential, private-store, migration, audit, ACL, worktree,
artifact-copy, or repository-tooling capability.

The `ContainerAudit layer` is a separate pure manual validation boundary in
`backend.container_audit`. It accepts only a frozen trusted content-free policy
and exactly seven injected metadata callbacks. It fixes the nine direct
top-level entries, Config key allowlist, metadata bounds and roles, runtime and
SQLite expectations, public status/count schema, and two-pass stability checks.
Evidence contains opaque identities/fingerprints, fixed names/enums, bounded
sizes/counts, and relationship/completeness flags only.

Issue #34 supplies no path input, real/default adapter, host probe, CLI,
composition root, service hook, scheduler, mutation, or diagnostic output.
The package may import only its own modules plus `dataclasses`, `enum`, and
typing support. Normal runtime, cleanup, leakage scanning, browser/frontend,
root wrappers, and workflows must not reference or invoke it. Issue #53 adds one
exact external read-only composition bridge without changing this layer's
policy or imports; a real final-layout pass remains separately authorized later
work.

The `Migration Evidence layer` is a separate offline manual boundary in
`backend.migration_evidence`. Its only public operations prepare an exact review
value, create one separately confirmed no-clobber package, and independently
verify one package. The module may read only local Git metadata/objects and
exact approved source/tests/docs through bounded readers; ACL and volume data
arrive only as content-free reviewed fingerprints. It cannot import normal
runtime, lifecycle, mailbox, provider, SQLite, private-knowledge/evaluation,
vault, credential, frontend, cleanup, or scheduler capabilities.

The bundle source is exact reviewed local `refs/heads/*`. Dirty snapshot records
bind the source-root worktree plus separate stage-zero regular index and
worktree layers. A content-free selection manifest records every
included/excluded status and reason; the canonical package manifest binds it,
Git/worktree/host evidence, the independently verified bundle, snapshot index,
and every payload. Package publication is a single external create-only commit;
no target inside any selected worktree is valid.

No backend service, browser/frontend, root wrapper, script, maintenance scan, or
workflow may import or invoke this layer. Issue #36's
`backend.reparenting_rehearsal.evidence_bridge` is reachable only inside a
self-created temporary synthetic scenario and may call the reviewed package
seams. Issue #53's exact `backend.real_host_preflight.baseline_bridge` may import
only `HostBaseline`; it cannot call review, create, or verify. Issue #54 adds
only the exact publication `review_bridge.py` and `creator_bridge.py`, plus the
physically separate verifier package's `bridge.py`. Those bridges import only
their single reviewed prepare, create, or verify capability. The leakage scanner
recognizes only the reserved package suffix so an accidental repository package
fails; it is not a package creator or reader. Any real capture remains a manual
review and separately authorized confirmation operation outside normal runtime.

The `Reparenting Rehearsal layer` in `backend.reparenting_rehearsal` is a
synthetic-only deep module. Its single public operation accepts only the complete
fixed linked-worktree choice set and a fixed failure-boundary enum. It accepts
no path, source, target, repository, environment, reader, host adapter or
callback, and it creates its own OS-temporary sandbox. The marker's filesystem
identity is captured at creation with a fixed sibling hard-link identity anchor
and revalidated before publication; same-text replacement, including attempted
inode reuse, or alias/reparse drift fails closed. The complete synthetic project,
including the exact local-only remote, is revalidated immediately before
and after review/baseline capture; the captured remote hash must equal the fixed
local bare remote rather than merely becoming a new baseline.

Inside that sandbox only, the module may initialize local synthetic Git state,
create and verify one Issue #35 evidence package, perform checked no-clobber
renames, repair or recreate linked worktrees from reviewed choices, compare the
captured Git/source baseline, and compose synthetic metadata for Issue #34
ContainerAudit. The only cross-layer imports are
`evidence_bridge -> backend.migration_evidence`,
`audit_bridge -> backend.container_audit`, and
`layout -> backend.project_layout`. It has no normal-runtime, browser, script,
workflow, cleanup or leakage consumer and no mailbox/provider/vault/private
store/credential/ACL/runtime/database capability.
After any main/worktree/audit publication injection, the complete Container is
renamed without clobbering to the single sibling rollback path, reviewed linked
metadata is repaired there, and baseline/evidence verification is repeated.
The public operation never deletes or cleans up the preserved synthetic
topology; caller-owned test teardown occurs only after independent observation.
All fixed linked-worktree targets must be absent before the first worktree or
administrative move. Their direct `Worktrees` parent must retain resolved
containment and be a non-reparse directory; Git may not populate a pre-existing
empty directory or follow a junction outside the Container.

The `Managed Runtime Activation Rehearsal layer` in
`backend.runtime_activation_rehearsal` is a synthetic-only deep module. Its sole
public seam is
`rehearse_managed_runtime_activation(*, adapters=...)`; the exact bundle contains
runtime, filesystem, database, lifecycle and probe adapters with no defaults.
The seam accepts no path, repository, source, target, environment, failure
selector, reader factory, CLI value, or ambient state, and there is
no default host adapter.

The package fixes Python 3.12.13, SQLite 3.50.4, the exact dependency lock,
Managed roles, both disabled provider routes, literal loopback health and one
persisted `rule_fallback` analysis. Frozen repr-redacted evidence binds the
actual temporary synthetic topology. A Windows venv is represented only as a
network-free rebuild at `Runtimes\venv\Scripts\python.exe`; the service start
must echo that exact venv and executable identity. Lifecycle-manager stop output
and an independent stopped probe must echo the code-fixed `pre_publication`
phase before every SQLite publication. Start, health and analysis then echo one
fresh activation nonce bound to that stopped gate. Final stop and probe
must echo it under `post_activation`, use a fresh stop token and bind the same
service identity before post-analysis database/source checks.
Database and reviewed browser-extension publication are create-only and require
stable, distinct identities plus SHA-256/integrity/sidecar/count or reviewed-hash
cross-checks.

The production package may import only standard-library value helpers and its
own modules. It may not import or expose filesystem, SQLite, process, network,
provider, mailbox, vault, private-store, credential, signing-material,
ContainerAudit, migration-evidence, cleanup, delete, move, overwrite, or
rollback capability. No normal runtime, script, frontend, wrapper, cleanup,
leakage scanner, or workflow may import or call it. Tests alone own
`issue37-synthetic-*` temporary sources/destinations and may dispose of their
parent only after source, legacy, competitor and no-forbidden-access assertions.
Race, reparse, existing-target, dependency, integrity and health failures all
return the same aggregate-only failure and never authorize source cleanup.

The `Cutover Contract layer` in `backend.cutover_contracts` is an internal,
pathless, content-free value boundary for Issue #51. It owns one immutable
`CutoverProfileV1`, four exact externally supplied real-host authorization
types, one exact-type authorization validator, one canonical
`ReceiptEnvelopeV1`, one synthetic test authorization type, and the fixed
blocked `default_operator_entry()`. Profile and receipt creation or parsing
perform only closed validation, canonical JSON serialization, and SHA-256
identity checks.

The real-host authorization classes have no public or internal issuer, create,
mint, generate, sign, random, secret, or clock capability. Their canonical
fingerprints are integrity identities, not signatures or grants of host
authority. Exact-type validation rejects mappings, receipts, test
authorization, subclasses, and duck-typed objects. Receipt creation or parsing
never authorizes an operation, and the default operator seam accepts no
capability and always returns `BLOCKED_NO_APPROVED_COMMAND`.

The package imports only pure standard-library value helpers and its own
modules. It cannot import or expose path/filesystem, process, SQLite, network,
environment, Git, ACL, browser, mailbox, provider, vault, private-store,
credential, authority-store, adapter, logging, scheduler, dynamic-import, or
host-mutation capability. Its approved consumers are the exact
`backend/cutover_journal/contracts_bridge.py` and
`backend/real_host_preflight/contracts_bridge.py`, plus Issue #54's exact
`backend/migration_evidence_publication/contracts_bridge.py`; no script,
frontend, executable operator surface, or normal runtime consumes it. Consumer
guards still reject every other static/dynamic import form.

The `Synthetic Cutover Journal layer` in `backend.cutover_journal` is the Issue
#52 state-machine boundary. It owns strict canonical hash-chained records,
exact in-memory Windows/Linux durability traces, per-claim synthetic ownership
leases, non-copyable/non-serializable exact-head effect permits backed by shared
single-use atomic-token issuances, one synthetic medium operation gate, fixed
forward/reverse transitions, read-only restart
inspection, and explicit
authorization-aware synthetic resume/rollback. It accepts no path, callback,
duck-typed adapter, host reader, service, ACL, Git/worktree, Runtime, SQLite,
provider, mailbox, vault, private data, CLI, HTTP route, or production consumer.

Only a fully namespace-barriered `INTENT` may precede a synthetic effect;
pending and unbarriered records never authorize action. Exact expected-post
inspection may append observation/commit only and cannot repeat the effect.
Every namespace-published current head must complete stable reread and full
snapshot reverification before a successor record or head-authorized permit.
Durable observed facts are authoritative; pending forward/reverse direction,
Profile/master/operator binding, identity mapping, and the fixed synthetic
transition mapping are verified again by the action seam. A fresh resume
authorization may renew `RESUME_BOUND` but cannot replace an observed outcome.
Reverse intent is derived LIFO from verified `COMMITTED/APPLIED` history and
uses the pre-bound recovery fingerprint. Unknown observation, identity drift,
authorization mismatch, or chain corruption produces `INCIDENT_STOP`. Issue #52
itself executes no real preflight or host composition. Evidence publication,
filesystem durability, migration, cutover, resume, rollback, and incident
recovery remain separately approved later work.

The `Real Host Preflight layer` in `backend.real_host_preflight` is the Issue
#53 read-only composition boundary. Portable immutable values bind opened-handle
volume identity, 128-bit file ID, object type, parent identity,
normalized-name fingerprint, reparse metadata, completeness, and opaque
content-free observations. The direct Windows reader is package-private and
exists only behind a root-and-marker identity-bound, atomically single-use
test-sandbox permit. It rejects paths outside the test-owned temporary root,
opens every controlled component without following reparse points, requires
controlled files to have exactly one NTFS link, and reopens and validates the
exact root and marker for every observer operation while holding both handle
chains through the target observation. It fails closed on aliases, missing or
replaced markers, unexpected volume/filesystem state, unreadable objects,
replacement, or identity drift. Scope and observer bindings live in a
module-owned weak registry and cannot be reassigned through caller object
state.

`CurrentTopologyPreflight` requires two complete identical observations.
`PreMutationGate` binds one fresh nonce, operation, prior observation, short
validity, and single use while repeating exact source, target-parent,
target-absence, reparse, Git, ACL, and volume checks.
`RealHostBaselineCollector` keeps source-root, parent, finance, volume,
operator-SID, and ACL observations separate before projecting the existing
content-free `HostBaseline`. Callback evidence is accepted only after exact
factory reconstruction. The four topology roles and the three baseline object
roles must match the normalized-name projections stored in an independent
canonical Profile snapshot created before any host callback. Nominal receipts
have package-private producers, enforce an exact class-to-observation-kind
binding, and atomically claim their module-owned state; a public
`ReceiptEnvelopeV1` alone is not a receipt capability. Gate bindings and
consumed state are likewise module-owned and cannot be reset by caller
attribute mutation.

Three exact bridges are the only prior-layer crossings:
`audit_bridge -> backend.container_audit`,
`baseline_bridge -> backend.migration_evidence.HostBaseline`, and
`contracts_bridge -> backend.cutover_contracts`. The audit bridge supplies
exactly seven caller-bound callbacks to the unchanged nine-zone policy.
`FinalAuditCompositionReadyReceiptV1` proves only that the composition exists;
it does not execute or claim a pre-cutover final-layout pass. Prepare and
readiness revalidate every bound callback and require each composed adapter to
remain the identical reader captured by the binding. Prepare stores a detached
canonical audit-policy snapshot. Each audit run captures that policy, bindings,
seven reader references, and both fingerprints once; it validates and consumes
that same local capture while rebuilding fresh adapters before invoking any
callback. Readiness uses the same capture rule and a canonical Profile snapshot.
Caller or callback mutation cannot relax the policy or retarget the adapters
supplied to an in-progress audit.

No normal runtime, script, frontend, wrapper, cleanup, leakage scanner, or
workflow consumes this layer. The zero-argument operator entry remains
`BLOCKED_NO_APPROVED_COMMAND` and rejects test authorization. The layer has no
service-control, ACL-apply, rename, worktree-mutation, Runtime-build,
database-copy, artifact, Config, provider, mailbox, vault, private-data, or
arbitrary command capability. Windows integration runs only in test-owned
temporary sandboxes; Linux tests cover portable contracts only. Issues #55
through #59 remain separate; Issues #38/#39 and parent Spec #50 are unchanged.

The `Reviewed Migration Evidence Publication layer` in
`backend.migration_evidence_publication` is the Issue #54 profile-bound
composition. Review consumes one opaque selection bound to the exact
`CutoverProfileV1` dirty-source, local-ref, worktree, package-target, Git, and
`RealHostBaseline` selections. Only its exact bridges may cross into Issue #35
prepare/create, Issue #53 HostBaseline collection, and Issue #51
Profile/authorization validation. The complete `MigrationEvidenceReview`
remains in module-owned memory rather than persisted authority. The
`synthetic_scope.py` test binder owns the package's sole parent-anchor hard-link
capability: it links the fixed sandbox marker into the target parent and
requires both names to retain one regular-file identity, preventing POSIX inode
reuse from masking same-path parent replacement.

Create requires the exact `EvidencePublicationAuthorizationV1`, matching review
receipt, and exact confirmed review fingerprint. It repeats complete discovery,
including fresh HostBaseline collection, and rejects Profile, selection,
dirty-source, ref, worktree, Git, host, target, review, receipt, or
authorization drift before the create-only no-clobber commit. The creator may
use shared pure archive validation but cannot import or call the independent
verifier capability.

The `Migration Evidence Verifier layer` in
`backend.migration_evidence_verifier` is a separate read-only process boundary.
Its one core bridge imports only `verify_migration_evidence_payload`. The fixed
worker reads the published package once through a bounded descriptor, passes
those exact bytes to that verifier, requires an identical target reread, and
independently recomputes package/manifest hashes and bounded counts. The verifier package
cannot import publication or create-only modules and owns no package-target
write, create, replace, rename, link, unlink, remove, or delete capability.

The three closed review, created, and verified receipts bind one operation,
Profile, governing master, review/selection/Git/host fingerprints, package and
manifest hashes, package identity, and applicable counts. Only an exact match
may produce `MigrationEvidenceReceiptSetV1`, which is later-gate evidence rather
than authorization. All real entries remain locked before Issue #39 and reject
missing, wrong-phase, and test authorization. Tests may create and verify only
inside test-owned temporary synthetic sandboxes; public results, `repr`, stdout,
stderr, and logs remain content-free. No real package, host preflight, service,
repository/worktree move, ACL apply, Runtime build, database copy, provider,
mailbox, vault, private store, or private data is accessed. The package is
evidence, not backup, Runtime artifact, private-data container, or authority to
migrate.

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
Managed launcher -> backend.email_agent.managed_runtime -> backend.project_layout/config
reviewed private location policies -> backend.project_layout protected path value
Issue #53 exact read-only composition -> backend.container_audit injected values
manual offline operator -> backend.migration_evidence review/create/verify
backend.reparenting_rehearsal -> exact synthetic audit/evidence/layout bridges
tests only -> backend.runtime_activation_rehearsal exact injected adapters
tests plus exact #52/#53/#54/#55/#56/#57/#58 consumers -> backend.cutover_contracts pure value seams
tests -> backend.real_host_preflight test-owned Windows sandbox and portable seams
backend.real_host_preflight -> exact audit/baseline/contracts bridges
backend.migration_evidence_publication -> exact review/create/HostBaseline/contracts bridges
backend.migration_evidence_publication verification composition -> backend.migration_evidence_verifier process
backend.migration_evidence_verifier bridge -> backend.migration_evidence exact-payload verify only
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
normal runtime/cleanup/leakage/browser/workflow -> backend.container_audit
backend.container_audit -> filesystem/Git/SQLite/ACL/volume/host/private-content capability
normal runtime/browser/scripts/workflows -> backend.migration_evidence
normal runtime/browser/scripts/workflows/cleanup/leakage -> backend.reparenting_rehearsal
backend.reparenting_rehearsal public seam -> Path/repository/target/host capability
backend.migration_evidence -> mailbox/provider/SQLite/vault/private-store/lifecycle capability
normal runtime/browser/scripts/wrappers/workflows/cleanup/leakage -> backend.runtime_activation_rehearsal
backend.runtime_activation_rehearsal -> filesystem/SQLite/process/network/provider/mailbox/vault/private-store/credential/audit/evidence capability
all backend packages except exact reviewed #52/#53/#54/#55/#56/#57/#58 consumers, plus scripts/frontend -> backend.cutover_contracts
backend.cutover_contracts -> filesystem/SQLite/process/network/Git/ACL/provider/mailbox/vault/private-store/authority issuer
normal runtime/browser/scripts/wrappers/workflows/cleanup/leakage -> backend.real_host_preflight
backend.real_host_preflight -> service-control/ACL-apply/rename/Git-worktree mutation/Runtime-build/SQLite-copy/artifact/Config/provider/mailbox/vault/private-data capability
normal runtime/browser/scripts/wrappers/workflows/cleanup/leakage -> backend.migration_evidence_publication or backend.migration_evidence_verifier
backend.migration_evidence_publication creator -> backend.migration_evidence_verifier or independent verify capability
backend.migration_evidence_verifier -> backend.migration_evidence_publication or package publication/mutation capability
```

`tests/test_cutover_contract_architecture.py` enforces the Cutover Contract
layer's recursively exact package files and public surface, exact pure
standard-library imports, sibling-only relative imports, forbidden
host/ambient-authority loads and calls, package-wide absence of authorization
minting or clocks, the exact #52/#53 bridge consumers with every other
static/dynamic consumer rejected, and the zero-argument blocked operator entry.
Any further consumer or executable composition requires a separately approved
Issue and a deliberate update to these exact guards.

`backend/project_layout/` may import only its own modules plus the reviewed
standard-library path/value modules. Placement validates identity twice and fails
closed on missing/unreadable evidence, reparse components, alias drift, wrong
names, wrong parents, or identity change. Managed placement is exactly
`email_ai_assistant\main`. Standalone placement requires a separate explicit
synthetic or temporary state root and never infers a Project Container.
`OperationalLayout` accepts only a validated `RepositoryPlacement`. The
flat-layout transition adapter cannot add a third placement mode.
`ProtectedLocationPolicy` fails closed for partial Managed placement and checks
both original and resolved candidate views. Exact AST guards allow the
project-layout import only in the reviewed Managed runtime and standalone
verification adapters, private-knowledge storage/snapshot, private-evaluation
repository-path, and mailbox vault/sales-policy modules. Only the narrower
reviewed private-location set may consume `ProtectedLocationPolicy`. Public
request payloads remove `protected_roots` and
`project_container`, and no environment, config, frontend, ordinary runtime, or
CLI option may provide them. Focused domain-policy tests pass a validated
Standalone placement directly and prove that its separate state root cannot be
reclassified as external storage; Standalone Verification Mode still disables
all such private capabilities.

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
`scripts/run_local_debug.py`. The ordinary flat configured mode loads
configuration, configures logging, attempts one fail-closed DPAPI/key/snapshot
load, and injects the resulting immutable tuple into the server. Managed and
Standalone modes inject `()` and never invoke this bridge. There is
`no reload, polling, hot update, or status endpoint`.
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
runtime_activation_rehearsal 必须保持 exact-file、internal-import、pathless、no-host-consumer，并且不得获得 filesystem、SQLite、process、network、signing、audit、evidence 或 cleanup capability。
docs/ 下 Markdown 文件必须包含 YAML front matter。
项目中不得提交 .env、数据库文件、密钥文件或真实 token 文件。
```

本地开发可能存在 `.env`、SQLite 数据库等已被 `.gitignore` 忽略的运行文件；自动化测试应允许这些已忽略文件存在，但禁止未被忽略的敏感文件进入项目。

## 5. 对应测试文件

可执行约束测试文件：

```text
tests/test_architecture_constraints.py
tests/test_runtime_activation_rehearsal_architecture.py
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
`private_knowledge_snapshot_path`, `protected_roots`, and `project_container`.
Legitimate current-email fields remain available to the injected or default
analyzer; only the trusted startup tuple is added internally to the default
analyzer through its keyword-only seam.

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

## Issue #55 fixed-role mutation architecture

`backend.cutover_host_mutation.__init__` may export only portable contracts and
must not import Windows adapters or the locked operator entry. No normal
runtime, script, frontend, root wrapper, or workflow may import this package.
The package may consume only the exact Issue #51 authorization/profile symbols,
the exact Issue #52 durable-permit seam, and Issue #53 path normalization
helpers.

Only `windows_acl_apply.py` may call `SetSecurityInfo`, and it may update only
the protected DACL of the journal-proven guarded new empty Container. Its
construction DACL is code-fixed, protected, non-inheritable, operator-only, and
contains no add-file, add-subdirectory, or delete-child right. Root, marker,
parent, and target handles stay held until the final DACL linearization point.
Parent, finance, and source-tree paths remain read-only; source reparse objects
are not traversed. Directory creation must use parent-handle-relative
`NtCreateFile` plus `FILE_CREATE`. Native rename must be handle-relative,
no-replace, same-volume, and same-file-ID verified. Test-only native execution
must remain inside a caller-owned temporary NTFS sandbox; the real constructor
stays locked and has no adapter imports.

## Issue #56 reversible repository transaction architecture

`backend.cutover_repository_transaction` is an internal synthetic-Windows
composition layer. Its executable entry points accept only a package-private
scope previously bound to a caller-owned temporary sandbox, one closed failure
selector, and an epoch. They expose no path, ref, Git command, repository,
repair, deletion, cleanup, service, Runtime, SQLite, ACL, provider, mailbox,
vault, private-store, or private-data parameter.

The package may cross only the exact #51 Profile/test-authorization values,
#52 durable-effect permit, and #55 handle-relative no-replace primitives. One
fixed scope-bound Git runner performs read-only relationship discovery and the
single reviewed `worktree add`. It binds the executable's opened identity,
version, and bounded whole-file content digest; for every allowlisted operation
it denies executable write sharing and revalidates exact executable content,
identity, and sandbox identities before and after use. It owns a bounded
process tree, suppresses repository hooks, rejects unsafe local Git
configuration at scope bind/rebind, and
has no arbitrary command seam; clone, repository copy, fetch, reset, stash,
prune, remove, and repair are absent. The reviewed roster is exactly eight
embedded plus three external worktrees. Administrative entries are discovered
only through verified Git relationships; the complete exact namespace is
enumerated, bounded-fingerprinted as opaque objects, and never parsed or edited
by the transaction.

Every physical/admin/directory/Git effect has a create-only durable journal
INTENT before the effect, the actual #55 or Git observation in OBSERVED after
it, and COMMITTED only after an independent reread matches OBSERVED exactly.
Filesystem rereads hold the target against write/delete sharing through
COMMITTED, administrative rereads also bind opaque content, and Git rereads
repeat relationship/ref/commit/clean-state verification. On an explicit
reverse request, an
exact before-effect
observation records `ABORTED/NOT_APPLIED`; an exact after-effect observation
may append only the missing OBSERVED/COMMITTED facts and never replays the
effect. Forward moves every original physical and administrative
object into no-replace preservation before counterpart creation, relocates the
original Repository Root identity to `main`, and journals the actual new
Container object identity. That identity is the trusted ContainerAudit policy
selection and must equal the freshly observed Container object. Final
verification also requires the reviewed non-intentional local-ref and remote
configuration selections. It verifies the exact nine-zone Container plus 8+3
topology through the unchanged ContainerAudit
filesystem/Git/embedded-worktree validators plus exact external Git
verification. Reverse accepts every exact completed forward boundary and each
safely classified forward crash gap, first preserves any published new failed
state, then restores the original Repository Root, all original
administrative identities, and all eleven original physical identities.
An explicitly repeated reverse call derives an exact plan from the committed
forward stage, reconciles each safely classified reverse crash gap, validates
the complete journal-bound retained failed evidence before any resumed
mutation, validates the exact current checkpoint, and continues only the
remaining fixed mutations. The retained failed Container must keep the same
journaled Container identity. It never resumes in the background or from an
ambiguous state.

Normal runtime, scripts, frontend, workflows, and all other backend packages
must not consume this package. The real constructor accepts no test authority
and remains `BLOCKED_NO_APPROVED_COMMAND` even after exact
`CutoverExecutionAuthorizationV1` validation, before a separately approved
Issue #39 command.

## Issue #57 managed publication architecture

`backend.cutover_managed_activation` is an internal synthetic-Windows
publication layer. `ManagedActivationPhase` composes exactly four narrow
sealed adapters: Runtime publication, stopped-database copy, CRX publication,
and deterministic Config publication. It owns no service, repository,
worktree, Git, ACL, browser, mailbox, provider, credential, vault,
private-data, cleanup, repair, replace, or arbitrary path/command capability.

The package snapshots one caller-owned sandbox into immutable exact paths and
binds its Profile/test authorization, held root/marker/target-parent identities,
approved Python source, canonical complete dependency lock, exact offline
wheelhouse, stopped-service receipt, database source identity, reviewed CRX
identity, and closed Config review. Every target is created relative to the
held parent handle with `NtCreateFile(FILE_CREATE)` and remains held against
replacement; created files also deny concurrent writers during publication.
The test harness materializes the approved Python distribution inside the
caller-owned sandbox; scope review rejects an external source path. Its
canonical manifest binds the complete CPython distribution tree, exact entry
count, total bytes, executable hash, and tree fingerprint. Before executing
target code, publication reopens and holds every source directory and file against
write/delete sharing, rejects reparse points and alternate streams, recomputes
the exact bounded manifest, and keeps a recursive change guard pending through
the complete build and verification window. Source/wheel/lock capture checks
size and aggregate remaining capacity before reading from held handles rather
than allocating from raced paths.
Runtime installation consumes only bytes captured from write/delete-blocked
reviewed wheel handles, rejects `.pth`, `sitecustomize.py`, and
`usercustomize.py`, and verifies the full installed closure through the new
Runtime running with fixed `-X frozen_modules=on -I -B -S`. An empty create-only Runtime root receives
only exact approved CPython files streamed from held source handles; each
finished file is reopened read-only against write/delete sharing before any
target code executes. A held exact tree binds that source-distribution
baseline, rejects reparse points and alternate data streams, and creates every
wheel member and dependency lock relative to a held child-parent handle.
The complete approved `Lib/encodings` package is streamed from held source
handles into one bounded deterministic ZIP_STORED `managed-startup.zip`.
That create-only held archive is first in code-fixed `python312._pth` and
`python._pth`, followed by `Lib` and `DLLs`; neither sentinel contains
`import site`. CPython startup therefore resolves its regular `encodings`
package from an immutable namespace before any target directory can supply a
new child. Archive/sentinel collision fails before execution. Wheel
payload, member, expanded-size, compression-ratio,
and complete Runtime entry/file/byte/path/depth ceilings fail before unsafe
allocation or disk growth. EOCD/central-directory bounds run before
`ZipFile`, enumeration is capped before sorting, and extraction plus import/
tree hashing are bounded and streaming. Fixed frozen-module mode plus explicit
`_imp.is_frozen("codecs")` evidence closes the pre-script `codecs` dependency.
Self-verification imports only the CPython built-ins `sys`, `nt`, `_sha2`, and
`_imp`, then rejects every later import.
It hashes the exact target executable, SQLite binaries, startup archive, dependency lock, and
installed import leaves; SQLite hashes are compared with the held approved
source-tree entries, and bounded exact distribution metadata proves the
installed set without importing or executing installed package code. Runtime process stdout is consumed
incrementally and the child is terminated at the fixed byte ceiling rather
than buffered without a bound. A recursive Windows change guard remains
pending on the Runtime parent across sealing, self-verification, and receipt
construction; child and NTFS stream changes fail before success linearizes.
Exact scans verify the Runtime root default stream and reject every extra,
missing, or changed member. Database copy keeps its
write-blocking source handle through pre-copy and post-copy sidecar checks,
integrity, hash, and
identity checks, including one final sidecar/identity gate after target
verification. The CRX target handle remains held through source stability,
receipt construction, and a final exact reread; CRX cannot be built, signed,
installed, loaded, or unpacked.
Config cannot read environment files, process environment, registry,
credential stores, clipboard, or hidden input.

Every target is create-only and every partial or failed publication is
retained. Public results are one fingerprinted four-receipt set that
independently rebuilds the complete typed mappings and top-level operation/
Profile/master/authorization chain; it remains content-free. Exact package/
export guards and an
executable-import consumer guard keep normal runtime, scripts, frontend,
workflows, and all other backend packages from consuming this package. Each
real constructor rejects test authority and remains
`BLOCKED_NO_APPROVED_COMMAND` before Issue #39.

## Issue #58 provider-disabled lifecycle architecture

`backend.cutover_service_lifecycle` is an internal synthetic lifecycle
composition. It may import only pure Cutover contracts and Issue #57 managed
publication receipts. It has no OS, path, socket, subprocess, SQLite, service
discovery, Git, ACL, browser, mailbox, provider, credential, vault,
private-data, logging, environment, cleanup, repair, or arbitrary command
capability.

`ProviderDisabledServiceAdapters` contains exactly `NewServiceAdapter` and
`LegacyServiceAdapter`. The new role has fixed start/health/synthetic
analysis/row-observation/stop callbacks. The legacy role has only recovery
start/health/stop callbacks. The controller generates each UUIDv4 nonce and
code-owned request/Config itself; callers cannot supply a launcher, process,
command, retry policy, provider setting, environment mapping, port, or role.
Start and health bind the same exact process, Runtime, Config, Profile,
LocalData/database role, nonce, and port owner.

`ProviderDisabledLifecycleTransaction` is single-forward and single-recovery.
Known pre-mutation start rejection becomes `SAFE_ABORT` without containment.
Known post-mutation validation failure becomes `ROLLBACK_REQUIRED` and rejects
forward resume. Identity, journal, reparse, provider-boundary, or safety
ambiguity becomes `INCIDENT_STOP`; containment calls only the exact proven
new-service stop. Rollback uses one fixed staged adapter and one committed
journal-head binding. It seals `FailedContainerPublicationReceiptV1` before
main restoration, retains new external/Git evidence, restores exactly eleven
original worktrees, and classifies the retained Container
`FAILED_CONTAINER_PRESERVED_WITH_LEGACY_MAIN_EXTRACTED`.

Legacy recovery is attempted once with dedicated environment-independent
provider-disabled Config and a nonce distinct from activation. Any start or
health failure becomes
`INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED`, without alternate launcher,
changed Config, retry, provider enablement, or synthetic legacy database write.
Normal runtime, frontend, scripts, workflows, cleanup, and every other backend
package remain non-consumers. Real construction remains locked without exact
`CutoverExecutionAuthorizationV1` and `RecoveryAuthorizationV1` and remains
non-executable before Issue #39.

## 7. 修改规则

如果需要改变架构边界，必须同时修改：

```text
docs/constraints/architecture_constraints.md
docs/constraints/tooling_constraints.md
docs/templates/agent_task_brief_template.md
tests/test_architecture_constraints.py
```

如果只是业务功能变化，不得随意放宽架构约束。
