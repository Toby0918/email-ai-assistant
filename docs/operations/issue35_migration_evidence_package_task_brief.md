---
last_update: 2026-07-25
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Issue #35 no-clobber migration evidence package task brief

## 1. 任务名称

```text
create a no-clobber migration evidence package
```

## 2. 任务类型

```text
security
```

## 3. 当前状态

```text
implementation_complete_review_pending
```

## 4. 任务目标

实现一个可独立验证的 migration evidence package，在任何真实 cutover 前保护
reviewed local Git refs、明确批准的 worktree HEAD、reviewed dirty source 以及
content-free Git/ACL/volume baseline。所有自动验证只使用 synthetic repositories
和 temporary destinations。

## 5. 非目标

- 不生成真实根工作区的最终 evidence package。
- 不替操作者选择真实 target、reviewed refs、worktrees 或 dirty-source allowlist。
- 不停止服务，不移动、复制、修复、prune 或删除任何现有仓库、worktree、branch
  或目录。
- 不 pull、merge、rebase 或在根工作区实施。
- 不修改 ACL，不执行 Project Container cutover，不开始 Issues #36 through #40。
- 不访问 mailbox、provider、vault、private store、credentials、signing material、
  ignored SQLite 或真实私有数据。
- 不把 deleted GitHub feature branch 或 remote-tracking ref 当作原始分支证据。
- 不自动 merge，不关闭 parent Spec #29。

## 6. 背景与依据

GitHub Issue #35 要求 create-only、fail-closed 的 evidence package。实施前的实时
准入证据为:

- Issue #34 is CLOSED。
- Issue #35 is OPEN and labelled `ready-for-agent`。
- Issue #35 的唯一 blocker #34 已关闭。
- Remote `master` resolves to
  `246c684563720f97f1e108c236d77c4f2b8040d0`。
- 实施 worktree 为独立 branch
  `codex/issue-35-migration-evidence-package`。
- 根工作区和全部既有 local worktrees 已通过 `git worktree list` 与独立
  `git status` 只读盘点，并全部视为 user-owned preserved state。

相关文档:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/project_status_log.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- GitHub Issue #35

## 7. 涉及范围

预计新增或修改:

- `backend/migration_evidence/`
- `tests/test_migration_evidence_*.py`
- `tests/test_architecture_constraints.py`
- `tests/test_static_linter_constraints.py`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/project_structure.md`
- `docs/operations/testing_checklist.md`
- `docs/operations/project_status_log.md`
- `scripts/generate_project_status.py`

不修改 frontend、mailbox/private-store/provider code、service lifecycle 或
`.github/workflows/cleanup_agent.yml`。

## 8. 技术方案

### 8.1 Public seams

TDD 只覆盖三个已批准 public seams:

1. `prepare_migration_evidence_review(...)` 通过 Git status、local refs 和
   `git worktree list` 实时发现 source state，返回 repr-redacted 的 exact review
   plan 与 SHA-256 review fingerprint。
2. `create_migration_evidence_package(...)` 只接受 exact confirmed fingerprint，
   在 source identity 两次一致后写入一个 create-only package target。
3. `verify_migration_evidence_package(...)` 在独立 temporary Git repository 中
   校验 package、Git bundle、manifest、snapshot 和 reviewed worktree identity。

### 8.2 Review and confirmation boundary

Review plan 记录:

- exact target；
- every dirty path 的 include/exclude classification；
- reviewed `refs/heads/*` 与 OID；
- reviewed worktree path identity、branch ref 与 HEAD；
- content-free status、current branch、HEAD、remote fingerprint、
  ahead/behind、ACL fingerprint 和 volume fingerprint。

真实根工作区只能先生成上述 content-free review value。操作者单独确认 exact
fingerprint 后，later invocation 才能进入 create seam。本 Issue 的自动测试和本次
执行都不得对真实根工作区调用 create seam。

### 8.3 Package contents

Package 使用标准库容器并包含:

- independently verified Git bundle for exact reviewed local branch refs；
- bounded Git/worktree/host baseline JSON；
- exact dirty snapshot index；
- approved index/worktree bytes for source, tests and documentation only；
- canonical SHA-256 manifest。

Manifest 使用 ordered path、size 和 SHA-256 绑定每个 payload file，并将
review fingerprint、package identity、Git evidence、snapshot evidence 纳入同一
canonical identity。Verifier 拒绝 missing、duplicate、unknown 或 drifted entries。

### 8.4 Dirty-source policy

每个 dirty path 必须 exact classified。只有显式批准且通过 source/test/docs policy
的 tracked/untracked path 才能读取 bytes。Ignored credentials、signing material、
SQLite、logs、PID state、virtual environments、IDE state、private data、caches
和未批准 outputs 只做 metadata classification，绝不打开。

Tracked staged 与 worktree versions 分别保存。Deleted path 只保存状态，不伪造
content。Symlink、reparse、submodule、unmerged state、unsupported type、path
escape、size overflow 或 identity drift fail closed。

### 8.5 Git and worktree policy

Bundle source 只允许 exact reviewed `refs/heads/*`。Remote refs 和已删除的
GitHub feature branches不得成为 source。每个 approved worktree 必须来自实时
`git worktree list`，保持 branch-attached，且 branch ref/OID/HEAD 与 review plan
完全一致。Bundle 必须在一个 empty synthetic repository 中通过独立
`git bundle verify`。

### 8.6 Create-only publication

Target 和 parent 在写入前后进行 absolute、non-reparse 和 identity checks。Payload
先写入 bounded internal stage；final publication 使用 same-volume atomic
no-clobber link。Existing target、post-validation racer、partial write 或 identity
drift 不得覆盖 target。Publication helper 成功返回是唯一 commit point；其后只允许
best-effort internal-stage cleanup，绝不按 pathname rollback final target。

### 8.7 Public result

Create/verify 的 public result 只含 fixed allowlisted status code 与 aggregate
counts。Native exception、path、ref、account、secret、matched value 或 file content
不得进入 result、repr、log 或 error text。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

无 HTTP API 变化。新增 manual internal Python interfaces only。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除或归档邮件。
- [x] 不在前端保存或暴露 API key。
- [x] 不处理邮件正文或 provider output。
- [x] Public result 只含 fixed code/counts。
- [x] Tests 使用 synthetic repositories and temporary destinations。
- [x] Ignored/private/credential paths 只分类，不读取。
- [x] 不修改 ACL、volume、service、repository placement 或 existing worktree。

## 11. Prompt Injection 防护

不适用。本任务不处理邮件、prompt 或 model output。所有 Git path、ref、remote
metadata 和 manifest field 仍按不可信输入处理，不执行其中命令，不允许 path
escape 或 option injection。

## 12. 验收标准

1. Git bundle 只覆盖 reviewed local refs，并可在 empty repository 独立 verify。
2. Exact dirty-source snapshot 覆盖批准的 tracked/untracked source、tests 和 docs，
   并区分 index/worktree/deleted state。
3. SHA-256 manifest 绑定 package identity、review fingerprint、Git evidence、
   snapshot index 和每个 payload file。
4. Status、branch、HEAD、remote fingerprint、ahead/behind、refs、worktrees、ACL
   和 volume baseline 有界且 content-free。
5. Forbidden ignored/private/output categories 被机械排除且未打开。
6. Existing target、reparse、race、partial write 或 identity drift fail closed，
   target 不被覆盖。
7. Public result 只含 fixed code and aggregate counts。
8. Synthetic restore tests 证明 Git objects/refs、dirty source 和 worktree identity
   可独立恢复。
9. 不停止服务、不移动仓库、不修改 ACL，不访问 mailbox/provider/private store。
10. 没有实现 Issues #36 through #40。

## 13. 测试计划

按 vertical TDD slices 执行:

- RED/GREEN: exact discovery and review fingerprint。
- RED/GREEN: reviewed local refs bundle and independent verify。
- RED/GREEN: tracked index/worktree and approved untracked snapshot restore。
- RED/GREEN: forbidden/ignored classification without content reads。
- RED/GREEN: worktree identity, status/remote/ahead-behind/host baseline。
- RED/GREEN: create-only existing target, reparse, race, partial write and drift。
- RED/GREEN: fixed content-free public results and manifest tamper rejection。
- Focused migration-evidence tests。
- Architecture/linter/mechanical/documentation tests。
- `python -m compileall backend scripts tests`。
- Full `python -m unittest discover -s tests`。
- Repository leakage scan API with a content-free fixed-code summary。
- `python scripts/maintenance_scan.py`。
- `git diff --check`。

## 14. 回滚方案

本实现仅在新独立 branch/worktree 中变更 versioned files。失败时停止并保留
user-owned root 和既有 worktrees 原样。Synthetic target 位于 temporary directory
并由测试生命周期处理。不得删除、prune、repair 或 reset 任何 existing worktree/
branch/directory，也不得生成真实 package 后再尝试 pathname rollback。

## 15. 需要人工确认的问题

- [x] Issue #35 scope and acceptance are explicit。
- [x] TDD seams are explicit in the user request and this brief。
- [x] Remote base, branch and worktree are explicit。
- [x] Automated verification is synthetic/temp only。
- [ ] Real package exact target。
- [ ] Real content-free include/exclude manifest。
- [ ] Real reviewed refs and worktree selection。
- [ ] Separate confirmation matching the real review fingerprint。

未完成的四项是 intentional stop gate，不阻断 synthetic implementation。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`。
- [x] 已阅读 project status、tooling、architecture、linter 和 mechanical constraints。
- [x] 已阅读 ADR 0009 与 migration planning brief。
- [x] 已明确任务目标、非目标和 TDD seams。
- [x] 已确认不访问真实邮箱、provider、vault、credentials 或 private data。
- [x] 已确认只在独立 Issue #35 worktree 修改。
- [x] 已确认不触碰根工作区和 existing worktrees。
- [x] 未新增依赖。

## 17. Remote provider private-context checklist

不适用。Provider 路由、remote input、runtime knowledge、privacy transform 和 budget
均不变，providers remain disabled。

## 18. Administrator stage-evaluation checklist

不适用。Raw-vault to evaluation staging 不变。

## 19. Final dataset build and interactive judge checklist

不适用。Private evaluation build/verify/run 不变。

## 20. Bounded corpus-to-runtime handoff checklist

不适用。Manual sync and current-click evidence contracts 不变。

## 21. Repository placement and migration-evidence checklist

- [x] Source repository and linked-worktree inventory are discovered live through
  Git; no existing worktree path is hard-coded in the implementation。
- [x] Package targets must be exact, external to the source repository, absent,
  create-only and non-reparse。
- [x] Git evidence is restricted to exact reviewed local `refs/heads/*` plus the
  approved root and linked-worktree identities。
- [x] Git bundle, Git/worktree/host baselines, dirty snapshot and every payload
  file are bound by the canonical SHA-256 manifest。
- [x] Index and worktree layers remain separate; deleted paths remain
  content-free records。
- [x] Ignored credentials, signing material, SQLite, logs, PID state, virtual
  environments, IDE state, private data, caches and unapproved outputs are
  mechanically excluded without content reads。
- [x] No CLI, runtime, browser, mailbox, provider, vault, maintenance or
  scheduled-workflow consumer is introduced。
- [x] Automated verification uses only synthetic repositories and temporary
  destinations。
- [x] A real package requires prior display of the exact target, content-free
  inclusion/exclusion manifest, reviewed refs and worktree selection, followed
  by a separate operator confirmation。
- [x] Issues #36 through #40 remain outside this implementation。

## 22. 执行后记录

```text
实际修改文件:
- backend/migration_evidence/ deep module
- migration-evidence focused tests and repository guard tests
- repository leakage scanner and generated project-status contracts
- AGENTS, README, CONTEXT, ADR 0009, constraints, planning/status/structure/
  testing/template documentation

测试结果:
- focused migration-evidence: 20 passed, 1 skipped because Windows directory
  symlink creation privilege is unavailable
- architecture/static/mechanical/leakage/status/transport: 120 passed
- compileall: passed
- full unittest final run: 1,818 passed, 3 skipped
- repository leakage summary: total=0
- maintenance scan: no findings
- git diff --check: passed

未完成事项:
- Standards/Spec dual-axis review and publication workflow are pending
- real package review and separate confirmation remain intentionally pending

后续建议:
- do not begin Issue #36 without separate authorization
```
