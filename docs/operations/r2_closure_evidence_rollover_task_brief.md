---
last_update: 2026-08-29
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 historical closure evidence rollover task brief

## 1. 任务名称

Retain stale Solo Maintainer Closure evidence before rebuilding exact-master closure.

## 2. 任务类型

```text
security
```

## 3. 当前状态

```text
in_progress
```

## 4. 任务目标

在冻结的 `master` commit `fbddaf31d3d3829ccf7e72bee00703da718222b8`、
tree `199ac0b98432f4dd59842de5475095b2caa5a7e8` 上新增一个独立、无参数、
no-clobber 的 maintenance seam。它只把已经严格验证且绑定旧 master 的 active
Solo Maintainer Closure 目录，以同 parent、同 volume、保持对象 identity 的 rename
保留为确定性 historical evidence，从而让 create-only closure 能针对新 master
重新生成；它不把旧证据升级为当前 approval 或 authority。

## 5. 非目标

- 不执行 Issue #39 真实主机 cutover、prepare、execution confirmation 或任何 host role。
- 不修改、关闭或重新标记 Issue #38/#39，不创建或修改 GitHub ruleset。
- 不 fetch、prune、repair damaged ref、删除、覆盖、复制、清理或回滚任何 closure 文件。
- 不改变 `SoloMaintainerClosure.prepare()` / `confirm(...)` 或 protected verifier 的
  public seam 和证据含义。
- 不增加邮箱、provider、vault、private data、runtime、frontend、HTTP、SQLite、
  credential、arbitrary path、shell command 或 caller-supplied repository 能力。
- 自动测试不得读取或移动真实 `.git/r2-solo-maintainer-closure-v1`。

## 6. 背景与依据

当前 active closure 精确绑定旧 master
`913111688e1fa1606b6a931ca96d50bd9780357a`，而当前 frozen master 已推进到
`fbddaf31d3d3829ccf7e72bee00703da718222b8`。现有 publication 为 create-only，
因此不得覆盖 active target；当前代码也没有获批的 stale-evidence rollover。

本任务依据用户 2026-08-29 的单独批准，以及：

- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md`
- `docs/operations/r2_solo_maintainer_closure_runbook.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/constraints/ci_guardrails.md`

## 7. 涉及范围

### Add

```text
backend/r2_closure_evidence_rollover/__init__.py
backend/r2_closure_evidence_rollover/contracts.py
backend/r2_closure_evidence_rollover/repository.py
backend/r2_closure_evidence_rollover/storage.py
backend/r2_closure_evidence_rollover/rollover.py
scripts/rollover_r2_solo_maintainer_closure.py
tests/test_r2_closure_evidence_rollover.py
tests/test_r2_closure_evidence_rollover_architecture.py
docs/operations/r2_closure_evidence_rollover_task_brief.md
```

### Modify

```text
AGENTS.md
CONTEXT.md
docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md
docs/operations/r2_solo_maintainer_closure_runbook.md
docs/constraints/tooling_constraints.md
docs/constraints/architecture_constraints.md
docs/constraints/linter_constraints.md
docs/constraints/mechanical_rule_translation.md
docs/constraints/ci_guardrails.md
docs/conventions/logging.md
docs/templates/agent_task_brief_template.md
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

任何额外路径都属于 contract change，必须停止并取得新的明确批准。

## 8. 技术方案

1. 新增独立 `ClosureEvidenceRollover.prepare()` / `execute(exact_candidate_fingerprint)`
   深模块；production constructor 和 CLI 都不接受 path、repository 或 host capability。
2. `prepare()` 只读重建 canonical 300-second candidate：验证 current HEAD 与
   `origin/master` 精确相等且 clean；active 目录、manifest、receipt、交叉绑定、旧
   commit/tree、旧 commit 是 current master 的严格祖先；target historical 名称不存在。
3. historical 名称固定为
   `r2-solo-maintainer-closure-v1.historical-<old-commit-16>-<manifest-fingerprint-16>`。
4. `execute()` 以 exact candidate fingerprint 做 compare-and-swap，fresh rederive
   所有状态，然后只允许 Git common directory 内 same-parent、same-volume、
   no-replace rename。source/target parent/target、reparse、hard-link、DACL 和 Windows
   file identity 在 commit point 前后核验。300 秒半开窗口同时使用 wall 和 private
   monotonic deadline；candidate 单独绑定 parent identity/DACL。Windows 必须释放 child
   handles 才能 rename directory，因此先用 writer-excluding handles 读取 exact bytes，
   再以 pending source-directory oplock 覆盖 release-to-rename gap。
5. 成功只返回 canonical content-free receipt 和固定状态；receipt 的 approval、
   execution authority、Issue #39 authority、deletion、overwrite、cleanup counts 均为零。
6. 任一失败返回固定 content-free code。不存在 pathname rollback、delete、repair、
   overwrite、copy 或 cleanup；任何 observed state 留待人工 incident disposition。
7. 固定 CLI 只有 `run`；它先打印 candidate，再以同一 fingerprint 调用 `execute()`。
   live command 仅在代码 merged、new exact-master LF worktree 验证完成后，依本任务的
   单独授权运行一次。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

无 HTTP/API 变化。新增 repository-internal maintenance seam；既有 closure 和 Issue #39
interfaces 不变。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱、provider、vault、private data 或 credential。
- [x] 不自动发送、删除或归档邮件。
- [x] 所有错误、repr、stdout/stderr 均为 fixed content-free data。
- [x] 测试只使用 synthetic temporary Git repositories 和 artifacts。
- [x] 不增加 delete、overwrite、cleanup、copy、repair 或 arbitrary-path surface。
- [x] historical evidence 明确不是 approval、current closure 或 Issue #39 authority。

## 11. Prompt Injection 防护

不适用。本任务不处理邮件、AI prompt 或不可信自然语言输入。

## 12. 验收标准

1. candidate 严格绑定 current master、旧 closure bytes/identity 和唯一 historical target。
2. wrong/stale/replayed fingerprint、master/status/artifact/ACL/identity/target drift 全部失败。
3. existing target、reparse、hard link、cross-volume 和 invalid old closure 全部 fail closed。
4. 成功只发生一次 no-replace identity-preserving rename；旧 bytes 和 file identity 不变。
5. 既有 closure/protected verifier/#39 public seams 和 authority counts 不变。
6. affected、architecture、mechanical、maintenance、leakage 和 full unit suites 通过。
7. PR 五项 checks 全部 `completed/success` 后才 merge；merged master 再等待同样五项 checks。
8. live rollover 后才生成 fresh closure、运行 protected verifier，并停在新的 #38 final review。

## 13. 测试计划

- 先写 failing unit/contract tests，再按最小 slice 实现。
- 运行 rollover focused tests、closure/protected-verifier affected tests、architecture、
  static linter、mechanical rule 和 status generator tests。
- 运行 `python -m unittest discover -s tests`、maintenance scan、repository leakage scan。
- live step 只验证真实 active/historical directories、bytes、identity 和 exact master；不执行
  #39 cutover。

## 14. 回滚方案

代码回滚由后续独立 Git 变更处理。live rollover 没有自动回滚：历史目录是保留证据，
不得 rename back、delete 或 overwrite；任何异常立即停止并进入单独 incident disposition。

## 15. 需要人工确认的问题

无。用户已批准本 brief 的最小 rollover、完整 PR/CI/merge 以及 merge 后一次 live
rollover；新的 #38 人工 final review 与任何 #39 真实 cutover 仍需分别确认。

## 16. 执行前检查

- [x] 已完整阅读当前 worktree 的 `AGENTS.md`、project status、适用 constraints 和 skills。
- [x] 已冻结 exact master commit/tree，并确认 worktree clean。
- [x] 已确认项目禁止所有 Superpowers workflow/skill。
- [x] 已确认 no mailbox/provider/private-data scope。
- [x] 已确认 exact Add/Modify/Delete allowlist。

## 17. Remote provider private-context checklist

不适用；remote provider dataflow 不变，providers 继续默认 disabled。

## 18. Administrator stage-evaluation checklist

不适用。

## 19. Final dataset build and interactive judge checklist

不适用。

## 20. Bounded corpus-to-runtime handoff checklist

不适用。

## 21. Repository placement and operational layout checklist

- [x] 不改变 Repository Root、Project Container、placement 或 ordinary layout。
- [x] 不增加 caller-supplied path/repository/host capability。
- [x] 不运行 migration、cutover、service、ACL-apply、database 或 runtime operation。
- [x] tests 仅 synthetic/offline；live rollover 只触及 fixed Git common closure evidence。

## 22. Issue #110 Solo Maintainer Closure / Execution Confirmation checklist

- [x] `backend.r2_solo_maintainer_closure` 的十文件和 public seam 不变。
- [x] manifest/receipt canonical validators 被复用，不重新解释 closure 语义。
- [x] historical evidence 不是 current closure、approval 或 authority。
- [x] no-replace、no-delete、no-overwrite、no-cleanup 与 content-free failures 保留。
- [x] protected verifier 仍只接受 fixed active directory；historical sibling 不可作为输入。
- [x] Execution Confirmation 和所有 production roots 不变且保持 dormant。

## 23. 执行后记录

- 2026-08-29：实现完成；变更范围与本 brief 的 exact Add/Modify/Delete allowlist 一致，
  Standards 与 Spec 双轴 review 均为 PASS。
- focused rollover tests：24/24 通过；既有 closure tests：35/35 通过；
  close-final-master tests：20/20 通过。
- architecture、static-linter、mechanical、status-generator 与 mailbox-transport
  suites 分别为 51/51、31/31、11/11、37/37、15/15 通过。
- full discovery：运行 2895 项，5 项预期跳过；2893 项通过。剩余两项仅因用户已有的
  localhost preview service 占用 `127.0.0.1:8765`，分别固定失败为
  `R2_ISSUE39_LEGACY_SERVICE_AMBIGUOUS`；未停止或修改该用户进程，待隔离 CI 复核。
- maintenance scan：exit 0，仅报告 24 项已知 low stale-doc；repository leakage scan：
  exit 0、零 finding；`git diff --check`：exit 0。
- PR #124 首轮 `portable-provenance` 以固定码 `R2_CI_PROVENANCE_INVALID` fail closed；
  根因为新增 Windows-only tests 使用了未登记的 skip reason。修复统一复用既有
  `Windows NTFS sandbox required`，并新增 architecture guard；rollover 25/25、
  CI-provenance 17/17 聚焦回归通过，等待新的 PR checks。
- PR、五项 CI、merge、merged-master CI、exact-master LF、live rollover、fresh closure、
  protected verifier 与新的 #38 final review：待后续受控步骤填写。
