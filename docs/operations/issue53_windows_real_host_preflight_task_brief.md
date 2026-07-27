---
last_update: 2026-07-26
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue #53 Windows real-host preflight task brief

## 1. 任务名称

```text
compose content-free Windows real-host preflight
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

只针对 GitHub Issue #53 建立 Windows read-only observation、
`CurrentTopologyPreflight`、`PreMutationGate`、
`RealHostBaselineCollector` 和 final-audit composition readiness。所有公开
receipt、result、stdout 和日志保持 content-free；现有九区
`ContainerAudit` policy core 保持不变，只通过七个窄 read-only callbacks
组合。

Windows 行为只在测试拥有的临时 sandbox 中执行。真实 operator command 在
Issue #39 之前继续锁定；缺少未来真实 `RealPreflightAuthorizationV1` 时只返回
`BLOCKED_NO_APPROVED_COMMAND`，并且 `TestSandboxAuthorizationV1` 不能进入
operator execution seam。

## 5. 非目标

- 不运行针对真实 Repository Root、Project Container、finance project 或其他
  真实 host target 的 preflight、baseline collection 或 final audit。
- 不修改既有 `backend.container_audit` 九区 policy、validation order 或
  pass/fail semantics。
- 不实现 Issue #54 through #59 的 evidence publication、ACL apply/filesystem
  mutation、repository/worktree transaction、Runtime/LocalData/CRX/Config
  publication、activation/recovery 或 final integration。
- 不签发、mint、伪造或储存 real-host authorization；测试授权只用于测试拥有的
  sandbox，且不能通过 real operator entry。
- 不停止、启动或探测真实 service；不 apply ACL，不 rename/move/copy/delete
  host objects，不创建或修改真实 worktree，不 build Runtime，不 copy database，
  不 publish artifact 或 Config。
- 不读取 mailbox、provider、vault、credential、private store、private data、
  OperatorPrivate content、SQLite rows、file content 或 environment secrets。
- 不改变 public HTTP、SQLite schema、frontend、prompt、AI JSON、provider
  routing、dependencies、scheduler、cleanup 或 workflow behavior。
- 不修改或关闭 Issues #38/#39，不关闭 parent Spec #50，不开始或修改
  Issues #54–#59，不 merge PR。
- 不触碰根工作区或任何既有 worktree 的文件状态。

## 6. 背景与依据

实施前实时门禁:

- Remote `master` 两次只读核对均精确指向
  `aa84c92639786d77673b9a94360210dc5d0b9287`。
- Issue #53 为 `OPEN`、`ready-for-agent`、无 assignee、无评论。
- Parent Spec #50 为 `OPEN`；#53 是 P3 Windows read-only preflight child。
- #53 唯一直接 blocker 是 #51；#51 已由 merged PR #60 完成。
- #52 已由 merged PR #61 完成，其 merge commit 就是本任务精确基线。
- #53 当前无未完成 blocker，并原生阻塞仍未开始的 #54 和 #55。
- Issue #38 与 Issue #39 均保持 `OPEN/ready-for-human`；#39 仍被 #38 阻塞，
  因而不存在本任务可使用的真实 Issue #39 execution authorization。
- 根工作区存在 user-owned dirty state，且有多个既有 worktree；全部保持不变。
- 本任务使用从精确基线创建的 clean sibling worktree 和
  `codex/issue-53-real-host-preflight` branch。

相关依据:

- GitHub Issues #50、#51、#52 and #53
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/issue34_content_free_container_audit_task_brief.md`
- `docs/operations/issue35_migration_evidence_package_task_brief.md`
- `docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md`
- `docs/operations/issue52_crash_safe_journal_recovery_task_brief.md`
- `docs/security/project_container_cutover_contracts.md`
- tooling、architecture、linter、mechanical、CI and testing constraints

## 7. 涉及范围

预计新增:

- `backend/real_host_preflight/` 的 Windows observation、portable contract、
  topology、fresh gate、baseline、audit bridge、contract bridge、composition
  和 locked operator modules
- `tests/real_host_preflight_fixtures.py`
- `tests/test_real_host_preflight_portable.py`
- `tests/test_real_host_preflight_topology.py`
- `tests/test_real_host_preflight_gate.py`
- `tests/test_real_host_preflight_baseline.py`
- `tests/test_real_host_preflight_windows.py`
- `tests/test_real_host_preflight_windows_composition.py`
- `tests/test_real_host_preflight_composition.py`
- `tests/test_real_host_preflight_leakage.py`
- `tests/test_real_host_preflight_architecture.py`
- 本 task brief

预计修改:

- exact `ContainerAudit`、migration-evidence `HostBaseline` and cutover-contract
  consumer allowlists，只增加 #53 的窄 bridge
- `AGENTS.md`、`CONTEXT.md`、`README.md`
- ADR、security、tooling/architecture/linter/mechanical/CI constraints
- migration、project-structure、testing and task-template operations docs
- project-status generator、generator tests and generated status log

不修改 frontend、normal runtime、mailbox、provider、vault、private knowledge、
private evaluation、requirements、service scripts、root wrappers、existing
ContainerAudit policy files 或 workflows。

## 8. 技术方案

### 8.1 TDD public seams

测试只通过以下已由 Issue #53 预先确认的 public seams 观察行为:

1. Windows read-only object observation boundary；
2. `CurrentTopologyPreflight`；
3. `PreMutationGate`；
4. `RealHostBaselineCollector`；
5. final-audit composition readiness；
6. default-locked real operator entry。

测试不 mock package internals。Windows API、Git observation、ACL observation
和既有 `ContainerAudit` 都位于 system boundary；只允许通过 exact narrow
callbacks 或 test-owned temporary filesystem state 注入。每个 vertical slice
遵循 one public failing test -> minimal implementation -> focused GREEN。

### 8.2 Windows read-only observation

Windows object observation使用 opened handles，而不是只信 path strings。
每个受控 object 绑定:

- volume identity；
- 128-bit file ID；
- exact object type；
- parent identity；
- normalized-name fingerprint；
- file attributes and reparse tag metadata。

受控 path components 使用 no-follow-reparse open。Alias、unexpected
filesystem/volume type、unreadable state、missing evidence、parent/leaf
replacement、normalized-name drift、reparse insertion 或 identity drift 均映射
到固定 fail-closed status；native path 和 exception text 不进入 public value。

生产代码不提供 write、rename、delete、ACL apply、service、Git mutation、
worktree mutation 或 arbitrary command capability。

### 8.3 Current topology and freshness

`CurrentTopologyPreflight` 收集两次完整 observations。只有 exact equal、
complete、content-not-observed、non-reparse、expected-volume and relationship
checks 全部通过时，才产生
`CurrentTopologyPreflightReceiptV1`。Receipt 使用既有 canonical
`ReceiptEnvelopeV1` preflight family，绑定 Profile、authorization/policy、
operation、master、observation fingerprint、bounded validity and counts。

`PreMutationGate` 在短 freshness window 内重新执行 exact source、
target-parent、target-absence、reparse、Git、ACL and volume checks。它绑定 fresh
nonce、one operation fingerprint、prior accepted topology observation and
single-use state，产生 `PreMutationGateReceiptV1`。Stale、replayed、different
nonce、target appearance、parent/source replacement 或任何 observation drift
固定失败。

### 8.4 Real HostBaseline projection

`RealHostBaselineCollector` 分开收集 source-root、projects parent、finance
project、volume、operator-SID and ACL evidence。Parent and finance observations
不得合并或互相代替。Canonical aggregate 绑定:

- separate source-root、parent and finance fingerprints；
- volume and filesystem evidence；
- operator-SID fingerprint；
- ACL fingerprints and aggregate count；
- completeness and `content_observed=false`。

Collector 只把 canonical aggregate projection 写入既有
`backend.migration_evidence.HostBaseline` value；它不改变 Issue #35 package
policy，也不读取 path/content/SID/SDDL/account/Git name。

### 8.5 Existing ContainerAudit composition

Existing `backend.container_audit` source and its final nine-zone policy remain
unchanged。#53 仅增加一个 exact bridge，把七个 caller-bound real read-only
metadata callbacks 组合成既有 `ContainerAuditAdapters`。Core 不获得
`ctypes`、path、filesystem、ACL、Git、SQLite 或 host imports。

`FinalAuditCompositionReadyReceiptV1` 只证明 exact policy、seven callbacks and
composition contract 已准备好；它不调用 current pre-cutover final audit，也不把
readiness 表述为 final layout passed。

### 8.6 Test sandbox and operator lock

Windows integration仅可由 exact `TestSandboxAuthorizationV1` 和测试拥有的
temporary scope 构造。Scope guard 拒绝任何 original/resolved path escape、
outside-root parent 或 authorization mismatch。Linux 执行 portable contract
tests only，不宣称 NTFS、Windows file ID 或 Windows ACL evidence。

Real operator entry不接受 path、callback、command 或 test authorization。缺少
未来 Issue #39 提供的真实 approved command 时固定返回
`BLOCKED_NO_APPROVED_COMMAND`，且 executed count 恒为零。

### 8.7 Content-free public boundary

Public receipts/results/logging capture只允许 fixed enum、opaque SHA-256
fingerprints and allowlisted bounded counts。Raw path、SID、SDDL、account、Git
name/ref、file content、database content、command、native error and exception
text 均被拒绝或丢弃。Production package不使用 `print()`，不格式化 callback 或
Windows exception。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

新增 internal Python read-only preflight package and exact bridge seams only；
无 HTTP API、CLI 或 executable Issue #39 command。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱、真实 Project Container、真实 service 或 private data。
- [x] 不自动发送、删除或归档邮件。
- [x] 不引入 frontend key、provider、mailbox、vault or private capability。
- [x] Windows integration 只在 test-owned temporary sandbox 中执行。
- [x] Parent and finance observations remain separate and content-free。
- [x] Receipts、results、stdout and logs expose no raw path、SID、SDDL、Git
  name or exception text。
- [x] Existing ContainerAudit policy remains unchanged。
- [x] No real-host authorization issuer or executable operator command exists。
- [x] Root worktree and all existing worktrees remain preserved。

## 11. Prompt Injection 防护

Not applicable to AI input。All path bindings、Windows metadata、callback
returns、authorization、Profile and receipt values are untrusted and must pass
exact types and closed validation；no string is interpreted as a command,
exception, script or free-form instruction。

## 12. 验收标准

1. Windows observations bind opened-handle volume、128-bit file ID、object
   type、parent identity、normalized-name fingerprint and reparse metadata。
2. Every controlled path component is opened no-follow-reparse；alias、
   unexpected volume/filesystem、unreadable or drifting state fails closed。
3. `CurrentTopologyPreflight` requires two complete identical observations and
   returns a content-free `CurrentTopologyPreflightReceiptV1`。
4. `PreMutationGateReceiptV1` is fresh、nonce-bound、short-lived、
   single-operation and repeats exact source/target-parent/target-absence/
   reparse/Git/ACL/volume checks。
5. Existing final nine-zone `ContainerAudit` policy is unchanged and receives
   exactly seven callbacks through the #53 bridge。
6. `FinalAuditCompositionReadyReceiptV1` proves composition readiness without
   claiming final-layout pass。
7. `RealHostBaselineCollector` preserves separate source/parent/finance/
   volume/operator/ACL evidence and projects canonical `HostBaseline`。
8. Public outputs contain no path、SID、SDDL、account、Git name/ref、command、
   exception or content。
9. Production composition owns no service-control、ACL apply、rename、
   worktree mutation、Runtime build、database copy、artifact、Config、
   provider、mailbox、vault or private-data capability。
10. Real operator entry remains `BLOCKED_NO_APPROVED_COMMAND` and rejects
    test authorization。
11. Windows sandbox tests cover file-ID stability、parent replacement、target
    appearance、reparse insertion、volume mismatch、two-pass drift and leakage。
12. Linux validates portable contracts only and makes no Windows/NTFS/ACL
    claim。
13. Task brief、operations、security、constraints and status documentation are
    synchronized。
14. No real project path、service、credential、mailbox、provider、vault、
    private data、ACL、worktree、Runtime or production database is accessed or
    changed。

## 13. 测试计划

- TDD vertical slices: portable contracts -> Windows handle observation ->
  topology two-pass -> fresh pre-mutation gate -> HostBaseline -> final-audit
  readiness -> operator/architecture lock。
- Windows focused sandbox tests，全部 target 位于 caller-owned temporary root。
- Linux portable-contract suite，不运行 Windows host observation。
- Focused Issue #53 tests。
- Affected ContainerAudit、migration evidence、Issue #51 contracts、
  architecture、static、mechanical、documentation、status-generator、leakage
  and maintenance regressions。
- Full `python -m unittest discover -s tests`。
- `python -m compileall -q backend scripts tests`。
- Frontend JavaScript syntax and manifest JSON checks。
- Repository leakage scan、maintenance scan、`git diff --check` and staged
  allowlist validation。
- Standards/Spec parallel review from exact fixed point；P1/P2 repair and
  re-review；P3 record only。
- Ready-for-review PR CI must pass before handoff。

## 14. 回滚方案

This slice changes only versioned source/tests/docs in the isolated worktree。
Before publication, rollback is removal or correction of the allowlisted Issue
#53 paths only。No real host state exists to reverse。After publication, normal
Git revert of the Issue #53 commit is sufficient；no host cleanup or data
rollback is authorized。

## 15. 需要人工确认的问题

无。Issue #53 and parent #50 provide the bounded read-only composition scope。
Any real operator command、authorization issuance、evidence publication、
mutation、cutover or Issue #54–#59 work requires separate approval。

## 16. 执行前检查

- [x] 已完整阅读 `$implement`、`$tdd` and `$code-review` skill rules。
- [x] 已阅读 `AGENTS.md`、`CONTEXT.md` and current project status。
- [x] 已阅读 tooling、architecture、linter、mechanical、CI、ADR、security、
  migration and testing rules。
- [x] 已实时核验 Issue #53、parent #50、dependency #51、#52 baseline and exact
  remote master。
- [x] 已建立 clean independent sibling worktree from the exact fixed point。
- [x] 已只读盘点并保护 root and all existing worktrees。
- [x] 已确认 TDD public seams、Windows sandbox and Linux portable boundary。

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

- [x] Managed topology remains exactly `email_ai_assistant/main`。
- [x] No placement mode、public path override or operator command is added。
- [x] Windows observations are read-only and content-free。
- [x] Existing ContainerAudit policy remains unchanged；only exact seven
  callbacks are composed by the new bridge。
- [x] HostBaseline projection does not widen Issue #35 review/create policy。
- [x] Real operator entry remains locked and test authorization cannot pass。
- [x] Tests never run against a real Project Container or real host target。
- [x] Issues #54–#59、#38/#39 and parent Spec #50 remain unchanged。

## 22. 执行后记录

```text
实际修改文件:
- `backend/real_host_preflight/` 的 28 个 exact flat modules。
- `tests/real_host_preflight_fixtures.py` 和 9 个
  `tests/test_real_host_preflight_*.py` modules。
- `tests/test_architecture_constraints.py` 与
  `tests/test_cutover_contract_architecture.py` 的 exact bridge consumer
  allowlists。
- `scripts/generate_project_status.py`、
  `tests/test_generate_project_status.py` 和
  `tests/test_mailbox_transport_constraints.py` 的 status/mechanical
  expectations。
- AGENTS/CONTEXT/README、ADR、security、tooling/architecture/linter/
  mechanical/CI constraints、migration/structure/testing/template/task-brief
  docs 和 generated project status log。

测试结果:
- TDD 从 portable observations、Windows handle observation、two-pass
  topology、fresh gate、baseline、composition、operator lock、architecture
  和 leakage 逐层记录 RED/GREEN；review hardening 另记录了 canonical ACL
  count、distinct topology identities、attribute/reparse consistency、
  exact evidence reconstruction、Profile role binding、receipt single-claim、
  module-owned gate state、root/marker permit、hard-link alias rejection 和
  final-audit reader identity 的 RED/GREEN。
- Focused Issue #53: 52 tests，`OK`。
- Affected ContainerAudit、migration-evidence、Issue #51 contracts、
  architecture/static/mechanical/status/transport/leakage/maintenance:
  253 tests，`OK (skipped=1)`。
- Full `python -B -m unittest discover -s tests`: 2073 tests，
  `OK (skipped=3)` with Python 3.12.13。
- `python -B -m compileall -q backend scripts tests`: exit 0。
- All frontend JavaScript files pass `node --check`; browser-extension
  manifest JSON parses successfully。
- Repository leakage scan: exit 0。Maintenance scan:
  `No cleanup findings detected.`。
- `git diff --check`: exit 0，only expected line-ending conversion warnings。
- Initial Standards/Spec and adversarial review P1/P2 findings were repaired
  with regression tests；formal re-review and ready-for-review PR CI remain
  pending at this checkpoint。

P3 records（本 Issue 不扩围）:
- Freshness still consumes a caller-supplied epoch；future Issue #39 must bind
  that input to its separately approved trusted clock seam。
- The baseline operator-SID fingerprint remains a separate observation from
  the Profile operator fingerprint；a future ticket must explicitly define a
  same-source relation before relying on one。
- The three closed receipt builders/views retain some duplicated schema
  structure；deduplication is deferred because it is not required by #53。

未完成事项:
- No local Issue #53 implementation or automated acceptance item remains。
- Standards/Spec review、publication、GitHub CI and human acceptance remain
  pending。
- No real preflight, final-layout audit, mutation or Issue #54–#59 work is
  authorized or performed。

后续建议:
- Do not begin Issues #54 through #59 without separate authorization.
- Do not merge until the ready-for-review PR passes GitHub CI and human review.
```
