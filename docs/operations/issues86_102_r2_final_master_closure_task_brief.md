---
last_update: 2026-08-02
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: task_brief
---

# Issues 86-102 R2 Final-Master Closure Task Brief

## 1. 任务名称

Implement the finite R2 final-master closure program from Issue #86 through
Issue #102.

## 2. 任务类型

```text
feature | security | test | docs | ci
```

## 3. 当前状态

```text
in_progress
```

## 4. 任务目标

从远端 `master@95e199e75b25af45e7e9ca0a8e85e7c26d4c5346` 开始，按 GitHub
原生依赖顺序逐一实现 #86-#102。最终产物必须把 frozen commit/tree、完整 closure
surface、Git-object source package、production compositions、统一 journal、retention、
generated runbook、portable/Windows provenance 和 fourteen global gates 绑定到唯一
`R2FinalMasterClosureReceiptV1`；唯一成功状态为
`ELIGIBLE_FOR_SINGLE_FINAL_MASTER_REVIEW`。

## 5. 非目标

- 不执行真实 Project Container cutover、rollback、service、ACL、Repository Root、
  worktree、Runtime、SQLite、CRX 或 Config 操作。
- 不启动或修改 #39，不签发、模拟、保存或读取真实 authority、private key、credential。
- 不访问 provider、mailbox、vault、Operator Private Zone、External Vault Zone 或 private data。
- 不新增 umbrella command、path/selector/force/shell/PowerShell/arbitrary Git surface。
- 不删除、清理、覆盖、prune、expire、recycle 或自动修复任何 original/new/partial/
  failed/evidence object。
- 不把 receipt、CI、review 或 synthetic evidence 变成 execution authority。
- 不更改正常 email-analysis API、SQLite schema、frontend permissions、prompt、provider
  routing、mailbox 或 private-knowledge policy。
- 不创建 #85 之外的新 remediation ticket；新发现按 frozen classification taxonomy
  返回现有 gap，除非出现需 operator 明确确认的真正 decision contradiction。

## 6. 背景与依据

- GitHub Spec #85 and child tickets #86-#102。
- Issue #38 remains the final operator approval surface; #39 remains blocked by #38。
- PR #84、Spec #69、#70-#83、accepted prototype 与历史 package
  `ae741bdd012bea76e2037b32a137ac26b8d96c79bcc734e8634f2095f97d55bc`
  仅为 non-authorizing prior evidence。
- `AGENTS.md`、`CONTEXT.md`、`docs/security/project_container_cutover_contracts.md`、
  tooling/architecture/linter/mechanical/CI constraints 共同约束实现。

## 7. 涉及范围

预计新增或修改：

- `backend/r2_final_master_closure/`：closure vocabulary、binding、gap/gate evidence、
  source-package/runbook/global coordinator contracts。
- 现有三个 production process roots、R2 publication/repository/lifecycle/recovery modules，
  仅按各 ticket 的 fixed composition seam 深化。
- `tests/`：public-contract、fresh-process、crash-gap、Git-byte、retention、runbook、
  Windows/portable provenance、architecture、mechanical、documentation、leakage tests。
- `.github/workflows/` 与 hash-locked CI inputs，仅在 #100 明确范围内修改。
- `docs/operations/`、`docs/security/`、`docs/constraints/` 与 generated status，按 ticket
  同步。

## 8. 技术方案

1. #86 建立一个纯 in-process 深层 module：公开 interface 仅包含 immutable binding、
   gap/gate receipts 与 terminal receipt construction；内部隐藏 canonical validation。
2. #87-#91 将 reviewed V2 binding 与 no-issuer dormancy 连接到三个物理独立 process roots。
3. #92 从 Git objects 证明 selected bytes、fourteen refs、Repository Root 和 eleven
   worktrees，不读取 ignored/private residue。
4. #93-#97 统一 `R2TransactionJournalV2`，逐次 authority 最多执行一个 action，并完成
   fresh-process inspection、forward seal 与 LIFO rollback。
5. #98 由 journal/plan/binding 确定性投影 object-level retention ledger，并证明生产图
   deletion capability count 为零。
6. #99 从同一 command catalog/state machine 生成 deterministic R2 operator runbook。
7. #100 构建 Git-object source package 与 pinned, hash-locked portable/independent Windows
   provenance gates。
8. #101 聚合 exact fourteen same-binding gate receipts；#102 freeze final master、生成 terminal
   receipt，并进入单次人工 final review。
9. 每个 ticket 使用一个或多个 vertical RED -> GREEN slice，通过公开 seam 测试并形成
   独立 Conventional Commit；完成后才 claim 下一 dependency-ready ticket。

## 9. 数据结构或接口变化

### 数据库变化

无 public/production SQLite schema change。所有测试数据库均为 synthetic caller-owned state。

### API 变化

无正常 HTTP API change。新增 interface 仅属于 dormant R2 closure/production process roots。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除、归档邮件。
- [x] 不在前端保存或暴露 provider key。
- [x] 不改变邮件正文的不可信输入边界或 AI JSON validation。
- [x] receipt、repr、stdout、stderr、logs 和 exceptions 仅含固定 status、fingerprints
  与 allowlisted aggregate counts。
- [x] 测试仅使用 synthetic identities、bytes、Git objects、journals、filesystems、SQLite、
  Config、service、authority 和 receipts。
- [x] closure evidence 永不实现或满足 execution-authority interface。

## 11. Prompt Injection 防护

不改变正常 analysis path；R2 closure/process interfaces 不接受邮件正文、自由文本或可执行
命令。

## 12. 验收标准

1. Exactly eight closure gaps 和 exact fourteen gate kinds 由 immutable registry 固定。
2. #86-#102 每个 acceptance criterion 均由 public-seam tests 和实现覆盖，依赖 blocker
   清零后才开始下一 ticket。
3. Terminal receipt exact binds final commit/tree、closure map、Git-object package、runbook、
   eight gap proofs 和 fourteen same-binding gate receipts。
4. Missing/duplicate/unknown/stale/mixed/self-certified/leaking evidence fail closed；receipt
   不能成为 authority。
5. Production no-issuer state 保持 dormant；所有验证为 synthetic/offline，provider attempts
   与 real-host operations 均为零。
6. Required/unclassified skips、leakage findings、cleanup operations、surface omissions 和
   #39 code changes 均为零。
7. 最终 full suite、architecture、mechanical、documentation、maintenance、repository
   leakage、Standards、Spec 与 security review gates 通过。

## 13. 测试计划

- 每个 ticket 先写一项公开行为测试并确认 RED，再实现最小 GREEN；不 mock 内部 module。
- 逐 ticket 运行 focused 与受影响 tests，定期运行 compile/architecture/mechanical checks。
- #100 的 native claims 仅来自 fresh runner-owned NTFS sandboxes；portable tests 明确不声称
  NTFS/ACL/real-console/process-isolation/durability evidence。
- #102 前运行 `python -m unittest discover -s tests`、maintenance scan、repository leakage
  scan，并按 `code-review` skill 进行 Standards/Spec 双轴独立 review 和复审。

## 14. 回滚方案

每个 issue 使用独立 Conventional Commit。后续回归只通过新的修复提交纠正，不重写历史，
不使用 destructive Git commands，不触碰 root worktree 或现有 linked worktrees。

## 15. 需要人工确认的问题

```text
#102 的 single final master review 与 Issue #38 operator approval 必须由人工完成；
agent 只能准备并验证 immutable evidence package，不能自我批准或把 review receipt 当作 authority。
```

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`、`CONTEXT.md`、project status log 与 parent Spec #85。
- [x] 已完整读取 tooling、architecture、linter constraints 和 issue tracker rules。
- [x] 已读取 #86-#102 live state、native dependencies 与唯一 frontier #86。
- [x] 已冻结 remote baseline 为 `95e199e75b25af45e7e9ca0a8e85e7c26d4c5346`。
- [x] 已建立干净 sibling worktree `D:\Projects\email_ai_assistant_issues_86_102_r2_closure`。
- [x] 已确认不触碰真实 host、mailbox、provider、vault、key、credential 或 private data。

## 17. Remote provider private-context checklist

Not applicable. No remote-provider input, runtime private knowledge, privacy transformation, or
provider budget changes are in scope. Providers remain disabled and verification remains offline.

## 18. Administrator stage-evaluation checklist

Not applicable.

## 19. Final dataset build and interactive judge checklist

Not applicable.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable.

## 21. 执行后记录

```text
实际修改文件：
- Pending.

测试结果：
- Pending.

未完成事项：
- #102 human final review remains human-only by contract.

后续建议：
- Pending.
```
