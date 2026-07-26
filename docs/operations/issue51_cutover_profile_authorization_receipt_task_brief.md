---
last_update: 2026-07-26
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue #51 Cutover Profile, authorization, and receipt contracts task brief

## 1. 任务名称

```text
establish locked Cutover Profile, authorization, and receipt contracts
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

只针对 GitHub Issue #51 建立纯 Python、跨平台、content-free 的 Project
Container cutover contract layer。该层接受一个 immutable
`CutoverProfileV1`，验证 distinct phase-specific authorization，并产生或解析
deterministic canonical `ReceiptEnvelopeV1`；它不得获得或调用任何真实主机能力。

## 5. 非目标

- 不实现 Issue #52 through #59 的 journal、preflight、Windows adapter、ACL、
  repository/worktree、Runtime、SQLite、artifact、Config、activation、rollback
  或 composition root。
- 不执行真实 preflight、evidence publication、migration、cutover、resume、
  rollback、incident recovery 或 cleanup。
- 不读取、探测、移动、复制、创建、删除、覆盖或修复真实 Runtime、SQLite、
  ACL、repository、worktree、browser profile、mailbox、provider、vault、
  credential、private store 或 private data。
- 不签发、生成或 mint real-host authorization；real authorization contracts
  只验证外部提供的 canonical values。
- 不改变 public HTTP、SQLite schema、frontend、prompt、AI JSON、provider routing、
  dependencies、scheduler、workflow 或 cleanup behavior。
- 不修改或关闭 Issues #38/#39，不关闭 parent Spec #50，不开始 Issues #52–#59。
- 不 merge PR，不修改 `D:\Projects\financial_statement_analysis`。

## 6. 背景与依据

实施前实时门禁:

- Remote `master` 精确指向
  `0c99d89195162a766d58c06baf2af2a81fede796`。
- Issue #51 为 `OPEN`、`ready-for-agent`，原生 `blocked_by=0`。
- Parent Spec #50 为 `OPEN`；#51 是其 P1 contracts child。
- #51 原生阻塞 #52 与 #53；本任务不会开始或修改它们。
- Issues #34 through #37 已关闭并作为 prior synthetic contract evidence。
- Issue #38 仍为 `OPEN/ready-for-human`；Issue #39 仍为
  `OPEN/ready-for-human` 并被 #38 阻塞。
- 未发现现有 Issue #51 PR。
- 独立 worktree 是
  `D:\Projects\email_ai_assistant_issue_51_cutover_contracts`，
  branch 是 `codex/issue-51-cutover-contracts`。
- 根工作区的 user-owned dirty state 和全部既有 worktrees 只读盘点并保持不变。

相关依据:

- GitHub Issues #50 and #51
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/issue34_content_free_container_audit_task_brief.md`
- `docs/operations/issue35_migration_evidence_package_task_brief.md`
- `docs/operations/issue36_reparenting_rehearsal_task_brief.md`
- `docs/operations/issue37_managed_runtime_localdata_rehearsal_task_brief.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`

## 7. 涉及范围

预计新增:

- `backend/cutover_contracts/`
- `tests/cutover_contract_fixtures.py`
- `tests/test_cutover_profile_contract.py`
- `tests/test_cutover_authorization_contract.py`
- `tests/test_cutover_receipt_contract.py`
- `tests/test_cutover_contract_architecture.py`
- `docs/security/project_container_cutover_contracts.md`
- 本 task brief

预计修改:

- `AGENTS.md`
- `CONTEXT.md`
- `README.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/project_structure.md`
- `docs/operations/testing_checklist.md`
- `docs/templates/agent_task_brief_template.md`
- tooling、architecture、linter and mechanical constraints
- project-status generator、generator tests and generated status log

不修改 frontend、normal runtime、mailbox、provider、vault、private knowledge、
private evaluation、requirements、service scripts、root wrappers 或 workflows。

## 8. 技术方案

### 8.1 TDD public seams

测试只通过四个预先确认的 public seams 观察行为:

1. `CutoverProfileV1` 的 pure create/parse/canonical round-trip；
2. distinct real authorization value parsing and
   `validate_real_host_authorization(...)`；
3. `ReceiptEnvelopeV1` 的 pure create/parse/canonical round-trip；
4. `default_operator_entry()` 的 fixed pre-Issue-#39 block。

测试不 mock package internals，不查询数据库或 filesystem side channel。

### 8.2 Locked Cutover Profile

`CutoverProfileV1` 只接受 closed content-free mappings。它绑定:

- exact governing master commit and operator fingerprint；
- fixed role and evidence-role fingerprints；
- reviewed Git selection fingerprints；
- exact eleven-worktree roster with eight embedded and three external roles；
- pinned Runtime inputs；
- create-only SQLite and CRX inputs；
- deterministic non-secret Config policy；
- fixed-role ACL policy；
- maintenance-window and no-cleanup rules；
- complete rollback-role fingerprints。

Public input does not contain `Path`、drive、directory、SID、SDDL、Git ref/name、
command、exception、database row、message or free text。Profile canonical bytes
and SHA-256 identity are deterministic。

### 8.3 Authorization separation

The following are exact distinct types:

- `RealPreflightAuthorizationV1`
- `EvidencePublicationAuthorizationV1`
- `CutoverExecutionAuthorizationV1`
- `RecoveryAuthorizationV1`

Each type validates exact operation、operation fingerprint、profile、master、
operator、phase、issued/not-before/expiry values and externally supplied
authorization fingerprint。The package has no real-authorization
`create`/`issue`/`mint`/random/time/secret/signing function。

`TestSandboxAuthorizationV1` is in-memory and synthetic-only。The real-host
validator uses exact type checks, so test authorization、receipt、mapping or
duck-typed objects cannot become real-host authority。

Missing、not-yet-valid、expired、wrong-profile、wrong-master、wrong-operation、
wrong-operator、wrong-phase and wrong-type cases return fixed allowlisted codes
with aggregate-only accepted/rejected counts。

### 8.4 Canonical content-free receipts

`ReceiptEnvelopeV1` uses strict UTF-8 canonical JSON:

- sorted keys、compact separators and `allow_nan=False`；
- duplicate keys、unknown fields、unknown enum values and non-canonical bytes
  fail closed；
- exact type/status compatibility；
- exact operation/profile/master/authorization/producer/subject bindings；
- bounded opaque input and observation fingerprints；
- exact per-type count keys with non-boolean bounded integers；
- closed per-type detail schemas；
- bounded validity and a verified SHA-256 receipt fingerprint。

Receipt status families are closed for preflight、evidence、ACL、repository、
worktree、Runtime、database、artifact、Config、activation、rollback and
incident stop。No receipt parser or validator is accepted as authorization。

### 8.5 Locked operator entry

`default_operator_entry()` accepts no path、adapter、callback、command or
authorization and always returns `BLOCKED_NO_APPROVED_COMMAND` with one blocked
aggregate count。This contract remains locked until a separately approved Issue
#39 implementation。

### 8.6 Capability isolation

The package remains pure value/JSON/hash code。It imports no `pathlib`、`os`、
`subprocess`、`sqlite3`、filesystem、network、process、ACL、Git、browser、
mailbox、provider、vault、private-store、environment、scheduler、logging or
dynamic import capability。No production consumer is added in this slice。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

新增 internal Python contract package only；无 HTTP API 或 CLI 变化。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱、真实主机、真实 SQLite 或真实 private data。
- [x] 不自动发送、删除或归档邮件。
- [x] 不引入 frontend key 或 provider capability。
- [x] Profile、authorization、receipt and failures remain content-free。
- [x] Tests use only synthetic opaque fingerprints and fixed enum values。
- [x] No real-host authorization issuer or executable operator command exists。
- [x] Root worktree and existing worktrees remain preserved。

## 11. Prompt Injection 防护

Not applicable to AI input。All JSON and mapping input is untrusted and must pass
exact schemas；no field is interpreted as a command, path, exception or free-form
instruction。

## 12. 验收标准

1. `CutoverProfileV1` satisfies every binding in Issue #51 and has no arbitrary
   host-path field。
2. Four real authorization types are distinct, operation-bound and phase-bound。
3. Every authorization mismatch returns its fixed allowlisted code。
4. No prerequisite function mints real authorization；default entry is blocked。
5. `ReceiptEnvelopeV1` is canonical, deterministic, duplicate/unknown rejecting
   and fingerprint-bound。
6. Receipt details、counts、status and type are exact closed schemas。
7. All twelve required status families are represented。
8. Receipts and test authorization cannot pass real-host validation。
9. Cross-platform tests cover deterministic fingerprints、phase separation、
   hostile parsing and content-free output。
10. Task brief、domain、security、constraints and status documentation are
    synchronized。
11. No real adapter or private/host capability is imported or invoked。

## 13. 测试计划

- TDD vertical slices: profile -> authorization -> receipt -> architecture lock。
- Focused Issue #51 tests。
- Affected Project Container、architecture、static、mechanical、documentation
  and status-generator regressions。
- Full `python -m unittest discover -s tests`。
- `python -m compileall -q backend scripts tests`。
- Frontend JavaScript syntax and manifest JSON checks。
- Repository leakage scan、maintenance scan and `git diff --check`。
- Standards/Spec parallel review from exact fixed point；P1/P2 repair and
  re-review。

## 14. 回滚方案

This slice changes only versioned source/tests/docs in the isolated worktree。
Before publication, rollback is removal or correction of the allowlisted Issue
#51 paths only。No real host state exists to reverse。After publication, normal
Git revert of the Issue #51 commit is sufficient；no cleanup or data rollback is
authorized。

## 15. 需要人工确认的问题

无。Issue #51 and parent #50 provide the exact bounded contract scope。Any future
host adapter、authorization issuance、command、journal、preflight or cutover
requires a separate approved Issue。

## 16. 执行前检查

- [x] 已完整阅读 `$implement`、`$tdd` and `$code-review` skill rules。
- [x] 已阅读 `AGENTS.md`、`CONTEXT.md` and current project status。
- [x] 已阅读 tooling、architecture、linter、ADR and migration rules。
- [x] 已实时核验 Issue #51、parent #50、dependencies and exact remote master。
- [x] 已建立 clean independent sibling worktree from the exact fixed point。
- [x] 已只读盘点并保护 root and all existing worktrees。
- [x] 已确认 TDD public seams and synthetic-only fixtures。

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
- [x] No placement mode or public path override is added。
- [x] All Issue #51 values are pathless and content-free。
- [x] No existing audit、evidence、rehearsal or runtime package is consumed。
- [x] Tests never activate a Project Container or real host。

## 22. 执行后记录

```text
实际修改文件:
- `backend/cutover_contracts/`
- `tests/cutover_contract_fixtures.py`
- `tests/test_cutover_profile_contract.py`
- `tests/test_cutover_authorization_contract.py`
- `tests/test_cutover_receipt_contract.py`
- `tests/test_cutover_contract_architecture.py`
- exact architecture、static、mechanical、status-generator and transport guards
- AGENTS/CONTEXT/README/ADR/constraints/operations/template/status/security docs

测试结果:
- TDD profile、authorization、receipt and architecture slices each recorded a
  failing public-seam test before implementation.
- Focused Issue #51 after review repairs: 44 tests, `OK`.
- Affected Project Container、architecture、status、documentation、leakage and
  maintenance regression after review repairs: 255 tests, `OK`.
- Full unittest with Python 3.12.13 and exact locked dependencies: 1942 tests,
  `OK (skipped=3)`.
- `python -m compileall -q backend scripts tests`: exit 0.
- 10 JavaScript syntax checks and one browser-extension manifest JSON check:
  exit 0.
- Maintenance scan: `No cleanup findings detected.`
- `git diff --check`: exit 0.
- Independent edge audit found four P2 groups: unchecked nominal-object
  construction/integrity, unhashable receipt type, consumer/relative-import
  bypasses, and dotted-module/stdin capability bypasses. Each received a
  focused RED regression, a bounded fix, and successful re-review; no P1/P2
  remains.
- Initial Standards/Spec fixed-point review found two additional P2 groups:
  hostile mapping/cyclic/canonical error escape and equivalent capability-guard
  bypasses. Exact-type-before-comparison parsing, fixed per-contract errors,
  bounded integrity failure, recursive package closure, forbidden-load checks,
  package-wide issuer checks and dynamic-consumer checks now have RED/GREEN
  regressions.
- The first Standards closing review found one remaining P2 equivalence group:
  `breakpoint`/`delattr`/`setattr` aliases and imported or rebound dynamic-import
  call aliases. Eight failing subcases recorded RED before the bounded guard and
  documentation fix. Final Standards and Spec closing reviews at `e215ef1`
  report zero P1/P2; Spec confirms all eleven Issue #51 acceptance criteria.
- Recorded P3 only: receipt status/count/detail semantic relationships are left
  to future real consumers; internal authorization/receipt schema registries
  remain mutable; authorization/receipt/architecture test files exceed the
  advisory 300-line size; and Profile/Receipt frozen projection helpers remain
  duplicated. None grants a current host capability or changes Issue #51
  acceptance.

未完成事项:
- No local Issue #51 implementation or acceptance item remains.
- Publication、GitHub CI and manual merge acceptance remain pending.
- Real host adapters、authorization issuance and Issues #52 through #59 remain
  separately authorized future work.

后续建议:
- Do not begin Issues #52 through #59 without separate authorization.
- Do not merge until the ready-for-review PR passes GitHub CI and human review.
```
