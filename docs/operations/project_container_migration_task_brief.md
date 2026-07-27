---
last_update: 2026-07-27
status: draft
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Project container and repository boundary migration task brief

> Planning record only. This document does not authorize moving, copying,
> deleting, renaming, committing, pushing, changing ACLs, creating accounts,
> enabling providers, creating automations, or accessing private data.

## 1. 任务名称

```text
project container and repository boundary migration
```

## 2. 任务类型

```text
security
```

## 3. 当前状态

```text
draft
```

The operator approved the design decisions recorded below. Full directory
migration remains blocked pending its separately approved cutover Issues and
maintenance evidence. Issue #30 separately authorizes only the
RepositoryPlacement/OperationalLayout compatibility seam from the stable
`origin/master@772a34d` checkpoint.

Issues #31 through #37 subsequently implemented the bounded Standalone,
Managed, protected-root, pure manual audit, offline migration-evidence, and
temporary synthetic reparenting/runtime-activation contracts in their own task
briefs. Issue #51 adds only a locked, pathless Cutover Profile, distinct
phase-specific authorization contracts, canonical content-free receipts, and a
default-blocked operator seam. Issue #52 adds only a pathless synthetic
crash-safe journal/state proof. Issue #53 adds only the default-locked Windows
read-only observation, current-topology/freshness, content-free HostBaseline,
and final-audit composition-readiness boundary. Windows behavior was exercised
only in caller-owned temporary sandboxes; no real Project Container audit,
operator preflight, evidence package, directory migration, ACL operation,
authorization issuance, or cutover has occurred.

## 4. 任务目标

将 `D:\Projects\email_ai_assistant` 定义为 email 项目集中容器，将完整 Git
仓库迁入 `D:\Projects\email_ai_assistant\main`，并把 runtime、普通运行数据、
日志、临时文件、构建产物和 linked worktrees 放入职责清晰的同级目录。

迁移完成后，`D:\Projects` 的一级目录只保留:

```text
D:\Projects\email_ai_assistant
D:\Projects\financial_statement_analysis
```

## 5. 非目标

- 本规划阶段不移动、复制、删除或重命名任何现有文件。
- 本规划阶段不修改业务代码、测试、Prompt、API、schema 或 provider 路由。
- 不读取、打印、复制或提交现有 `.env` 的内容。
- 不读取 raw vault、真实邮件、真实附件、restoration mapping 或私有评估明文。
- 不启用 OpenAI、DeepSeek、Ollama、Qwen、Gemma 或任何 mailbox operation。
- 不创建 Windows operator 账户，不修改 ACL，不启用 BitLocker。
- 不创建、恢复或重新绑定任何 Codex automation。
- 不提交、push、创建 PR、创建 GitHub Issue 或修改 remote state。
- 不把 raw vault、recovery material 或交互式秘密放入项目容器。
- 不修改 `D:\Projects\financial_statement_analysis`。
- 不夹带当前 Issue 工作树中的业务修改。

## 6. 背景与依据

### 当前盘点事实

- 当前 Git 仓库根是 `D:\Projects\email_ai_assistant`。
- 当前分支是 `master`，盘点时 HEAD 为
  `f07178160c188cccf49ec017e70ee97c2f714057`，比 `origin/master` ahead 1。
- 盘点时有 32 个 modified tracked paths 和 13 个 untracked source/test paths。
- 仓库有 481 个 tracked paths。
- 两个 linked worktree 均为 clean:
  - `prototype/current-email-ui-preview`
  - `agent/issue-23-action-console-shell`
- `D:\Projects` 当前有 5 个一级目录，无一级文件。
- `D:\Projects\email-ai-assistant` 不是 Git 仓库，只包含一个正在被进程占用的
  `-local-data\email_agent.sqlite3`。
- 已知范围内只发现这一个 `email_agent.sqlite3`。
- `D:\Projects\email_ai_assistant-runtime` 包含固定
  Python 3.12.13 / SQLite 3.50.4 runtime。
- 当前 `.venv` 使用 Python 3.12.13 / SQLite 3.50.4，并通过绝对路径绑定上述
  runtime。
- `email_ai_assistant-venv-py3126-backup-20260722` 使用 Python 3.12.6 /
  SQLite 3.45.3，不符合当前基线。
- 当前 `.env` 和 `frontend\browser_extension.pem` 存在且被 Git 忽略，内容未读取。
- 当前目录 ACL 继承了 `Authenticated Users` modify 和 `Users` read/execute。
- D 盘是 fixed NTFS volume。操作员确认 D 盘已经加密；实施时仍需记录只读系统
  状态证据。
- 当前没有连接 removable volume。raw vault 和 recovery 状态为
  `not provisioned`。
- 操作员已经删除旧 Codex `weekly-cleanup-agent`。
- 仓库仍包含 `.github/workflows/cleanup_agent.yml` 的 weekly scheduled GitHub
  Actions workflow definition；本规划未验证或修改其 remote enabled state。

### 相关文档

- `AGENTS.md`
- `CONTEXT.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_cleanup_task_brief.md`
- `docs/operations/project_structure.md`
- `docs/security/email_data_handling.md`
- `docs/security/private_knowledge_handling.md`

## 7. 涉及范围

### 规划阶段新增或修改

- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- 旧 cleanup automation 的项目文档入口

### 后续实施预计涉及

- 项目根路径和 container layout helpers
- `backend/email_agent/config.py`
- `scripts/manage_local_service.py`
- `scripts/run_local_debug.py`
- 本地 `.cmd` 启动入口
- repository leakage scan 与新增 content-free container audit
- private-storage path policies and their tests
- project-local `.codex` configuration
- `AGENTS.md`
- `README.md`
- operations, security, constraints and deployment documentation

该列表是预计范围，不授权本规划阶段修改上述实现文件。

## 8. 技术方案

### 8.1 最终目录模型

```text
D:\Projects\
├── email_ai_assistant\
│   ├── main\
│   ├── Runtimes\
│   ├── LocalData\
│   ├── RuntimeTemp\
│   ├── Logs\
│   ├── Artifacts\
│   ├── Worktrees\
│   ├── Config\
│   └── OperatorPrivate\
└── financial_statement_analysis\
```

职责:

- `main`: 唯一完整 Git common directory 和日常人工 Codex/IDE 开发工作区。
- `Runtimes`: 可重建的 Python、SQLite runtime、venv 和依赖。
- `LocalData`: 普通分析 SQLite，不是 raw vault。
- `RuntimeTemp`: 请求级附件临时文件，只用于现有点击分析边界。
- `Logs`: 内容受限的日志和 PID。
- `Artifacts`: CRX、构建包、allowlisted migration rollback package 和已审查
  历史产物。
- `Worktrees`: 自动化 worktree zone；其中的 linked checkouts 是版本化工作树，
  Git common directory 仍属于 `main\.git`。
- `Config`: 只保存 non-secret settings。
- `OperatorPrivate`: 后续 operator-only confidential zone。

`OperatorPrivate` 默认禁用。本次唯一计划例外是未来在独立 ACL 和 operator
账户就绪后，用 `OperatorPrivate\LegacyCredentials` 隔离现有 `.env` 和 extension
signing PEM。该目录不得成为 normal runtime、Codex 或 provider input。

### 8.2 三层安全边界

1. `main` 是 Git publication boundary、唯一 Git common directory 和日常人工
   development boundary。
2. parent container 是 local operating boundary，其中明确分为 non-versioned
   Local Operational Zone、versioned Automation Worktree Zone 和独立控制的
   Operator Private Zone。
3. raw vault and recovery 是 external isolated boundary。

目录层级本身不构成机密性保证。ACL、operator identity、at-rest encryption、
indexing/sync exclusion、reparse rejection 和 fail-closed path validation 必须
同时成立。

Raw vault 将来只能位于独立 removable NTFS BitLocker To Go volume。Recovery
material 必须位于不同的离线 volume。当前没有这些介质，因此相关能力保持
`not provisioned` 和 disabled。

### 8.3 Git repository migration

- 不重新 clone 代替当前仓库。
- 在实施前创建 Git bundle、allowlisted dirty-source snapshot、
  status/worktree inventory 和 SHA-256 manifest。
- Dirty-source snapshot 必须完整覆盖 tracked files 和经逐项审查、确认保留的
  untracked source/test/docs，但不得笼统复制 ignored 或 repository-adjacent state。
- `.env`、PEM、SQLite、logs、PID、`.venv`、IDE state、private data 和未经审查的
  build outputs 不得进入 ordinary `Artifacts` rollback package；这些来源在原位
  保留，或仅按另行批准的受保护备份流程处理。
- Git bundle 只保护 Git objects and refs，不能替代 allowlisted dirty-source
  snapshot。
- 在同一 volume 内把现有 `.git`、tracked paths 和确认保留的 untracked source/test
  paths 重新归属到空的 `main`。
- `.env`、`.venv`、SQLite、logs、PID、IDE state、PEM 和 build outputs 不进入
  `main`。
- 迁移后 branch、HEAD、remote、ahead/behind、tracked/untracked state 和逐文件
  hash 必须与迁移前一致。

### 8.4 Linked worktrees

两个 worktree 不按普通目录复制。保留原 branch and commit identity，在
`Worktrees` 中重新创建，或使用经过验证的 `git worktree repair`。每个 worktree
必须在迁移后独立通过 `git status`、branch 和 HEAD 校验。

### 8.5 Runtime

目标:

```text
Runtimes\
├── python-3.12.13-sqlite-3.50.4\
└── venv\
```

- create-only 复制并验证 fixed runtime。
- 不直接移动现有 Windows venv。
- 使用新 runtime 和锁定 requirements 重建 `Runtimes\venv`。
- 旧 `.venv` 和 Python 3.12.6 backup 在 full verification 前保留。
- 清理旧环境必须获得单独删除批准并优先使用 Recycle Bin。

### 8.6 LocalData

计划中的唯一 active normal analysis database:

```text
D:\Projects\email_ai_assistant\LocalData\email_agent.sqlite3
```

迁移前正常停止服务，并对 source/destination 执行 content-free size、SHA-256、
SQLite integrity、sidecar 和 aggregate-count checks。Destination create-only，
禁止覆盖。旧数据库在新服务验证和单独清理批准前保留。

该决策只改变 public/debug analysis SQLite 的本地位置，不允许 raw mailbox data、
vault content、restoration mapping 或 private evaluation plaintext 进入 SQLite。

### 8.7 Configuration and credentials

- `main\.env.example` 保留 versioned placeholders。
- `Config\settings.env` 只允许 non-secret allowlisted keys。
- API key and token 由独立 operator account 的 Windows Credential Manager 管理。
- mailbox app password 和 evaluation key 继续 hidden interactive input only。
- 现有 `.env` 不自动读取、转换或复制。
- 远程 providers 在迁移和安全重构期间保持 disabled。

### 8.8 Managed container and standalone verification modes

- Managed container mode 通过受控 launcher 读取 container configuration，并把
  state 路由到固定 sibling directories。
- Standalone/CI mode 保持仓库可 clone 和可测试，只允许 synthetic data、temporary
  directories 和 provider-disabled behavior。
- Standalone mode 不得接入 real SQLite、mailbox、OperatorPrivate 或 external vault。

### 8.9 Runtime outputs and artifacts

- `browser_extension.crx` 进入 `Artifacts\BrowserExtension`。
- `outputs\sdd` 在 leakage review 通过后进入
  `Artifacts\HistoricalReviews`。
- 旧 log、PID、cleanup report、empty `scripts\outputs` 和 `.idea` 不迁移。
- 任何删除只在完成验证后另行批准。

### 8.10 Container audit

新增 read-only content-free audit，检查:

- exact top-level allowlist
- unique Git repository root
- ACL, volume identity and reparse state
- non-secret Config key allowlist
- SQLite filename, size, sidecar, integrity and aggregate counts
- Python and SQLite runtime versions
- bounded log and artifact metadata
- OperatorPrivate directory identity and ACL only
- raw vault `not provisioned` state

审计不得读取 OperatorPrivate、raw vault、private dataset、real mail 或 secret values，
不得自动删除、移动或修复。

该审计是 migration preflight、post-cutover verification 和后续 maintenance 的
强制人工 gate。它不得加入 automation、scheduler 或 background task。任何 allowlist、
identity、ACL、volume、reparse、runtime、database metadata 或 unreadable-state
漂移都必须以固定 code fail closed。公开输出只允许 fixed overall status code 和
aggregate counts，不得输出 sensitive path、account、record、secret、matched value
或 native exception detail。

Issue #34 implements only the pure injected validation core described above.
It has no CLI, default/real host adapter, normal-runtime consumer, maintenance
integration, scheduler, or composition root. Its automated tests use synthetic
content-free evidence and do not execute a real preflight/post-cutover audit.
The future migration gate must compose reviewed real adapters under a later
separately approved Issue without widening this core contract.

### 8.11 Codex and automation

- Daily human Codex/IDE workspace 只能是 `main`；经单独批准的 automation 只可
  打开分配给它的 linked worktree。
- Project-local `.codex` paths 必须更新到 `main`，然后重新打开或重启 Codex。
- No parent-level `AGENTS.md` is created in the first-stage layout. The Project
  Container top level contains exactly the nine approved directories, and normal
  Codex/IDE sessions must open `main` rather than the parent.
- 旧 Codex `weekly-cleanup-agent` 已由操作员删除，不得恢复或重新绑定。
- `.github/workflows/cleanup_agent.yml` 仍定义 scheduled GitHub cleanup scan。
  删除 Codex automation 不等于停用该 workflow；是否停用或移除必须由单独批准的
  Issue 决定，本规划不修改它。
- 未来 weekly code-review automation 是独立设计，只能在 `Worktrees` 的
  `codex/weekly-review-*` branch 修改已提交代码。
- 未来 automation 不得修改 dirty main worktree，不得自动 push、create PR、merge
  或删除 branch。它只能访问分配的 linked worktree，不得打开或遍历 parent
  Project Container、其他 worktrees、Local Operational Zone 或 Operator Private
  Zone，也不得访问 mailbox、provider 或 private data。
- 任何自动化提出的修改都必须运行 task-defined tests，并留在隔离 branch 等待
  操作员人工审核和集成。
- 本 task brief 是这些 future boundaries 的 active planning source；deprecated
  cleanup automation 文档只保留历史事实，不得作为新实现依据。

### 8.12 Implementation sequence

1. 当前代码修改先形成 independently reviewed stable Git checkpoint。
2. 为目录迁移建立独立 approved Issue and task brief。
3. 先实现并测试 container/repository path abstraction、dual modes 和 audit guards。
4. 先人工审核 exact external target、content-free inclusion/exclusion manifest、
   reviewed local refs and worktree selection；另行确认后才可 create and
   independently verify the real no-clobber migration evidence package。
5. 记录 baseline status, refs, worktrees, file hashes, ACL and volume evidence，
   并通过 mandatory manual preflight container audit。
6. 正常停止 local service。
7. 创建其余 allowlisted rollback artifacts and empty target directories。
8. 收紧 container ACL，但不影响 `D:\Projects` 或 finance project。
9. 将完整 Git repository 重新归属到 `main`。
10. 重建 runtime and worktrees。
11. 迁移 LocalData and non-sensitive artifacts。
12. 在 operator identity ready 后隔离 legacy credentials。
13. 更新 project config, docs and local bindings。
14. 运行 full verification、disabled-provider health check 和 mandatory manual
    post-cutover container audit。
15. 保留所有旧来源，直到单独 cleanup approval；此时 `D:\Projects` 暂时仍可超过
    两个一级目录。
16. 仅在另一个 cleanup Issue 获得明确删除批准后，把已验证旧来源送入 Recycle Bin，
    再验证 `D:\Projects` 只剩两个 approved project directories。

### 8.13 Issue #30 compatibility checkpoint

Issue #30 implements only:

- `RepositoryPlacement` validation for exact Managed and explicit Standalone
  placement, stable directory identity, and protected roots。
- `OperationalLayout` resolution for the seven absolute ordinary locations。
- A separate flat-layout transition adapter for current local-service paths。
- Synthetic/offline public-interface tests and fixed placement failures。

It performs no real migration, directory creation, service routing, private-path
guard expansion, container audit, ACL/volume operation, mailbox/provider/vault/
credential access, or Issue #31 through #40 work.

### 8.14 Issue #32 Managed local-service checkpoint

Issue #32 implements only:

- exact Managed placement and pre-existing zone validation before Config read or
  service start；
- provider-disabled `--managed-container` lifecycle/direct-launch routing；
- `LocalData` SQLite, `RuntimeTemp` attachment temp, `Logs` diagnostics/PID,
  Managed runtime, artifact, worktree, and exact non-secret Config resolution；
- bounded allowlisted Config read with no credential/provider/private-path
  sourcing；
- injection of resolved config into request handling while repository source,
  Git, project status, maintenance, and leakage scanning remain at `main`；
- synthetic loopback start/health/analysis persistence/stop tests。

It performs no real migration, runtime rebuild, database/artifact copy, worktree
relocation, container audit, preflight evidence capture, ACL change, mailbox or
provider call, private-store/credential read, or Issue #34 through #40 work.

### 8.15 Issue #35 migration-evidence checkpoint

Issue #35 implements only:

- live, read-only discovery of exact local `refs/heads/*`, branch-attached
  worktrees, dirty status, remote fingerprints and ahead/behind metadata；
- an independently verified Git bundle for reviewed local refs, including
  original branch commit sequences that no longer have GitHub feature refs；
- an exact-allowlist snapshot with separate tracked index/worktree layers,
  approved untracked source/tests/docs, and content-free deletion records；
- canonical SHA-256 binding of package identity, Git/worktree/host evidence,
  dirty selection and every payload file；
- mechanically excluded credentials, signing material, SQLite, logs, PID state,
  virtual environments, IDE state, private data, caches and unapproved outputs；
- create-only, external-target publication with reparse, race, partial-write and
  identity-drift failures closed；
- synthetic repository restore tests only。

It creates no real evidence package and does not choose a real target, reviewed
refs, worktrees or dirty-source allowlist for the operator. A real package
requires the exact target, content-free inclusion/exclusion manifest, reviewed
refs and worktree selection to be displayed first, followed by a separate
operator confirmation. It performs no service stop, repository move, ACL
change, mailbox/provider/vault/private-store/credential access, or Issue #36
through #40 work.

### 8.16 Issue #36 synthetic reparenting rehearsal checkpoint

Issue #36 implements only a self-contained temporary synthetic rehearsal:

- one public seam with exact content-free worktree choices and fixed failure
  boundary, but no path/repository/target/host input；
- a local synthetic repository with three branch refs, local-only remote,
  non-zero ahead count, dirty main and two clean linked worktrees；
- an exact synthetic Issue #35 evidence package created and independently
  verified before rename；
- complete legacy-source rename followed by checked no-clobber movement of the
  existing `.git`, tracked source and reviewed untracked source into `main`；
- metadata-only preservation of excluded credential/signing/runtime/output/
  IDE/cache/SQLite/log/private canaries in the sibling legacy source；
- injected per-worktree repair/recreate choices preserving branch, HEAD, common
  identity and clean active status without clone, prune, deletion or overwrite；
- post-state baseline equality, exact Managed relationship and a passed
  synthetic ContainerAudit；
- verified rollback at evidence, legacy, Container, main, worktree and audit
  publication boundaries；post-main failures move the whole Container to the
  one no-clobber sibling rollback path and repair the reviewed relocated
  worktrees；
- marker filesystem identity plus fixed sibling hard-link anchor binding,
  including pre-publication same-text/inode-reuse drift, reparse and
  non-local-remote rejection；
- no automatic public-operation teardown; caller-owned test cleanup occurs only
  after independent filesystem/Git/evidence assertions。

It creates no real evidence package or Container, accepts no real Repository
Root, and performs no real worktree/branch/directory/ACL/runtime/database
mutation. Real cutover composition and Issues #38 through #40 remain separate.

### 8.17 Issue #37 synthetic runtime and LocalData activation checkpoint

Issue #37 implements only a caller-owned temporary synthetic rehearsal:

- one pathless public seam accepting exactly five injected runtime, filesystem,
  database, lifecycle and probe adapters, with no default host adapter；
- exact Python 3.12.13, SQLite 3.50.4 and dependency-lock identity/digest
  evidence, plus a create-only fixed runtime and
  `Runtimes\venv\Scripts\python.exe` rebuilt without network or legacy reuse；
- lifecycle-manager stop output and an independent `pre_publication` proof
  before any source SQLite observation or publication；
- create-only LocalData publication with distinct object identity, source and
  destination SHA-256/size/count equality, integrity/schema validation, and no
  WAL/SHM/journal sidecar；
- one fresh activation nonce bound to the initial gate and echoed by start,
  health, analysis and the
  `post_activation` stopped proof；the final proof binds the same service,
  rejects stale replay and uses a fresh stop token；
- an exact source re-observation after publication and after the activated
  synthetic service stops；
- exact RuntimeTemp attachment, Logs log/PID, Config non-secret settings and
  Artifacts browser-extension roles derived from the actual synthetic topology；
- a pre-frozen reviewed browser-extension identity/hash, create-only
  publication, two independent destination observations, and no
  signing-material capability；
- both providers disabled, no provider key/private knowledge/client, literal
  `127.0.0.1` health, exactly one user-confirmed persisted `rule_fallback`
  analysis, and one-row destination count increase；
- fixed failure for runtime/database/artifact race, reparse, existing target,
  dependency, integrity and health faults without target overwrite or source
  cleanup；
- exact package/import/consumer guards and fixed aggregate-only public results。

The integration fixture owns an `issue37-synthetic-*` parent and performs
exclusive local writes only beneath it. Caller teardown occurs after independent
source, legacy, competitor, Managed-role, database and signing-canary assertions.
No real runtime, `.venv`, SQLite, extension artifact, migration evidence package,
Project Container, provider, mailbox, vault, private store or credential was
opened or activated. Issues #38 through #40 remain separate.

### 8.18 Issue #51 locked Cutover Profile, authorization, and receipt checkpoint

Issue #51 implements only the pure `backend.cutover_contracts` package:

- immutable, strict-canonical `CutoverProfileV1` binding the governing master,
  operator and every fixed role/evidence/review selection, the exact
  eleven-worktree roster with eight embedded and three external roles, pinned
  Runtime inputs, create-only SQLite and CRX, deterministic non-secret
  provider-disabled Config, fixed-role ACL, maintenance/no-cleanup rules and
  complete rollback roles；
- no profile field for a host path, drive, directory, SID, SDDL, Git name/ref,
  command, exception, database content or free-form message；
- distinct externally supplied `RealPreflightAuthorizationV1`,
  `EvidencePublicationAuthorizationV1`,
  `CutoverExecutionAuthorizationV1`, and `RecoveryAuthorizationV1` values with
  exact operation, phase, profile, master, operator, fingerprint and bounded
  validity checks；
- fixed authorization-validation statuses for missing, wrong type, not-yet
  valid, expired, wrong profile/master/operation/operator/phase and invalid
  context；
- no issuer or minting seam, secret, signer, clock or random source capable of
  creating real-host authorization, and exact-type rejection of
  `TestSandboxAuthorizationV1`, receipts, mappings and duck types；
- deterministic canonical `ReceiptEnvelopeV1` with twelve closed receipt
  families, exact status/type/detail/count schemas, complete operation/profile/
  master/authorization/producer/subject/input/observation/validity binding and
  verified SHA-256 identity；
- duplicate, unknown, non-canonical or content-bearing receipt input rejected
  without exposing raw paths, SID/SDDL, Git names, commands, exceptions,
  database content or free-form messages；
- one no-argument `default_operator_entry()` returning only
  `BLOCKED_NO_APPROVED_COMMAND`, one blocked count and zero executions；
- a pure standard-library value/JSON/hash layer with no host adapter,
  composition root, CLI, normal-runtime consumer, filesystem, process, SQLite,
  ACL, Git, network, browser, mailbox, provider, vault, private-store,
  environment, scheduler, logging or dynamic-import capability。

This checkpoint parses and validates contracts only. It does not execute real
preflight, evidence publication, migration, cutover, resume, rollback, incident
recovery or cleanup and does not access real Runtime, SQLite, ACL, repository,
worktree, mailbox, provider, vault or private data. Its only approved consumer is
the exact Issue #52 bridge.

### 8.19 Issue #52 crash-safe journal and recovery-classification checkpoint

Issue #52 implements only the pathless `backend.cutover_journal` synthetic
transaction proof:

- strict canonical create-only records with exact sequence, previous-record hash,
  record hash, fixed synthetic step/direction/event, governing
  master/operation/profile/authorization/owner bindings and opaque observations；
- one pre-mutation binding that revalidates the exact execute authorization and
  exact pre-bound rollback-phase `RecoveryAuthorizationV1` without issuing
  authority；
- fixed forward and reverse `INTENT -> EFFECT_OBSERVED -> COMMITTED` transitions,
  with reverse intent derived LIFO only from verified `COMMITTED/APPLIED` forward
  history；
- exact in-memory Windows/Linux pending-file, published-file and namespace
  barrier traces, stable reread, per-claim synthetic owner lease, complete-chain
  recovery ownership, medium-gated atomic single-use durable-intent permit,
  stable-current-head continuation and exact lost-ack retry；
- immutable restart inspection with no append, owner claim or effect, plus
  separately explicit resume/rollback seams that fresh-validate exact
  phase-specific authorization and observation；
- exact expected-post reconciliation without blind effect retry, and
  authoritative durable observed facts, fresh `RESUME_BOUND` renewal,
  direction-aware pending recovery, exact Profile/master/operator and synthetic
  effect-mapping checks, and pre-bound-authority rollback after execute
  authorization expiry；
- fixed content-free public status/phase/receipt-fingerprint/allowlisted-count
  output distinguishing `SAFE_ABORT`, `ROLLBACK_REQUIRED`, `INCIDENT_STOP`, and
  `CUTOVER_SUCCEEDED`；
- complete forward/reverse/durability crash matrices and exact architecture
  guards.

The package accepts no path, callback, host adapter, CLI, HTTP route, filesystem,
service, ACL, Git repository/worktree, Runtime, SQLite, artifact, Config,
provider, mailbox, vault, private store, credential or private data. The
Windows/Linux trace is contract evidence only, not real filesystem durability
evidence. No real preflight, migration, cutover, resume, rollback or recovery was
executed. Issue #52 did not authorize later work; Issue #54 is bounded
separately below, Issues #55 through #59 remain unstarted, and Issues #38/#39
and parent Spec #50 are unchanged.

### 8.20 Issue #53 content-free Windows real-host preflight checkpoint

Issue #53 implements the physically separate, default-locked
`backend.real_host_preflight` read-only composition:

- opened-handle Windows observations bind volume identity, 128-bit file ID,
  object type, parent identity, normalized-name fingerprint, attributes, and
  reparse metadata without relying on path strings alone；
- every controlled component is opened no-follow-reparse and alias, scope
  escape, unexpected volume/filesystem, unreadable/incomplete evidence,
  replacement, target appearance, normalized-name change, or identity drift
  fails closed with fixed content-free output；
- Windows native behavior is reachable only from exact
  `TestSandboxAuthorizationV1`-bound, caller-owned temporary sandboxes through
  a package-private root/marker identity-bound atomically single-use permit;
  controlled files require exactly one opened-handle link and the observer/
  scope are not package exports; Linux
  runs portable contracts and injected composition only and makes no NTFS,
  Windows file-ID, Windows ACL, or real-host evidence claim；
- `CurrentTopologyPreflight` accepts only two complete, identical observations
  of source, target parent, target absence, controlled reparse state, Git, ACL,
  and volume evidence; every value is factory-reconstructed and all four names
  must match their exact Profile role selections；
- `PreMutationGate` repeats those checks and binds an accepted topology, exact
  operation, fresh UUIDv4 nonce, short half-open validity, and one consumed
  attempt; each topology receipt is atomically single-claim and module-owned
  receipt/gate state cannot be minted or reset by a public envelope, caller
  attribute, copy, or serialization; stale, replayed, retargeted, or drifting
  state fails closed；
- `RealHostBaselineCollector` preserves distinct source-root, projects-parent,
  finance-project, volume, operator-SID, and role-specific ACL evidence, then
  projects only a deterministic aggregate into the existing `HostBaseline`；
- the exact `audit_bridge.py` composes the unchanged final nine-zone
  `ContainerAudit` through its existing seven read-only callbacks, while
  `FinalAuditCompositionReadyReceiptV1` proves only composition readiness and
  revalidates every binding/reader identity without invoking the current
  pre-cutover audit or claiming a final-layout pass；
- exact `contracts_bridge.py` and `baseline_bridge.py` consumers validate
  existing contracts and project the existing baseline without widening #51
  receipt/authorization schemas or #35 evidence-package operations；
- receipts, results, repr, stdout, stderr, and logs expose no raw path, SID,
  SDDL, account, Git name/ref, file ID, command, callback exception, native
  error text, or content；
- the operator entry remains zero-capability and fixed at
  `BLOCKED_NO_APPROVED_COMMAND`, one blocked count, and zero executions; it
  cannot accept test authorization or mint real authorization.

The package has no service-control, ACL-apply, rename, repository/worktree
mutation, Runtime-build, database-copy, artifact, Config, provider, mailbox,
vault, private-store/private-data, evidence-publication, migration, cutover,
resume, rollback, recovery, cleanup, or scheduler capability. No Issue #53 test
accessed the real Repository Root, finance project, service, ACL, worktree,
Runtime, production database, credential, mailbox, provider, vault, or private
data. Issue #53 did not authorize #54; the #54 checkpoint follows below.
Issues #55 through #59 remain separately authorized, and Issues #38/#39 and
parent Spec #50 remain unchanged.

### 8.21 Issue #54 reviewed Migration Evidence publication checkpoint

Issue #54 defines the profile-bound review, separately authorized create-only
publication, and separate-process read-only verification boundary:

- review consumes only exact `CutoverProfileV1` dirty-source, local-ref,
  worktree, package-target, Git, and `RealHostBaseline` selections, with no
  arbitrary replacement inputs;
- `MigrationEvidenceReviewReceiptV1` binds operation, Profile, governing
  master, review, selection, Git, host, and allowlisted counts through
  content-free fingerprints; the complete `MigrationEvidenceReview` remains
  in memory and is not persisted as alternate authority;
- create runs in the physically separate
  `backend.migration_evidence_publication` composition and requires the exact
  `EvidencePublicationAuthorizationV1`, review receipt, and confirmed review
  fingerprint;
- create repeats complete discovery and fresh HostBaseline collection before
  the existing no-clobber commit, rejecting Profile, selection, dirty-source,
  ref, worktree, Git, host, target, review, receipt, or authorization drift;
- `MigrationEvidenceCreatedReceiptV1` binds review, package, manifest, package
  identity, authorization, and aggregate-count fingerprints;
- verification runs through the separate read-only
  `backend.migration_evidence_verifier` process, reads the published package
  once through a bounded descriptor, invokes the independent verifier on those
  exact bytes, requires an identical target reread, and independently
  recomputes package/manifest hashes and counts;
- the creator may use shared pure archive-format validation but cannot import
  or call the independent verifier; the verifier cannot import publication or
  create-only capability and cannot modify a package;
- `MigrationEvidenceReviewReceiptV1`,
  `MigrationEvidenceCreatedReceiptV1`, and
  `MigrationEvidenceVerifiedReceiptV1` must agree exactly before
  `MigrationEvidenceReceiptSetV1` can provide later-gate evidence; no receipt or
  Set is authorization;
- before Issue #39, real review/publication/verification entries remain locked
  and reject missing, wrong-phase, malformed, and
  `TestSandboxAuthorizationV1` inputs;
- all executable package creation and verification stays in test-owned
  temporary synthetic sandboxes, and public receipts/results/repr/stdout/
  stderr/logs expose no path, ref, object ID, worktree name, command, content,
  native error, or exception text.

Issue #54 authorizes no real package, host preflight, service stop,
repository/worktree move, ACL apply, Runtime build, database copy, provider
call, mailbox access, vault/private-store access, or private-data read. A
Migration Evidence Package is evidence, not backup, Runtime artifact,
private-data container, or authorization to migrate. Issues #55 through #59
remain separate; Issues #38/#39 and parent Spec #50 remain unchanged.

## 9. 数据结构或接口变化

### 数据库变化

无 schema change。只规划 normal analysis SQLite 的 path relocation。

### API 变化

新增内部 Python `RepositoryPlacement`/`OperationalLayout` compatibility
interfaces、provider-disabled Managed launcher adapter、Issue #35 的
`prepare_migration_evidence_review`、`create_migration_evidence_package` 和
`verify_migration_evidence_package` manual seams，以及 Issue #36 的
`rehearse_repository_reparenting` 和 Issue #37 的
`rehearse_managed_runtime_activation(*, adapters=...)` synthetic-only seams。
Issue #51 additionally exposes internal-only `CutoverProfileV1`, four distinct
real-authorization value parsers, `validate_real_host_authorization(...)`,
canonical `ReceiptEnvelopeV1`, and the default-blocked
`default_operator_entry()`。Issue #53 additionally exposes internal-only
portable observation values, Windows test-sandbox observation,
`CurrentTopologyPreflight`, `PreMutationGate`, `RealHostBaselineCollector`, and
final-audit composition readiness through exact narrow bridges; its operator
entry remains blocked and no HTTP/CLI command is added；
Issue #54 additionally exposes internal profile-bound review, separately
authorized create-only publication, separate-process read-only verification,
and closed content-free review/created/verified receipt consistency seams. Its
real entries remain locked before Issue #39 and no HTTP/CLI command is added；
无 HTTP API 变化。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 本规划不读取真实邮箱数据。
- [x] 本规划不自动发送、删除或归档邮件。
- [x] 本规划不在前端保存或暴露 API key。
- [x] `.env`、PEM、SQLite 和 private stores 只做 content-free inventory。
- [x] Raw vault and recovery remain external and not provisioned。
- [x] Providers remain disabled。
- [x] 当前 Issue 的用户修改保持原样。
- [x] 删除、ACL、account、automation 和 remote actions 均未授权。

## 11. Prompt Injection 防护

本任务不处理邮件正文、附件内容、AI prompt 或 provider response。任何文件名、
日志文本或迁移输入仍按不可信数据处理，不执行其中命令。

## 12. 验收标准

规划文档验收:

1. Glossary、ADR 和 task brief 对 Project Container 与 Repository Root 使用一致术语。
2. 明确 `main` 是唯一 Git common directory 和日常人工 Codex/IDE root，并记录
   受限 linked worktree exception。
3. 明确 first-stage directory names and responsibilities。
4. 明确 raw vault/recovery not provisioned and external。
5. 明确 `.env` and credentials 不进入 ordinary config。
6. 明确 dirty worktree、worktrees and Git history 的保护方式。
7. 明确 migration verification, rollback and separate deletion approval。
8. 区分已删除的 Codex cleanup automation 与仍存在的 GitHub scheduled workflow，
   并明确 future automation isolation rules。
9. 本规划阶段没有业务代码、文件迁移、删除、ACL 或 automation change。
10. Issue #35 synthetic restore proves reviewed Git objects/refs, separate dirty
    index/worktree layers and linked-worktree identity can be independently
    recovered without generating a real package。
11. Evidence publication rejects existing target, reparse, race, partial write
    and identity drift, and semantic verification rejects manifest/evidence/
    snapshot tampering。
12. Issue #51 profile, authorization and receipt contracts remain immutable,
    closed-schema, pathless, content-free and canonical, with no real-host
    adapter or authorization issuer。
13. Issue #51 default operator entry remains
    `BLOCKED_NO_APPROVED_COMMAND`; receipts and synthetic authorization cannot
    become execution authority。
14. Issue #53 Windows behavior is limited to caller-owned temporary sandboxes
    bound to exact test authorization; Linux validates portable contracts only
    and makes no NTFS/Windows ACL/real-host evidence claim。
15. Current topology requires two complete identical observations, while the
    pre-mutation gate is fresh UUIDv4-nonce-bound, exact-operation-bound,
    short-lived and single-use with repeated source/parent/absence/reparse/Git/
    ACL/volume checks。
16. RealHostBaseline keeps source, parent, finance, volume, operator-SID and ACL
    evidence separate and content-free before canonical projection。
17. Final-audit readiness composes the unchanged final nine-zone policy and
    exact seven callbacks without invoking the audit or claiming a final pass。
18. The #53 operator remains fixed blocked, no real authorization is issued,
    public output remains content-free, and no mutation/runtime/data/provider/
    mailbox/vault/private-data capability is introduced。
19. Issue #54 review accepts only exact Profile-bound evidence selections and
    does not persist the complete review as authority。
20. Issue #54 create requires exact publication authorization and confirmed
    review fingerprint, reruns complete discovery and fresh HostBaseline
    collection, and remains create-only/no-clobber。
21. Issue #54 verification is a separate read-only process; creator and verifier
    capabilities remain isolated and package/manifest hashes are recomputed。
22. Review, created, and verified receipts agree on the same operation, Profile,
    master, review bindings, hashes, identity, and counts before a content-free
    `MigrationEvidenceReceiptSetV1` can exist。
23. Real #54 entries remain locked before Issue #39; tests stay temporary and
    synthetic, public output stays content-free, and the evidence package is
    neither backup/runtime/private data nor migration authorization。

后续 migration cutover acceptance 至少包括:

- [ ] Git branch、HEAD、refs、remote、ahead/behind 和 dirty paths 与 baseline 一致。
- [ ] 逐文件 hash and count verification passes。
- [ ] 所有 linked worktrees pass independent status checks。
- [ ] Python 3.12.13 and SQLite 3.50.4 are verified。
- [ ] Full unittest, compile, static, architecture, documentation and leakage checks pass。
- [ ] Container audit passes without reading private content。
- [ ] Providers remain disabled and local health check passes。

后续 cleanup closeout acceptance 另行包括:

- [ ] 已取得针对每个旧来源的单独删除批准并使用 recoverable cleanup。
- [ ] `D:\Projects` 最终只有两个 approved project directories。

## 13. 测试计划

规划文档阶段:

- documentation front matter and metadata validation
- documentation contract tests
- `git diff --check`
- scope review against current dirty worktree

后续 implementation 阶段:

- focused path, config, service, worktree and audit tests
- focused synthetic migration-evidence review, restore, exclusion, no-clobber
  and semantic-verification tests
- focused portable, topology, pre-mutation gate, HostBaseline, composition,
  architecture and leakage tests for Issue #53
- focused profile-bound review, separately authorized create-only publication,
  receipt consistency, package observation, separate verifier process,
  architecture, locked-entry and leakage tests for Issue #54
- Windows native observation tests only beneath test-owned temporary sandboxes;
  Linux portable-contract tests do not claim NTFS or Windows ACL evidence
- affected ContainerAudit, migration-evidence and cutover-contract regression
  suites, including exact bridge-consumer guards and unchanged-policy review
- `python -m unittest discover -s tests`
- `python -m compileall backend scripts tests`
- architecture, linter and mechanical guards
- repository leakage scan for `main`
- content-free container audit
- maintenance scan
- disabled-provider service health check

所有测试必须使用 synthetic fixtures，不访问 mailbox、provider、vault、DPAPI、
BitLocker private content 或 ignored SQLite text。

## 14. 回滚方案

- 在切换前保存 allowlisted dirty-source snapshot、Git bundle、hash manifest、
  ACL export、status and worktree inventory。
- 普通 rollback package 明确排除 `.env`、PEM、SQLite、logs、PID、`.venv`、
  IDE state、private data 和未经审查的 build outputs；这些来源保持原位，除非另有
  受保护备份批准。
- 新位置通过所有 checks 前不删除或覆盖旧来源。
- 回滚时先停止新 service，恢复原 directory identity，修复 linked worktree paths，
  恢复 ACL and project bindings，再重新验证 original service。
- Git bundle 只作为 object/ref recovery，不替代 allowlisted dirty-source snapshot。
- Issue #35 已实现 create-only package mechanism，但本次没有生成真实 rollback
  artifact；未获审核与单独确认前，不能把 synthetic verification 视为 real baseline。
- 任何 material deletion 使用单独批准和 recoverable Recycle Bin。

## 15. 需要人工确认的问题

已确认:

- [x] Container root is `D:\Projects\email_ai_assistant`。
- [x] Full Git repository target is `main`。
- [x] First-stage directory names and responsibilities。
- [x] Three-layer boundary。
- [x] Raw vault/recovery remain not provisioned。
- [x] Worktrees are rebuilt under `Worktrees`。
- [x] Config contains no real credentials。
- [x] LocalData owns the only active normal analysis SQLite。
- [x] Venv is rebuilt rather than moved。
- [x] Managed container and standalone verification modes。
- [x] Narrow legacy-credential isolation exception。
- [x] Separate future Windows operator account and runbook。
- [x] Providers disabled during migration。
- [x] `main` is the daily human development workspace；approved automation
  worktrees are the narrow exception。
- [x] Container ACL hardening is a prerequisite。
- [x] Operator confirmed D drive encryption。
- [x] Artifact retention policy。
- [x] Manual content-free container audit。
- [x] Old Codex cleanup automation retired；the separate GitHub scheduled
  workflow remains an explicit unresolved implementation item。
- [x] Future weekly code-review automation uses isolated branches。
- [x] Migration waits for a stable Git checkpoint。

仍需在后续 implementation Issue 明确:

- exact external migration-evidence target
- exact content-free inclusion/exclusion selection
- exact reviewed local refs and root/linked-worktree selection
- matching review-fingerprint confirmation after the above values are displayed
- exact migration date and maintenance window
- exact operator account name
- exact ACL command transcript and recovery location
- exact retention period for migration rollback artifacts
- whether `git worktree repair` or clean recreation is selected per worktree
- whether `.github/workflows/cleanup_agent.yml` is disabled or removed in a
  separately approved change
- final automation name and schedule

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`。
- [x] 已阅读 tooling, architecture and linter constraints。
- [x] 已明确本规划目标和非目标。
- [x] 已确认不会读取真实邮箱、真实密钥或真实客户数据。
- [x] 已确认当前用户修改不属于本规划文档 scope。
- [x] Issue #30 compatibility-seam implementation 已批准。
- [x] Issue #30 baseline 是 reviewed `origin/master@772a34d` checkpoint。
- [x] Issue #51 pure contracts only are implemented and default blocked。
- [x] Issue #52 synthetic journal/state proof is implemented without host
  capability。
- [x] Issue #53 read-only preflight composition is implemented, Windows-tested
  only in caller-owned temporary sandboxes, and operator-blocked。
- [x] Issue #54 profile-bound review/create/verify composition exists only for
  test-owned temporary synthetic sandboxes; real entries remain locked and no
  real package was created。
- [ ] Issues #55 through #59 remain separately approved and unimplemented here。
- [ ] Full cutover implementation Issues 已批准。
- [ ] 维护窗口已确认。
- [ ] Baseline and rollback artifacts 已生成并验证。

## 17. Remote provider private-context checklist

Not applicable to this planning-only change. The design does not change remote
AI input, runtime knowledge, privacy transformation, provider routing or budgets.
All providers remain disabled throughout migration.

## 18. Administrator stage-evaluation checklist

Not applicable. Raw-vault to evaluation staging is unchanged and remains disabled.

## 19. Final dataset build and interactive judge checklist

Not applicable. Evaluation build, verify and run behavior is unchanged.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable. Manual sync and current-click evidence contracts are unchanged.

## 21. 执行后记录

```text
实际修改文件:
- Planning documents plus the bounded Issue #30/#31/#32/#33/#34/#35/#36 checkpoints.

测试结果:
- Each implemented checkpoint records focused and full verification in its
  dedicated task brief.

未完成事项:
- Real audit composition, real evidence-package generation, migration and
  Issues #37 through #40.

后续建议:
- Continue only with the next separately approved dependency-ordered Issue.
```
