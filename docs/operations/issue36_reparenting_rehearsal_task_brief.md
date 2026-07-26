---
last_update: 2026-07-25
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Issue #36 synthetic repository reparenting rehearsal task brief

## 1. 任务名称

```text
rehearse repository and worktree reparenting
```

## 2. 任务类型

```text
security
```

## 3. 当前状态

```text
implemented
```

## 4. 任务目标

只在一个有明确 synthetic marker 的 temporary project 中演练完整
legacy-source rename、既有 Git common directory 与 source reparenting、linked
worktree recovery、ContainerAudit 和 publication-boundary rollback。演练必须证明
captured baseline 与迁移后 Git/source state 一致，并复用 Issue #35 contract 生成和
验证 synthetic evidence package。

## 5. 非目标

- 不生成当前真实仓库的 evidence package。
- 不在真实根工作区 pull、merge、rebase、rename、move、repair、prune 或实施。
- 不删除、覆盖、移动、修复或清理任何真实 worktree、branch、directory、ACL、
  runtime 或 database。
- 不把 fresh clone 当作迁移实现。
- 不访问 mailbox、provider、vault、private store、credentials、signing material
  或真实私有数据。
- 不增加 normal runtime、browser、frontend、public HTTP、CLI、scheduler、workflow
  或 default host adapter 入口。
- 不开始 Issues #37 through #40，不自动 merge，不关闭 parent Spec #29。

## 6. 背景与依据

实施前的实时准入证据为：

- PR #47 is MERGED，merge commit 为
  `0a6e6ba7b6047f7cfbc52772712e4e2b0b6f70a2`。
- Issue #35 is CLOSED/completed。
- Issue #36 is OPEN，唯一 label 为 `ready-for-agent`，唯一 blocker #35 已关闭。
- Remote `master` 精确指向
  `0a6e6ba7b6047f7cfbc52772712e4e2b0b6f70a2`。
- 独立实施 worktree 为
  `D:\Projects\email_ai_assistant_issue_36_reparenting_rehearsal`，branch 为
  `codex/issue-36-reparenting-rehearsal`。
- 真实根工作区、local branches 和所有既有 worktrees 已只读盘点并作为
  user-owned preserved state。

相关文档：

- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/issue34_content_free_container_audit_task_brief.md`
- `docs/operations/issue35_migration_evidence_package_task_brief.md`
- `docs/operations/project_status_log.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- GitHub Issue #36

## 7. 涉及范围

预计新增或修改：

- `backend/reparenting_rehearsal/`
- `tests/reparenting_rehearsal_fixtures.py`
- `tests/test_reparenting_rehearsal_*.py`
- `tests/test_architecture_constraints.py`
- `tests/test_static_linter_constraints.py`
- `AGENTS.md`
- `CONTEXT.md`
- `docs/constraints/`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/project_structure.md`
- `docs/operations/testing_checklist.md`
- `docs/operations/project_status_log.md`
- `docs/templates/agent_task_brief_template.md`
- `scripts/generate_project_status.py`

不修改 frontend、mailbox/private-store/provider code、service lifecycle、real host
configuration 或 `.github/workflows/cleanup_agent.yml`。

## 8. 技术方案

### 8.1 Confirmed public seam

TDD 只覆盖一个 approved manual internal Python seam：

`rehearse_repository_reparenting(*, worktree_choices, fail_at)`。

- `worktree_choices` 必须是 synthetic scenario 中 exact worktree ID 的 complete
  injected reviewed choice set；每项只能为 `repair` 或 `recreate`。
- `fail_at` 必须显式传入 `None` 或一个 fixed publication-boundary enum。
- 返回值只包含 fixed status 和 aggregate counts。

Public seam 不接受 `Path`、source、target、repository、host adapter、reader、
environment 或 callback capability。模块内部自行创建 unique
`TemporaryDirectory(delete=False)` 与固定 synthetic scenario；它不自动清理
source、legacy source、worktree、target 或 rollback path。测试只在独立观察完成后
清理 caller-owned parent。它不提供 ambient/current-repository default，不从 cwd、
environment、request、CLI 或 config 自动发现 target。

### 8.2 Synthetic scope gate

Source 必须位于 OS temporary root 下的 dedicated scope，scope 中必须有由 builder
创建并绑定的 synthetic marker。Canonical source 名称为 `email_ai_assistant`；
legacy source 为同级 `email_ai_assistant-legacy-source`；staging Container 为同级
唯一路径。任一 scope/path/identity/marker drift、reparse component、existing target
或非 synthetic local-only remote 都 fail closed。Builder 绑定 marker filesystem
identity；每次 publication 前重验，same-text replacement 也必须失败。
完整 synthetic project 与 exact local-only remote 还必须在 baseline capture
前后再次验证；captured remote fingerprint 必须精确等于 fixed local bare
remote，不能把 capture-window drift 当作新 baseline。

### 8.3 Baseline and Issue #35 evidence

Internal evidence bridge 只在 synthetic source 上调用
`prepare_migration_evidence_review(...)`。Runner 在任何 rename 前，以 exact
review fingerprint 创建并立即独立验证一个 source/worktrees/Container 外部的
synthetic `*.migration-evidence.zip`。

Additional baseline 绑定：

- all local `refs/heads/*` 与 OID；
- branch、HEAD、upstream、remote config fingerprint、ahead/behind；
- Git common directory filesystem identity；
- exact tracked/index state、reviewed untracked paths 与 SHA-256；
- 每个 main/linked worktree 的 branch、HEAD、clean status 和 common identity；
- excluded category metadata 与 legacy-source location，不读取其 bytes。

### 8.4 Reparenting and reviewed worktree choices

Runner 先把完整 synthetic old root rename 为 legacy source，再把预先创建并验证的
clean Project Container 发布到 canonical replacement path。现有 `.git` common
directory、tracked content 和 reviewed untracked source 通过 checked no-clobber
rename 进入 `main`；不执行 clone。

每个 linked worktree 必须有 exactly one injected reviewed choice：

- `repair`：checked rename 既有 worktree directory 到 `Worktrees/<name>`，再使用
  bounded synthetic Git command repair metadata。
- `recreate`：保留 legacy-source 中的 original directory，使用同一既有 Git
  common directory 在 `Worktrees/<name>` create a clean worktree，并只移除 stale
  synthetic administrative entry；不删除 original directory。
所有 fixed target 必须在任何 worktree/admin mutation 前一次性验证为 absent；
existing empty target 同样 fail closed。Direct `Worktrees` parent 必须保持
non-reparse resolved containment，并在 `git worktree add` 前再次验证；junction
不得把 target 逃逸到 Container 外。

迁移后逐项验证每个 active worktree 的 branch、commit、common identity 与 clean
status。

### 8.5 ContainerAudit

Internal audit bridge 只依据已完成且已验证的 synthetic state 构造
content-free `TrustedAuditPolicy` 与 exactly seven metadata adapters。它不读取真实
ACL、volume、runtime、SQLite 或 private content；`backend.container_audit` 继续
没有 real adapter、default adapter、CLI、scheduler 或 normal-runtime consumer。
Audit 必须返回 `container_audit_passed`，legacy source 必须保持在 Container 外。

### 8.6 Publication boundaries and rollback

Boundaries 固定为：

1. verified synthetic evidence package；
2. complete legacy-source rename；
3. clean Project Container publication；
4. main Repository Root publication；
5. linked-worktree publication；
6. passed ContainerAudit。

每个 boundary 后调用 injected failure seam。失败时不得 unlink/rmdir/delete 或覆盖
source、legacy source、worktree、target。Rollback 只允许 checked no-clobber rename
到唯一 preserved rollback path，且返回前必须重新验证 Issue #35 package 和可恢复
source/common-directory identity。Main/worktree/audit failure 将完整 Container
no-clobber rename 到该 rollback path，再修复 exact reviewed relocated worktrees。
Public failure 为 fixed `reparenting_rehearsal_rollback_verified` 或
`reparenting_rehearsal_failed`，没有 path、ref、exception 或 content。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

无 HTTP API 变化。新增 synthetic-only manual internal Python interfaces。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱或真实私有数据。
- [x] 不自动发送、删除或归档邮件。
- [x] 不访问 provider、vault、private store、credentials 或 signing material。
- [x] Ignored/excluded canary bytes 不读取、不移动。
- [x] Tests 只使用 temporary synthetic repositories 和 local bare remote。
- [x] 不对真实 root/worktree/branch/ACL/runtime/database 执行 mutation。
- [x] Public results 只含 fixed status/counts。
- [x] 不增加 runtime/browser/frontend/CLI/workflow consumer。

## 11. Prompt Injection 防护

不适用。本任务不处理邮件、prompt 或 model output。所有 path、ref、remote、
filename 和 Git output 仍按不可信输入处理；不把其内容作为 command，不允许 option
injection、path escape、alias/reparse escape 或 unbounded output。

## 12. 验收标准

1. 完整 synthetic old root 成为 legacy source，clean Container 发布到 canonical
   replacement path。
2. 既有 Git common directory、tracked content 和 reviewed untracked source 进入
   `main`，无 fresh clone。
3. Ignored credentials/signing/runtime/outputs/IDE/caches/excluded canaries 原位留在
   legacy source且 bytes 未被读取。
4. Branch、HEAD、refs、remote、ahead/behind、tracked/untracked state 和 hashes
   与 baseline 一致。
5. 每个 linked worktree 按 injected repair/recreate choice 完成，保留 branch、
   commit、common identity 和 clean status。
6. New synthetic Container passes ContainerAudit，legacy source stays outside。
7. 每个 publication boundary failure 都保留 original source 或 independently
   verified rollback path。
8. Source、legacy source、worktree 和 target 不被删除或覆盖。
9. #35 package 只针对 synthetic source 创建和验证。
10. 不触碰真实 workspace，不实现 #37 through #40。

## 13. 测试计划

按 vertical TDD slices 执行：

- RED/GREEN: fixed public request and content-free result contract。
- RED/GREEN: internally-created synthetic scope/path/marker gate。
- RED/GREEN: #35 evidence create/verify and complete baseline capture。
- RED/GREEN: complete source rename plus no-clobber main reparenting。
- RED/GREEN: excluded categories remain in legacy without byte reads。
- RED/GREEN: injected repair and recreate choices。
- RED/GREEN: post-state equality and ContainerAudit pass。
- RED/GREEN: failure injection at every publication boundary and verified
  rollback preservation。
- RED/GREEN: reject existing target, missing choice, drift, non-local remote,
  reparse and any real/non-temporary path。
- Focused Issue #36 tests。
- Architecture/linter/mechanical/documentation tests。
- `python -m compileall backend scripts tests`。
- Full `python -m unittest discover -s tests`。
- Repository leakage scan API with fixed content-free summary。
- `python scripts/maintenance_scan.py`。
- `git diff --check`。

## 14. 回滚方案

Versioned implementation 只发生在新独立 branch/worktree。Synthetic rehearsal
自身的 rollback 不删除任何 preserved object：pre-publication failure 使用
no-clobber rename 恢复 canonical source；post-publication failure 保留 legacy、
partial/complete Container 与 verified evidence package，并把可恢复 topology 移到
唯一 rollback path。任何身份或 package re-verification 失败返回固定 failure 并停止。

## 15. 需要人工确认的问题

无。Issue #36、用户指令和 parent migration brief 已确认 public seams、synthetic
scope、injected choices、failure boundaries 与禁止事项。

## 16. 预期输出

- Synthetic-only reparenting rehearsal module。
- Synthetic topology/failure-injection tests。
- Updated architecture/tooling/mechanical/documentation contracts。
- Full verification and dual-axis code-review evidence。

## 17. Repository placement and operational layout checklist

- [x] Managed topology remains exactly `email_ai_assistant/main`。
- [x] No new implicit placement mode is added。
- [x] Synthetic scope is explicit, temporary, marker-bound and fail-closed。
- [x] No normal runtime, public request, environment or CLI can supply roots。
- [x] Protected/private-store policies are unchanged。
- [x] ContainerAudit remains content-free, injected and without real adapter。
- [x] Migration evidence is synthetic-only and separately verified。
- [x] Tests never migrate the real repository or create a real Managed Container。

## 18. 执行后记录

```text
实际修改文件：
- `backend/reparenting_rehearsal/`
- `tests/test_reparenting_rehearsal_*.py`
- exact architecture/status-generator guards
- AGENTS/CONTEXT/ADR/constraints/operations/template/status documentation

测试结果：
- Focused Issue #36: 17 tests, `OK`.
- Issue #35 regression: 32 tests, `OK (skipped=1)`.
- ContainerAudit regression: 38 tests, `OK`.
- Architecture/static/status/transport after the final record update: 115 tests, `OK`.
- Full unittest after generated status update: 1853 tests, `OK (skipped=3)`.
- `compileall` and `git diff --check`: exit 0.
- Inclusive repository leakage scan: `total=0`.
- Maintenance scan: `No cleanup findings detected.`
- Standards/Spec dual-axis review: no P1/P2 findings.
- Non-blocking P3: `test_reparenting_rehearsal_has_no_host_consumers` is
  54 lines versus the 50-line recommendation; no behavior or safety boundary
  is affected.

未完成事项：
- Real evidence package, audit, migration/cutover and Issues #37 through #40.

后续建议：
- Continue only through the next separately approved dependency-ordered Issue.
```
