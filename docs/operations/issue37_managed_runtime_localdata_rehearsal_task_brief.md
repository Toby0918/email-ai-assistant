---
last_update: 2026-07-26
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue #37 managed runtime and LocalData activation rehearsal task brief

## 1. 任务名称

```text
rehearse managed runtime and LocalData activation
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

只针对 temporary synthetic sources and destinations 演练 Managed runtime、
LocalData、RuntimeTemp、Logs、Artifacts、Config 和 provider-disabled service
activation。演练必须通过 injected runtime、filesystem、database、lifecycle 和
probe adapters 证明 pinned runtime、locked dependency rebuild、stopped-service
SQLite publication、reviewed artifact publication 和 loopback persisted analysis
满足 Issue #37 的 fail-closed 边界。

## 5. 非目标

- 不构建、移动、复制、激活或修复真实 runtime、`.venv`、SQLite、extension
  artifact、worktree、branch、directory 或 service。
- 不生成真实 migration evidence package，不运行真实 ContainerAudit。
- 不访问 network other than the required synthetic loopback service、mailbox、
  provider、vault、private store、credentials、ignored `.env`、signing material
  或真实私有数据。
- 不执行 network install、dependency upgrade 或 requirements change。
- 不增加 CLI、public HTTP field、public SQLite schema、prompt、AI JSON、
  browser permission、scheduler、workflow 或 default host adapter。
- 不删除、覆盖、移动、修复、prune 或 cleanup 任何真实或 synthetic source。
- 不开始 Issues #38 through #40，不自动 merge，不关闭 parent Spec #29。

## 6. 背景与依据

实施前实时门禁：

- PR #48 is `MERGED`，merge commit 为
  `23646f5761a2dc40c53810098fac89e7c1b24f05`。
- Issues #32、#34 和 #36 均为 `CLOSED/completed`。
- Issue #37 为 `OPEN`，唯一 label 为 `ready-for-agent`。
- Issue #37 的原生 blockers 只有 #32 和 #34，均已关闭。
- Remote `master` 精确指向 `23646f5761a2dc40c53810098fac89e7c1b24f05`。
- 独立 worktree 为
  `D:\Projects\email_ai_assistant_issue_37_runtime_localdata_rehearsal`，
  branch 为 `codex/issue-37-runtime-localdata-rehearsal`。
- 真实根工作区、local branches、existing worktrees、runtime、`.venv` 和
  database 已只读盘点并保持 user-owned preserved state。

相关依据：

- GitHub Issues #29 and #37
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/issue32_managed_container_mode_task_brief.md`
- `docs/operations/issue34_content_free_container_audit_task_brief.md`
- `docs/operations/issue36_reparenting_rehearsal_task_brief.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`

## 7. 涉及范围

预计新增：

- `backend/runtime_activation_rehearsal/`
- `tests/runtime_activation_rehearsal_fixtures.py`
- `tests/test_runtime_activation_rehearsal_*.py`
- 本 task brief

预计修改：

- `scripts/manage_local_service.py`
- `tests/test_manage_local_service.py`
- architecture/static/mechanical guards
- `AGENTS.md`
- `CONTEXT.md`
- ADR 0009 and the Project Container migration brief
- project structure, testing checklist and task-brief template
- project status generator, its tests and generated status log

不修改 frontend、provider、mailbox、private-store、public API/schema、requirements
或 `.github/workflows/cleanup_agent.yml`。

## 8. 技术方案

### 8.1 唯一 public seam

```python
rehearse_managed_runtime_activation(
    *,
    adapters: ManagedActivationAdapters,
) -> ManagedActivationResult
```

`ManagedActivationAdapters` 精确包含五个无默认、target-bound adapters：

- `runtime`
- `filesystem`
- `database`
- `lifecycle`
- `probe`

Public seam 不接受 `Path`、source、target、Repository Root、Project Container、
cwd、environment、reader factory、CLI argument 或 default host adapter。Public
result 只包含 fixed completed/failed status 和 aggregate counts，不返回 path、
identity、hash、version、exception、content 或 diagnostic detail。

### 8.2 Trusted policy and adapter evidence

Trusted policy 固定：

- Python `3.12.13`
- SQLite `3.50.4`
- exact `requirements.txt` dependency pins
- exact Managed zone roles
- both provider routes disabled
- one loopback persisted synthetic analysis

Adapter evidence 使用 exact frozen/slotted/repr-redacted values。编排器要求两次
stable identity observation并跨 adapters 核对 opaque identities、SHA-256、
integrity、sidecars、aggregate counts、provider state 和 fixed call order。任一
unknown type、exception、drift、malformed evidence 或 mismatch 返回 fixed failure。

### 8.3 Runtime and Windows venv

Runtime adapter 只能表示 create-only fixed-runtime publication 和
`rebuild_venv_from_lock`。成功证据必须证明：

- runtime and venv targets were absent and created without overwrite；
- Python/SQLite probe 精确匹配 pinned versions；
- installed dependency pins 精确匹配 locked requirements；
- requirements identity/hash 在 rebuild 前后稳定；
- no network install or dependency upgrade；
- legacy venv was not read, copied, moved, removed or used as rebuild source；
- runtime source and legacy venv remain present and identity-stable。

### 8.4 Managed layout and non-secret state

Filesystem evidence 必须绑定 exact synthetic
`email_ai_assistant/main` relationship and approved ordinary zones。Attachment
temporary state、log、PID and Config roles 必须分别绑定 `RuntimeTemp`、`Logs`
和 `Config`。Config keys 只有：

- `EMAIL_AGENT_LOG_LEVEL`
- `EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS`

所有 reparse、alias、identity drift、missing zone、wrong role 或 observed secret
state fail closed。

### 8.5 Lifecycle stop and SQLite publication

现有 lifecycle manager 的 stop path 必须只在 loopback health 明确变为 unavailable
后删除 PID 并返回 `stopped`。Stop timeout must return nonzero `unknown` and retain
PID。Rehearsal 在 lifecycle stop result 之外，还要求 independent probe evidence；
两者必须回显 code-fixed `pre_publication` phase 后内部才创建 stopped gate，
database adapter 在 gate 前不得被调用。

SQLite success requires：

- stable source identity before and after publication；
- source and destination are distinct objects；
- destination target was absent and publication was create-only；
- exact size and SHA-256 equality immediately after publication；
- `PRAGMA integrity_check` success and complete expected schema；
- no `-wal`、`-shm` or journal sidecar after confirmed stop；
- equal pre-activation aggregate counts；
- source remains unchanged after the persisted synthetic analysis；
- destination aggregate count increases by exactly one。

Existing target、race、reparse、sidecar、integrity、hash、schema 或 count mismatch
fail closed without overwrite or source cleanup。

### 8.6 Reviewed browser-extension artifact

Probe adapter supplies one independent reviewed synthetic CRX identity and
SHA-256。Filesystem adapter may publish only that file create-only into the
approved artifact role after source/review equality。Destination identity and
hash are independently rechecked。Signing material has no adapter path, read,
copy or enumeration capability；tests use a signing canary and require zero reads。

### 8.7 Provider-disabled activation

Lifecycle start evidence must bind the same service identity and echo one fresh
activation nonce bound to the validated initial stopped gate；health and
analysis evidence must echo that token while proving both provider routes
disabled, no provider key, no private knowledge and exact Managed writable
roles。Probe evidence must then prove：

1. healthy literal loopback service；
2. exactly one user-confirmed synthetic analysis；
3. `rule_fallback` route；
4. positive persisted ID；
5. one-row destination aggregate increase。

Service is stopped again before final database/source preservation checks。The
final lifecycle/probe pair must echo the same activation token under
`post_activation`, bind the same service identity, and use a fresh stop token；
initial or older stopped evidence replay fails closed。A health or analysis
failure triggers best-effort synthetic stop and fixed failure；it never deletes
or rolls back source or published targets。

## 9. 数据结构或接口变化

### 数据库变化

无 public schema change。Only temporary synthetic SQLite fixtures are created。

### API 变化

无 HTTP API change。新增一个 synthetic-only internal Python seam。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实 mailbox、SQLite、runtime、artifact、credential 或 private data。
- [x] 不自动发送、删除、归档、移动、转发或扫描邮件。
- [x] Provider、mailbox、vault、private-store and credential access remain absent。
- [x] Tests only use temporary synthetic state and literal loopback。
- [x] Signing material has no read/copy capability。
- [x] No network install, dependency upgrade or real `.venv` modification。
- [x] Public results are content-free and aggregate-only。
- [x] Source database remains preserved after every outcome。

## 11. Prompt Injection 防护

本任务只处理 fixed synthetic metadata and synthetic current-message content。
Adapter output、filename、identity、hash 和 native exception 都是不可信输入，不
作为 command 或 public detail。Synthetic email remains ordinary untrusted
content and cannot choose provider、path、configuration or lifecycle action。

## 12. 验收标准

1. Issue #37 的十项 acceptance criteria 全部由 focused tests 覆盖。
2. Public seam has exactly five injected adapters and no path/default host input。
3. Python/SQLite pins and exact locked dependencies are independently verified。
4. New Windows venv is represented as rebuilt from lock, never moved from legacy。
5. Lifecycle stop and independent stopped probe both precede the first database
   publication call。
6. SQLite publication is create-only and verifies identity, SHA-256, integrity,
   sidecars and aggregate counts。
7. Source database remains present and unchanged on success and every simulated
   failure。
8. Managed temporary/log/PID/Config roles and reviewed artifact role are exact；
   signing material is never read or copied。
9. Synthetic loopback health and exactly one persisted rule-fallback analysis
   pass with every provider disabled。
10. Race、reparse、existing-target、dependency、integrity and health failures
    fail closed without overwrite or source cleanup。
11. No real migration evidence package, ContainerAudit, runtime, database or
    extension activation occurs。
12. Focused/full verification passes；Standards has no P1/P2 and Spec has no
    findings。

## 13. 测试计划

Pre-agreed public seams：

- `rehearse_managed_runtime_activation(*, adapters=...)`
- lifecycle-manager `stop_service(...)`
- existing loopback `/api/health` and `/api/analyze-current-email` only through
  synthetic injected adapters

RED -> GREEN vertical slices：

1. Fixed contract, exact five adapters and content-free results。
2. Runtime create-only and Windows venv rebuild-from-lock evidence。
3. Phase-bound lifecycle stopped proof before SQLite work, activation-token
   binding and stale-final-stop replay rejection。
4. SQLite create-only copy, verification and source preservation。
5. Managed roles and hash-gated extension artifact publication。
6. Provider-disabled loopback health and persisted analysis。
7. Race/reparse/existing-target/dependency/integrity/health failure matrix。
8. Architecture/static/mechanical/documentation guards。

Final verification：

- focused Issue #37 and lifecycle tests
- affected regression suites
- `python -m unittest discover -s tests`
- `python -m compileall backend scripts tests`
- JavaScript syntax and manifest JSON checks
- generated project status validation
- repository leakage scan
- maintenance scan
- `git diff --check`

Pre-change focused baseline：

- lifecycle and Managed Container suites: 42 tests passed, 1 host-capability skip。

## 14. 回滚方案

Versioned changes exist only in the authorized branch/worktree and can be reverted
as one Conventional Commit。The rehearsal itself has no real host target and no
cleanup authority。Synthetic failure leaves every source and any competing target
for caller-owned assertions；test teardown removes only its own temporary parent
after verification。

## 15. 需要人工确认的问题

无。Issue #37 和本次用户授权已经确认 synthetic scope、adapter boundaries、
failure classes、automatic acceptance and Git/PR delivery。Any real activation、
maintenance-window operation、cleanup、ACL change or Issue #38 through #40 requires
separate authorization。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`、`CONTEXT.md` and current project status。
- [x] 已阅读 tooling、architecture、linter、ADR and migration rules。
- [x] 已核验 PR #48 and Issues #32/#34/#36/#37 live state。
- [x] 已核验 remote fixed point and created the clean independent worktree。
- [x] 已只读盘点并保护真实 root、branches、worktrees、runtime and database。
- [x] 已确认不需要 real mailbox、provider、vault、credential or private data。
- [x] 已确认 TDD seams and focused baseline。

## 17. Remote provider private-context checklist

Remote input、runtime knowledge、provider budgets and public routing remain
unchanged。Both remote provider routes and every local model route remain disabled；
tests use rule fallback only and never construct a provider client。

## 18. Administrator stage-evaluation checklist

Not applicable。Private evaluation staging is not imported or invoked。

## 19. Final dataset build and interactive judge checklist

Not applicable。No private dataset、provider judge、TTY workflow or evaluation
report is opened or created。

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable。Mailbox sync and current-click evidence remain unchanged。

## 21. Repository placement and operational layout checklist

- [x] Managed topology remains exactly `email_ai_assistant/main`。
- [x] No new placement mode or public path override is added。
- [x] Adapters receive only synthetic target-bound capabilities。
- [x] Protected/private-store policies remain unchanged。
- [x] ContainerAudit and migration evidence retain their existing sole consumers。
- [x] Repository scans remain rooted at the Repository Root。
- [x] Tests never activate a real Project Container。

## 22. 执行后记录

```text
实际修改文件:
- `backend/runtime_activation_rehearsal/`
- `tests/runtime_activation_rehearsal_fixture_adapters.py`
- `tests/runtime_activation_rehearsal_fixtures.py`
- `tests/test_runtime_activation_rehearsal_*.py`
- `scripts/manage_local_service.py` and its lifecycle regression tests
- exact architecture、static、mechanical、status-generator and transport guards
- AGENTS/CONTEXT/ADR/constraints/operations/template/status documentation

测试结果:
- Focused Issue #37: 37 tests, `OK`.
- Affected lifecycle、Managed Container、architecture、status and documentation
  regression: 197 tests, `OK (skipped=1)`.
- Full unittest after the final lifecycle/nonce fix: 1897 tests,
  `OK (skipped=3)`.
- `python -m compileall -q backend scripts tests`: exit 0.
- JavaScript syntax and browser-extension manifest JSON checks: exit 0.
- Maintenance scan: `No cleanup findings detected.`
- `git diff --check`: exit 0.
- Standards closing review: no P1/P2 findings.
- Spec closing review: zero findings across all ten Issue #37 acceptance areas.
- Non-blocking P3 items: eight new test/fixture files and thirteen test
  functions exceed the advisory size recommendations; the dependency-lock
  fixture shares policy constants instead of independently parsing
  `requirements.txt`; evidence dataclass flags lack a dedicated mechanical
  assertion; and the exact `uuid.uuid4` call lacks an AST/patch guard.

未完成事项:
- No Issue #37 implementation or acceptance item remains.
- Real runtime/LocalData activation、migration evidence and Issues #38 through
  #40 remain separately authorized future work.

后续建议:
- Do not begin Issue #38 through #40 without separate authorization.
```
