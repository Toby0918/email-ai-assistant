---
last_update: 2026-08-30
status: active
owner: "@tobyWang"
review_cycle: per-change
source_type: task_brief
---

# R2 closure rollover source-delete guard incident task brief

## 1. 目标

修复 historical closure evidence rollover 在真实 Git-common ACL 布局中无法取得
source-directory `DELETE` handle 的缺陷，同时保持 exact bytes、identity、原始 protected
DACL、same-parent no-replace rename、无清理和 fail-closed 边界。

## 2. 已确认 incident

只读 disposition 在 frozen master
`3ca0faddb9b6384941974c23e891aac18588246b` 上以 terminal rename 空操作探针复现：

- 两个 artifact file handle、level-7 oplock 和 stream guard 全部通过；
- `_open_rollover_guards()` 打开 active closure directory 时，请求
  `DELETE | READ_CONTROL | FILE_READ_ATTRIBUTES`，返回 Win32 error 5；
- active closure DACL 仅允许 protected read/execute；真实 Git-common parent 给普通会话的
  权限不含 `FILE_DELETE_CHILD`；
- 现有 native test 仅保护 child，测试 parent 仍给进程 delete-child 权限，因而漏检；
- source 保持存在、historical target 不存在，两个 artifact SHA-256 未改变。

## 3. 授权与边界

用户授权在确认代码缺陷后执行任务简报、测试、PR、CI、merge 并重新冻结 master。
本代码修复和自动测试不得读取或移动真实 closure，不得重试 live rollover，不得修改真实
DACL，不得移动、删除、覆盖、修复或清理真实证据。merge 后只完成新的 exact-master
冻结；新的 live rollover、closure、protected verifier、Issue #38 final review 和 Issue #39
cutover 均需继续服从各自既有治理边界。

## 4. 公开 seam 与 TDD

预先确认的测试 seam 是既有 `FixedClosureEvidenceStorage.commit(observation,
before_commit)`。先新增一个 production-shaped parent ACL native test：parent 允许当前进程
读写但不授予 `FILE_DELETE_CHILD`，active closure 保持既有 protected read/execute DACL。
测试必须先在旧实现上失败，再以同一 public seam 验证成功 rename、原始 source DACL
保留到 target、parent DACL 不变且无额外对象。

## 5. 最小技术方案

1. 先取得并保持 candidate-bound parent namespace/identity/DACL guard。
2. 以 owner-available `WRITE_DAC | READ_CONTROL | FILE_READ_ATTRIBUTES` 打开一个固定
   source control handle，验证 exact original protected read/execute DACL。
3. 仅在该 held handle 上短暂应用固定 protected DACL：保留 Everyone read/execute，并只向
   object owner 授予 standard `DELETE`。
4. 在 parent guard 下取得所需 source rename handle；在任何后续步骤前，通过原 control
   handle 恢复 exact original DACL并逐 handle 比对。
5. 保持原有 file/source/parent oplock、fresh state callback、exact byte/identity/name guard，
   最终仍只调用一次 same-parent no-replace handle rename。
6. 任一临时 DACL apply/open/restore/verify 失败均返回固定 publication rejection；代码不做
   pathname rollback、copy、delete、overwrite、repair 或 cleanup。

临时 DACL 只作用于 test-owned sandbox 或以后另行授权的 live rollover。它不修改
Git-common parent DACL，也不改变最终 retained evidence DACL。

## 6. 精确路径 allowlist

### Add

```text
docs/operations/r2_closure_rollover_delete_guard_incident_task_brief.md
```

### Modify

```text
AGENTS.md
CONTEXT.md
backend/r2_closure_evidence_rollover/storage.py
tests/test_r2_closure_evidence_rollover.py
tests/test_r2_closure_evidence_rollover_architecture.py
docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md
docs/operations/r2_closure_evidence_rollover_task_brief.md
docs/operations/r2_solo_maintainer_closure_runbook.md
docs/constraints/tooling_constraints.md
docs/constraints/architecture_constraints.md
docs/constraints/linter_constraints.md
docs/constraints/mechanical_rule_translation.md
docs/constraints/ci_guardrails.md
scripts/generate_project_status.py
docs/operations/project_status_log.md
tests/test_architecture_constraints.py
tests/test_static_linter_constraints.py
tests/test_mechanical_rule_constraints.py
tests/test_generate_project_status.py
tests/test_mailbox_transport_constraints.py
```

### Delete

```text
none
```

任何额外路径都必须停止并重新取得明确批准。

## 7. 验收

- production-shaped parent ACL native test red then green；
- existing rollover focused/native/architecture tests 通过且真实 closure 未被测试访问；
- full unit suite、maintenance scan、leakage scan 通过；
- PR 五项 checks 全部 `completed/success` 后 merge；
- merged master 五项 checks 全部 `completed/success`；
- 创建并验证 clean exact-master LF review worktree，raw tracked bytes 与 Git blobs 精确一致；
- 不执行 live rollover 或任何真实 host cutover。

## 8. 回滚

代码通过后续独立 Git 变更回滚。live evidence 没有本任务内的回滚或清理动作。

## 9. 本地执行记录

- read-only incident probe 精确定位 source-directory open 的 Win32 error 5；probe 的
  terminal rename 被内存桩阻断，source/target existence 和两个 artifact SHA-256 前后相同。
- production-shaped parent-without-delete-child tracer test 在旧实现上固定失败，修复后
  通过；临时 DACL write-success/readback-failure 回归同样先红后绿，并证明 original DACL
  在异常路径恢复。focused rollover/native/architecture 28/28 通过。
- rollover + existing closure + protected-verifier affected suites 在新增异常路径用例后为
  83/83 通过。
- architecture/static/mechanical/status suites 130/130 通过。
- mailbox generator trust-hash regressions 和 server 网络边界用例单独复核 3/3 通过。
- full discovery 运行 2898 项、5 项预期跳过；本改动导致的 2 项 generator trust-hash
  failures 已修复。另有 2 项既有 `R2_ISSUE39_LEGACY_SERVICE_AMBIGUOUS`，对应用户现场
  localhost preview service；另 1 项 server connection-aborted 在单独重跑时通过。未停止、
  修改或探测该用户服务。
- maintenance scan exit 0，仅报告既有 24 项 low stale-doc；repository leakage scan exit 0、
  零 finding。
- live rollover、真实 DACL 变更、证据移动/清理、fresh closure、protected verifier、Issue
  #38 final review 和 Issue #39 cutover 均未执行。
