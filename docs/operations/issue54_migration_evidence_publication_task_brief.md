---
last_update: 2026-07-27
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue #54 Migration Evidence publication task brief

## 1. 任务名称

```text
compose reviewed Migration Evidence Package publication and verification
```

## 2. 任务类型

```text
security
```

## 3. 当前状态

```text
in_progress
```

## 4. 任务目标

只针对 GitHub Issue #54 建立 profile-bound evidence review、物理分离的
create-only publication composition，以及运行在独立进程中的 read-only
verification。Review、created、verified 三类 content-free receipt 必须绑定同一
operation、`CutoverProfileV1`、governing master、review fingerprint、package
and manifest hashes，以及适用的 aggregate counts。

Create 必须要求 exact `EvidencePublicationAuthorizationV1` 和人工精确确认的
review fingerprint，并重新执行完整 live discovery。真实 operator entry 在
Issue #39 之前保持锁定。

## 5. 非目标

- 不创建真实 Migration Evidence Package，也不读取真实 Repository Root 或任何
  既有 worktree 内容。
- 不运行真实 host preflight，不停止或启动 service，不 apply ACL，不移动
  repository/worktree，不 build Runtime，不 copy database。
- 不读取或调用 provider、mailbox、vault、credential、private store 或 private
  data。
- 不把 package 表述为 backup、Runtime artifact、private container 或 migration
  authorization。
- 不实现 Issue #55–#59，不修改或关闭 Issues #38/#39，不关闭 parent Spec #50。
- 不增加 CLI、workflow、scheduler、normal runtime、frontend、cleanup 或 root
  wrapper consumer。
- 不签发、mint、伪造或保存 real-host authorization。
- 不修改公开 HTTP API、SQLite schema、prompt、AI JSON、provider routing 或
  dependencies。
- 不 merge PR，不触碰根工作区或任何既有 worktree。

## 6. 背景与依据

实施前实时门禁:

- Remote `master` 精确指向
  `9f93e3bc01687ab3a263dd111183d2bfb4abead6`，与操作员指定 fixed point
  一致。
- Issue #54 为 `OPEN`、`ready-for-agent`；唯一直接 blocker #53 已完成，GitHub
  native dependency summary 无未完成 blocker。
- Parent Spec #50 保持 `OPEN`；#54 只是 P4，当前阻塞仍未开始的 #59。
- Issue #39 仍未提供可执行真实 operator command，因此所有真实 entry point
  必须保持 default locked。
- 根工作区存在 user-owned dirty state，且已有多个 worktree；本任务使用从精确
  remote baseline 创建的 clean isolated worktree 和
  `codex/issue-54-migration-evidence-publication` branch。

相关依据:

- GitHub Issues #50、#53 and #54
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/issue35_migration_evidence_package_task_brief.md`
- `docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md`
- `docs/operations/issue53_windows_real_host_preflight_task_brief.md`
- `docs/security/project_container_cutover_contracts.md`
- tooling、architecture、linter、mechanical、CI、testing and review constraints

## 7. 涉及范围

预计新增:

- profile-bound review and create-only publication composition package
- physically separate read-only verifier-process package
- exact migration-evidence、cutover-contract and read-only preflight bridges
- closed content-free review、created and verified receipt views
- receipt consistency/pre-mutation handoff readiness gate
- focused synthetic fixtures and tests for Issue #54
- 本 task brief

预计修改:

- 既有 migration-evidence neutral validation/result seams，以移除 creator 对
  independent verifier 的能力和 verifier 对 publication module 的依赖
- exact bridge consumer allowlists and executable architecture guards
- `AGENTS.md`、`CONTEXT.md`、`README.md`
- ADR、security、tooling/architecture/linter/mechanical/CI constraints
- migration、project-structure、testing and task-template operations docs
- project-status generator、generator tests and generated status log

不修改 frontend、normal runtime、provider、mailbox、vault、private knowledge、
private evaluation、requirements、service scripts、root wrappers、existing
worktrees 或 workflows。

## 8. 技术方案

### 8.1 TDD public seams

测试只通过以下已由 Issue #54 和操作员要求预先确认的 public seams 观察行为:

1. profile-bound evidence review；
2. independently authorized create-only publication composition；
3. separate-process read-only verification；
4. review/created/verified receipt consistency gate；
5. default-locked real operator entries。

每个 vertical slice 遵循 one public failing test -> minimal implementation ->
focused GREEN。Git discovery、host-baseline collection、process launch 和
temporary filesystem 是 system boundaries；测试只注入 exact narrow adapters
或 test-owned temporary synthetic state，不 mock package internals。

### 8.2 Profile-bound review

Review 接受 exact canonical `CutoverProfileV1`、operation fingerprint、
governing master、适用的 exact authorization、已绑定到 Profile 的 selection，
以及 Issue #53 read-only baseline seam。它调用既有 Issue #35 complete discovery
并产生 in-memory `MigrationEvidenceReview`。

公开 `MigrationEvidenceReviewReceiptV1` 只暴露 closed enums、opaque SHA-256
fingerprints and bounded counts。它绑定 operation、Profile、master、review、
selection、Git、host and target identity；不得持久化或序列化完整
`MigrationEvidenceReview`，不得暴露 path、ref、object ID 或 worktree name。

### 8.3 Create-only publication composition

Create 物理上与 verifier 分离，只能接受 exact
`EvidencePublicationAuthorizationV1`、同一 Profile/operation/master、review
receipt、in-memory review 和 exact operator-confirmed review fingerprint。

在 publish 前必须重新运行完整 discovery，并与 confirmed review and receipt
逐项一致；任何 selection、dirty layer、local ref、worktree、Git、
HostBaseline、target or Profile drift 固定失败。既有 Issue #35 create-only
publisher仍负责 no-clobber package commit。

`MigrationEvidenceCreatedReceiptV1` 绑定 review、package、manifest、
package-identity and aggregate-count fingerprints。Creator 可使用共享的纯
package-format validation，但不得导入、构造或调用 independent verifier
process/capability。

### 8.4 Separate read-only verification process

Verifier 使用独立 package and process entry，只获得 read-only package
descriptor/value and expected content-free bindings。它重新读取 package，调用
既有 independent package verifier，并独立重新计算 package SHA-256 and
manifest SHA-256。

Verifier package 不得导入 publication、create-only publisher、write、
replace、rename、unlink、remove、mkdir 或 package target mutation capability。
Parent 只接受 strict canonical child response；timeout、non-zero exit、
malformed/duplicate/unknown output、hash/count mismatch、collision、corruption
或 manifest mismatch 固定失败，不包含 child exception text。

### 8.5 Receipt consistency gate

`MigrationEvidenceReceiptSetV1` 只在 review、created and verified receipts
exact match 以下 bindings 时产生:

- operation fingerprint；
- Profile fingerprint；
- governing master fingerprint；
- review、selection、Git and HostBaseline fingerprints；
- package、manifest and package-identity fingerprints；
- applicable exact aggregate counts。

该 value 只表示后续 pre-mutation gate 可消费的一致 evidence receipt set；它本身
不是 migration authorization，不执行 preflight、mutation、cutover 或 final
integration。

### 8.6 Test sandbox and operator lock

所有 package creation and verification tests 只在 test-owned
`TemporaryDirectory` synthetic Git sandboxes 中运行。Package-private sandbox
binder 只能接受 exact `TestSandboxAuthorizationV1` and marker-bound scope；
测试中的 review/create/verify operation authorization 仍分别使用 exact
`RealPreflightAuthorizationV1`、`EvidencePublicationAuthorizationV1` and
`RealPreflightAuthorizationV1` canonical values。

Zero-capability operator command 始终返回 fixed
`BLOCKED_NO_APPROVED_COMMAND`。单独的 locked real entry validation seam 只接受
authorization value，不接受 path、callback or command，并对 missing、
wrong-phase and `TestSandboxAuthorizationV1` 返回 fixed rejected result；即使
收到结构正确的 real authorization，在 Issue #39 前也不得执行。

### 8.7 Content-free boundary

Receipt、result、repr、stdout、stderr and logs 只允许 fixed enum、opaque
SHA-256 fingerprints and bounded counts。Raw path、Git ref/name/OID、worktree
name、file content、command、native error and exception text 必须被拒绝或
丢弃。Production code 不使用 `print()`，不把 callback/process exception
格式化到公开结果。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

只新增 internal Python composition、read-only process and receipt interfaces；
无 HTTP API、CLI 或 executable Issue #39 command。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱、真实 Repository Root、existing worktree 或 private data。
- [x] 不自动发送、删除或归档邮件。
- [x] 不引入 provider、mailbox、vault、credential 或 private capability。
- [x] Package creation only occurs inside test-owned temporary synthetic roots。
- [x] Complete review remains in memory and is not alternate persisted authority。
- [x] Creator owns no independent verifier capability；verifier owns no publisher
  or mutation capability。
- [x] Public outputs expose no path、ref、OID、worktree name or exception text。
- [x] No real-host authorization issuer or executable operator command exists。
- [x] Root worktree and all existing worktrees remain preserved。

## 11. Prompt Injection 防护

Not applicable to AI input。Profile、authorization、receipt、Git discovery、
HostBaseline、child-process response and package values are untrusted and must
pass exact types、canonical decoding and closed validation；no string is
interpreted as command、path override、exception、script or free-form
instruction。

## 12. 验收标准

1. Review exact profile-bound dirty-source、local-ref、worktree、package-target、
   Git and RealHostBaseline selections，且没有 arbitrary replacement input。
2. `MigrationEvidenceReviewReceiptV1` 绑定 operation、Profile、master、review、
   selection、Git、host and counts，且 content-free。
3. Complete `MigrationEvidenceReview` 不持久化为 alternate authority。
4. Create 是物理分离的 publication composition，要求 exact
   `EvidencePublicationAuthorizationV1` and confirmed review fingerprint。
5. Create 重复完整 discovery，并通过 creator-owned source-snapshot、
   staged package/manifest and published-identity bindings 拒绝 post-review、
   post-rediscovery and post-commit replacement。
6. Created receipt 绑定 review、package、manifest、package identity and counts。
7. Verification 在分离 read-only process 中通过 bounded descriptor 首次读取
   package，只把该 exact payload 交给 independent verifier，随后要求 target
   重读 identity/bytes 完全一致，并重新计算 package/manifest hashes。
8. 三类 receipts 在 consistency gate 中对同一 operation、Profile、master、
   review、hashes and counts exact agree。
9. Creator 不能调用 independent verifier；verifier 不能 publish or modify。
10. Existing host-agnostic evidence policy remains free of Windows/filesystem
    mutation、service、ACL apply、Runtime、provider、mailbox、vault and
    private-data capabilities。
11. Real entry points remain locked before Issue #39 and reject missing、
    wrong-phase and test authorization。
12. Synthetic tests cover selection、source bytes、dirty/ref/worktree/
    HostBaseline drift、post-commit replacement、path ABA、collision、
    corruption、manifest mismatch、process separation and leakage。
13. Docs state package is evidence only，not backup、runtime artifact、private
    container or migration authorization。
14. No real operational action or access occurs。

## 13. 测试计划

- TDD vertical slices: review -> create-only composition -> verifier process ->
  receipt consistency -> operator/architecture lock。
- Focused Issue #54 synthetic tests。
- Affected migration-evidence、Issue #51 contracts、Issue #53 baseline、
  architecture、static、mechanical、documentation、status-generator、leakage
  and maintenance regressions。
- Full `python -B -m unittest discover -s tests`。
- `python -B -m compileall -q backend scripts tests`。
- Frontend JavaScript syntax and manifest JSON checks。
- Repository leakage scan、maintenance scan、`git diff --check` and staged
  allowlist validation。
- Standards/Spec parallel review from exact fixed point；P1/P2 repair and
  re-review；P3 record only。
- Ready-for-review PR CI must pass before handoff。

## 14. 回滚方案

This slice changes only versioned source/tests/docs in the isolated worktree。
Before publication, rollback is removal or correction of the allowlisted Issue
#54 paths only。No real package or host state exists to reverse。After
publication, normal Git revert of the Issue #54 commit is sufficient；no host
cleanup or data rollback is authorized。

## 15. 需要人工确认的问题

无。Issue #54、parent #50 and the operator request provide the bounded
composition scope。Any real operator command、migration、mutation、cutover or
Issue #55–#59 work requires separate approval。

## 16. 执行前检查

- [x] 已完整阅读 `$implement`、`$tdd` and `$code-review` skill rules。
- [x] 已阅读 `AGENTS.md`、`CONTEXT.md` and current project status。
- [x] 已阅读 tooling、architecture、linter、mechanical、CI、ADR、security、
  migration and testing rules。
- [x] 已实时核验 Issue #54、parent #50、dependency #53 and exact remote master。
- [x] 已建立 clean isolated worktree from the exact fixed point。
- [x] 已只读盘点并保护 root and all existing worktrees。
- [x] 已确认 TDD public seams、synthetic-only sandbox and locked operator boundary。

## 17. Remote provider private-context checklist

Not applicable。Remote input、runtime knowledge、provider budgets and public
routing remain unchanged；all providers remain disabled。

## 18. Administrator stage-evaluation checklist

Not applicable。Private-evaluation staging is not imported or invoked。

## 19. Final dataset build and interactive judge checklist

Not applicable。No dataset、provider judge、TTY workflow or report is opened。

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable。Mailbox sync and current-click evidence remain unchanged。

## 21. Repository placement and operational layout checklist

- [x] No placement mode、public path override or real operator command is added。
- [x] Profile-bound review reuses complete Issue #35 discovery and Issue #53
  content-free baseline evidence。
- [x] Create requires exact separate authorization and confirmed review
  fingerprint，then repeats complete discovery。
- [x] Publication remains create-only and no-clobber。
- [x] Verification is a separate read-only process and has no publication
  capability。
- [x] Receipts are closed、canonical、content-free and consistent。
- [x] Tests never run against a real Repository Root、existing worktree or real
  package target。
- [x] Issues #55–#59、#38/#39 and parent Spec #50 remain unchanged。

## 22. 执行后记录

```text
实际修改文件:
- backend/migration_evidence/：抽取中立 archive validation/results，增加
  creator-owned source/package/manifest/published-identity binding 与 exact-payload
  independent verification seam。
- backend/migration_evidence_publication/：新增 profile-bound review、separately
  authorized create-only composition、content-free receipts/Set、locked real entries。
- backend/migration_evidence_verifier/：新增 sanitized separate read-only process，
  bounded first read、exact-payload verify、stable reread and process-tree cleanup。
- tests/：新增 Issue #54 fixtures、review/create/commit-binding/receipt/operator/
  architecture/verifier tests，并同步 exact consumer、documentation、status and
  leakage guards。
- AGENTS.md、CONTEXT.md、README.md、ADR/security/constraints/operations/template
  docs and project status generator：同步 evidence-only、capability wall、
  synthetic-only、locked-entry and no-real-operation contracts。

测试结果:
- TDD red/green：post-commit valid replacement、post-rediscovery source-byte drift
  before commit、verifier path ABA and dynamic-import guard regressions。
- Focused Issue #54：46 tests，OK。
- Affected Issue #35/#51/#53：186 tests，OK，1 skipped。
- Architecture/static/mechanical/status/leakage constraints：157 tests，OK。
- Full unittest discovery：2132 tests，OK，3 skipped。
- compileall、7 个 frontend JavaScript syntax checks and extension manifest JSON：
  OK。
- Read-only maintenance scan --fail-on-high：No cleanup findings detected。
- Standards final re-review：P1=0、P2=0；Spec final re-review：P1=0、P2=0、P3=0。

P3 records:
- Standards P3：verifier response fingerprint currently proves a distinct child
  but is not compared for exact equality with the launcher-known child PID；
  fixed child/process isolation satisfies Issue #54，后续 ticket 可收紧 provenance。

未完成事项:
- Versioned implementation and local review are complete。Explicit allowlist
  stage、commit、push、ready-for-review PR and remote CI are the remaining
  publication steps；merge remains unauthorized。

后续建议:
- Do not begin Issues #55 through #59 without separate authorization.
- Do not merge until the ready-for-review PR passes CI and human review.
```
