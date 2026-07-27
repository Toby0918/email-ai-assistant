---
last_update: 2026-07-26
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue #52 crash-safe journal and recovery classification task brief

## 1. 任务名称

```text
prove crash-safe journal and recovery classification
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

只针对 GitHub Issue #52 建立 synthetic、cross-platform、content-free 的
crash-safe journal、durability contract、restart inspection 和 recovery
classification。每个 fixed action 必须先有 durable INTENT，随后记录 exact
observed effect，最后进入 COMMITTED；reverse action 使用同一状态模型和同一
journal owner。

## 5. 非目标

- 不实现 Issue #53 through #59 的 real-host preflight、Windows ACL/filesystem
  primitives、repository/worktree、Runtime/data/artifact/Config、activation/
  recovery adapter 或 final composition。
- 不执行真实 preflight、evidence publication、migration、cutover、resume、
  rollback、incident recovery 或 cleanup。
- 不读取、探测、创建、移动、复制、删除、覆盖或修复真实 filesystem target、
  service、ACL、Git repository/worktree、Runtime、SQLite、browser profile、
  mailbox、provider、vault、credential、private store 或 private data。
- 不提供 default adapter、host path、CLI、HTTP route、script、workflow、
  scheduler、normal-runtime consumer 或 authorization issuer。
- 不签发、生成或 mint real-host authorization；只验证 Issue #51 已定义的外部
  canonical authorization values。
- 不修改或关闭 Issues #38/#39，不关闭 parent Spec #50，不开始 Issues #53–#59。
- 不 merge PR，不修改 `D:\Projects\financial_statement_analysis`。

## 6. 背景与依据

实施前实时门禁:

- Remote `master` 精确指向
  `ae753319aa01c52c12af8952fd2ea2d975e60c0b`。
- Issue #52 为 `OPEN`、`ready-for-agent`，唯一 blocker 是 #51。
- Issue #51 已由 merged PR #60 完成；merge commit 精确等于上述 master。
- Parent Spec #50 为 `OPEN`；#52 是其 P2 journal/state child。
- 独立 worktree 是
  `D:\Projects\email_ai_assistant_issue_52_crash_safe_journal`，
  branch 是 `codex/issue-52-crash-safe-journal`。
- 根工作区的 user-owned dirty state 和全部既有 worktrees 只读盘点并保持不变。

相关依据:

- GitHub Issues #50、#51 and #52
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md`
- `docs/security/project_container_cutover_contracts.md`
- tooling、architecture、linter、mechanical and CI constraints

## 7. 涉及范围

预计新增:

- `backend/cutover_journal/`
- `tests/cutover_journal_fixtures.py`
- `tests/test_cutover_journal_record_contract.py`
- `tests/test_cutover_journal_durability.py`
- `tests/test_cutover_journal_chain.py`
- `tests/test_cutover_journal_recovery.py`
- `tests/test_cutover_journal_crash_matrix.py`
- `tests/test_cutover_journal_architecture.py`
- 本 task brief

预计修改:

- `tests/test_cutover_contract_architecture.py`，只允许精确 journal consumer
- `AGENTS.md`、`CONTEXT.md`、`README.md`
- ADR、security、constraints、migration、structure、testing and template docs
- project-status generator、generator tests and generated status log

不修改 frontend、normal runtime、mailbox、provider、vault、private knowledge、
private evaluation、requirements、service scripts、root wrappers 或 workflows。

## 8. 技术方案

### 8.1 TDD public seams

主要行为测试通过四个预先确认的 public seams 观察:

1. `JournalRecordV1` 的 strict create/parse/canonical round-trip；
2. `DurableJournalStore` 的 exclusive owner、create-only append、complete-chain
   verification 和 exact synthetic durability protocol；
3. synthetic transaction 对 fixed step 的 forward/reverse
   INTENT -> observed effect -> COMMITTED 编排；
4. `inspect_restart(...)` 的 read-only classification，以及分别显式调用的
   resume/rollback seam。

测试只使用 exact in-memory synthetic journal/effect values，不接受 callback、
`Path`、handle 或 duck-typed adapter。Adversarial tests 可直接构造 hostile
snapshot/record，或 instrument store-private in-memory dictionary 来确定性触发
owner、append、permit first-mint/consume and restart races；这些 seam 不接受或
模拟 real-host capability。

### 8.2 Canonical journal records

`JournalRecordV1` 使用 strict canonical UTF-8 JSON。每条 create-only record
绑定:

- exact sequence and previous-record hash；
- record hash；
- fixed step、direction and event code；
- governing master、operation、Profile、forward authorization and pre-bound
  Recovery authorization fingerprints；
- current record authorization fingerprint；
- opaque before、expected-after and observed-effect fingerprints；
- fixed effect outcome。

Unknown/duplicate fields、non-canonical bytes、truncation、missing/duplicate
sequence、wrong previous hash、wrong binding、invalid transition or hash mismatch
fail closed。

### 8.3 Durability and ownership

生产 package 只定义 pathless exact synthetic persistence model，不实现或接受
任何真实 filesystem adapter。Windows and Linux 使用同一 logical append
contract，并由
fixed platform-specific file and namespace barrier codes 证明顺序:

1. create-only pending write；
2. pending file barrier；
3. no-replace final publication；
4. published record file barrier；
5. namespace barrier；
6. record-hash-bound stable reread acknowledgement。

只有完成 final namespace barrier and stable reread、再次 round-trip 验证的
current active INTENT 才能产生 non-copyable/non-serializable action permit。Permit
只持有 opaque token；store-private immutable issuance 绑定 exact current owner
lease、active durable INTENT、current durable journal head and stable-reread hash。
同一 issuance 的所有 permit view 共享一次由 active-token dictionary `pop`
原子取得的消费权；head advance、pending record、durable observed fact、owner
restart、copy、serialization、retarget 或 replay 均 fail closed。Historical intent
不能重新 mint。Synthetic medium operation gate 覆盖 append、restart、permit
mint/claim and effect mutation。任何 namespace-published current head 若只缺 final
stable reread，必须在 successor append 或 permit 前 exact reread 并重新验证完整
snapshot；INTENT、RESUME_BOUND、EFFECT_OBSERVED、COMMITTED 的 lost
acknowledgement 都遵守同一规则。Pending 和 unbarriered publication 永不授权
action。
一个 operation journal 只允许一个 exclusive owner；每次 claim 使用不同的
synthetic lease，stale store 不能使用或释放 recovered owner。Recovery owner 只有
在 claim 后重新读取并完整验证 chain 才能获得 usable lease。

### 8.4 Forward and reverse state machine

Forward step 使用 fixed order。每个 effect 前必须先取得 durable INTENT permit；
effect 后取得 exact observation，再 durable publish OBSERVED and COMMITTED。
Reverse step 只能从 COMMITTED/APPLIED forward records 按 LIFO 派生，并使用同一
journal、same step code、reverse direction and swapped before/after
observations。

如果 restart 看到 exact pre-action state，可在 valid unexpired forward
authorization 下 exact retry。看到 exact expected post-action state时，只能补写
OBSERVED/COMMITTED，绝不能 blind retry effect。Durable observed fact 是
authoritative；`NOT_APPLIED` 不能被 resume 改成 `APPLIED`，fresh resume
authorization 只能追加新的 `RESUME_BOUND`。Pending record 必须按 exact
direction/event/outcome 分类：INTENT 核对 pre-state；EFFECT_OBSERVED/COMMITTED
核对 record-bound observed fingerprint；RESUME_BOUND 核对 active durable fact
或 exact before/expected state。恢复只能 exact-complete 该 candidate，不能重复
effect；pending COMMITTED 发布后本次 action 立即结束，不能顺带执行下一步。
Forward authorization 已过期时，pre-bound valid Recovery authorization 可在
explicit rollback seam 中先 reconcile exact partial fact，再从
COMMITTED/APPLIED record 派生 reverse。Action seam 在任何 append/effect 前及
commit 前核对 exact Profile/master/operator、identity mapping、journal-bound
transition mapping and post-effect observation。Unknown observation、identity
drift 或 unsafe transition 一律 INCIDENT_STOP。

### 8.5 Restart inspection and public output

`inspect_restart(...)` 只读取 exact synthetic snapshot and observations。它不得 claim
mutation ownership、append journal、run forward/reverse action、start service 或
改变 synthetic state。Fixed classifications cover:

- `SAFE_ABORT`
- `RESUME_ALLOWED`
- `ROLLBACK_REQUIRED`
- `INCIDENT_STOP`
- `CUTOVER_SUCCEEDED`

Public operation result fields只允许 fixed status、receipt fingerprint、phase
and allowlisted integer counts。No path、command、exception、identity value or
free-form text is returned。

### 8.6 Capability isolation

`backend.cutover_journal` uses only pure standard-library value helpers,
exact in-memory synthetic state, and exact public Issue #51 contracts。It
accepts no callback or duck-typed adapter and imports no
`os`、`pathlib`、`tempfile`、`subprocess`、`sqlite3`、`ctypes`、`msvcrt`、
`fcntl`、network、environment、logging、dynamic import、ACL、Git、mailbox、
provider、vault、private-store or cleanup capability。No production consumer is
added。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

新增 internal synthetic Python journal/recovery seams only；无 HTTP API、CLI
或 real-host adapter。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱、真实主机、真实 filesystem target 或真实 SQLite。
- [x] 不自动发送、删除或归档邮件。
- [x] 不引入 frontend key、provider、mailbox、vault or private capability。
- [x] Journal、observations、results and failures remain content-free。
- [x] Tests use only synthetic opaque fingerprints and in-memory state。
- [x] No real-host authorization issuer or executable operator command exists。
- [x] Root worktree and existing worktrees remain preserved。

## 11. Prompt Injection 防护

Not applicable to AI input。All record、snapshot、adapter return and mapping
values are untrusted and must pass exact schemas；no field is interpreted as a
path、command、exception or free-form instruction。

## 12. 验收标准

1. DurableJournalStore publishes create-only canonical records with exact
   sequence/hash/binding/observation fields。
2. Forward and reverse actions satisfy durable INTENT、observed effect and
   COMMITTED ordering。
3. Pending and unbarriered records never authorize actions。
4. Windows/Linux durability protocols expose explicit file and namespace
   barrier acknowledgements behind one exact synthetic contract。
5. One operation journal has one owner；recovery ownership requires complete
   chain verification and a new lease；stale handles fail closed。
6. Restart inspection is read-only and causes no effect or journal write。
7. Resume requires unexpired matching forward authorization and exact
   pre/post observation。
8. Rollback uses the pre-bound Recovery authorization and only LIFO
   journal-derived COMMITTED/APPLIED reverse steps。
9. Corruption、unknown state、identity drift or ambiguity returns
   `INCIDENT_STOP` with no guessed action。
10. Every forward and reverse crash boundary、pending/truncation/sequence/hash/
    binding/ownership/exact-retry case has a public-seam test，including
    authoritative observed outcomes、pending direction、fresh resume rebind、
    Profile/identity/mapping substitution and single-use active-intent permit。
11. Public results contain only fixed status、receipt fingerprint、phase and
    allowlisted counts。
12. Docs distinguish SAFE_ABORT、ROLLBACK_REQUIRED、INCIDENT_STOP and
    CUTOVER_SUCCEEDED。
13. No real host or private capability is imported or invoked。

## 13. 测试计划

- TDD vertical slices: record -> durability/ownership -> transaction ->
  restart/recovery -> crash matrix -> architecture lock。
- Focused Issue #52 tests。
- Affected Issue #51 contract、architecture、static、mechanical、documentation、
  status-generator、leakage and maintenance regressions。
- Full `python -m unittest discover -s tests`。
- `python -m compileall -q backend scripts tests`。
- Frontend JavaScript syntax and manifest JSON checks。
- Repository leakage scan、maintenance scan and `git diff --check`。
- Standards/Spec parallel review from exact fixed point；P1/P2 repair and
  re-review。

## 14. 回滚方案

This slice changes only versioned source/tests/docs in the isolated worktree。
Before publication, rollback is removal or correction of the allowlisted Issue
#52 paths only。No real host state exists to reverse。After publication, normal
Git revert of the Issue #52 commit is sufficient；no cleanup or data rollback is
authorized。

## 15. 需要人工确认的问题

无。Issue #52 and parent #50 provide the exact bounded journal/state scope。Any
real persistence adapter、filesystem primitive、service/repository/runtime
mutation or Issue #53–#59 composition requires separate approval。

## 16. 执行前检查

- [x] 已完整阅读 `$implement` and `$tdd` skill rules。
- [x] 已阅读 `AGENTS.md`、`CONTEXT.md` and current project status。
- [x] 已阅读 tooling、architecture、linter、CI、ADR and migration rules。
- [x] 已实时核验 Issue #52、parent #50、dependency #51 and exact remote master。
- [x] 已建立 clean independent sibling worktree from the exact fixed point。
- [x] 已只读盘点并保护 root and all existing worktrees。
- [x] 已确认 TDD public seams and exact synthetic-only state。

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
- [x] No placement mode、host path or public override is added。
- [x] Journal and observation values are content-free and pathless。
- [x] Persistence/effect/observation state is exact and synthetic-only；no
  callback、Path、handle or production consumer exists。
- [x] Pending records and inspection cannot authorize a host action。
- [x] Tests never activate a Project Container or real host。

## 22. 执行后记录

```text
实际修改文件:
- `backend/cutover_journal/` 的 25 个 exact flat synthetic modules。
- `tests/cutover_journal_fixtures.py`、5 个 Issue #52 behavior test modules
  和 1 个 exact architecture/consumer guard module。
- `tests/test_cutover_contract_architecture.py` 的 sole-consumer allowlist。
- `tests/test_generate_project_status.py` 和
  `tests/test_mailbox_transport_constraints.py` 的 exact status/mechanical
  expectations。
- AGENTS/CONTEXT/README、ADR、security、tooling/architecture/linter/
  mechanical/CI constraints、migration/structure/testing/template/task-brief
  docs、status generator and generated status log。

测试结果:
- TDD 从 strict record、durability/ownership、chain、transaction、recovery、
  crash matrix 到 architecture 逐层记录 RED/GREEN；review repair 另记录了
  stale owner、namespace lost-ack、atomic first-mint/consume、authorizing-head
  stable、pending/terminal classification 和 max-count 的精确 RED/GREEN。
- Focused Issue #52: 77 tests, `OK`。
- Affected Issue #51 contracts: 44 tests, `OK`。
- Architecture、static、mechanical、status-generator and mailbox guards:
  121 tests, `OK`。
- Repository leakage and maintenance regressions: 17 tests, `OK`。
- Full `unittest discover -s tests` was executed three times with Python
  3.12.13。Each discovered 2020 tests and completed 2016 passes plus 3 skips；
  two runs hit the unchanged Windows
  `test_private_knowledge_locking` post-kill re-lock race，and one run passed
  that case but hit the unchanged server socket
  `ConnectionAbortedError` case。Both exact cases then passed together, 2/2；
  an exact discover-derived suite excluding only those asserted IDs passed the
  remaining 2018 tests，`OK (skipped=3)`。No implicated private-knowledge or
  server source/test file changed in Issue #52；GitHub Ubuntu CI remains the
  required clean full-suite gate。
- `python -m compileall -q backend scripts tests`: exit 0。
- All 10 frontend JavaScript files pass `node --check`；browser-extension
  manifest JSON parses successfully。
- Maintenance scan: `No cleanup findings detected.`。
- `git diff --check`: exit 0，only expected line-ending conversion warnings。
- Final Standards review: PASS，no P1/P2；25 package files are `<=300` lines
  and every package function is `<=50` lines。
- Final Spec review: PASS，no P1/P2/P3 across all Issue #52 acceptance criteria；
  additional read-only reverse namespace-lost-ack probes remain exactly once。
- Final adversarial state audit: PASS，no reproducible P1/P2 after 77 focused
  tests、50 rounds/300 concurrent-owner cases、forward/reverse lost-ack and
  max-count probes。
- Recorded P3 only from Standards: architecture/crash-matrix/durability/recovery
  test modules and some test/helper functions exceed advisory size guidance。
  This is test-maintainability debt；Issue #52 does not expand into test-file
  decomposition。

未完成事项:
- No local Issue #52 implementation or acceptance item remains。
- Local Windows full-suite evidence retains the two unrelated timing-flake
  disclosures above；their exact tests pass in isolation and are not modified
  in this slice。
- Publication、GitHub CI、human review and manual merge acceptance remain
  pending。
- Real host adapters and Issues #53 through #59 remain separately authorized；
  parent Spec #50 and Issues #38/#39 remain unchanged。

后续建议:
- Do not begin Issues #53 through #59 without separate authorization.
- Do not merge until the ready-for-review PR passes GitHub CI and human
  acceptance。
```
