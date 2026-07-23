---
last_update: 2026-07-23
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
4. 记录 baseline status, refs, worktrees, file hashes, ACL and volume evidence，
   并通过 mandatory manual preflight container audit。
5. 正常停止 local service。
6. 创建 allowlisted rollback artifacts and empty target directories。
7. 收紧 container ACL，但不影响 `D:\Projects` 或 finance project。
8. 将完整 Git repository 重新归属到 `main`。
9. 重建 runtime and worktrees。
10. 迁移 LocalData and non-sensitive artifacts。
11. 在 operator identity ready 后隔离 legacy credentials。
12. 更新 project config, docs and local bindings。
13. 运行 full verification、disabled-provider health check 和 mandatory manual
    post-cutover container audit。
14. 保留所有旧来源，直到单独 cleanup approval；此时 `D:\Projects` 暂时仍可超过
    两个一级目录。
15. 仅在另一个 cleanup Issue 获得明确删除批准后，把已验证旧来源送入 Recycle Bin，
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

## 9. 数据结构或接口变化

### 数据库变化

无 schema change。只规划 normal analysis SQLite 的 path relocation。

### API 变化

新增内部 Python `RepositoryPlacement`/`OperationalLayout` compatibility
interfaces；无 HTTP API 变化。

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
- Planning documents plus the bounded Issue #30 compatibility seam.

测试结果:
- Issue #30 focused and full verification are recorded in its dedicated task brief.

未完成事项:
- All real migration and Issue #31 through #40 work.

后续建议:
- Continue only with the next separately approved dependency-ordered Issue.
```
