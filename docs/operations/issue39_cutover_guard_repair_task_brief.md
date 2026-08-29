---
last_update: 2026-08-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Issue 39 cutover launch and visible-confirmation repair task brief

## 1. 任务名称

Issue 39 cutover launch anchor and visible action confirmation repair.

## 2. 任务类型

```text
fix | security | test | docs
```

## 3. 当前状态

```text
in_progress
```

## 4. 任务目标

修复真实 Project Container cutover 的两个 fail-closed 缺陷：固定命令当前从
legacy Repository Root 启动，但该 clean root 不含冻结 master runner；所有 live
Execution Confirmation 当前只显示 candidate fingerprint 和 acknowledgement，无法让
operator 在签署前审阅动作身份与已验证状态。

修复后，初始进程只能从 code-fixed、已登记的 exact-master launcher worktree 启动；
在任何确认输入前，控制台必须显示严格、无路径、由当前绑定事实确定的操作上下文。

## 5. 非目标

- 不执行真实 incident disposition、evidence publication、cutover、resume 或 rollback。
- 不访问 provider、mailbox、vault、private data、credentials 或 recovery media。
- 不增加 caller-selected path、environment override、arbitrary command 或 adapter surface。
- 不 fetch、prune、clone、reset、stash、repair、删除、覆盖或清理任何现场。
- 不修改 Issue、ruleset 或服务状态，直到本任务到达其单独授权的 GitHub gate。
- 不改变产品邮件读取、附件、provider、发送、删除或归档边界。

## 6. 背景与依据

2026-08-29 的 real-cutover zero-mutation preflight 发现：

1. `D:\Projects\email_ai_assistant` clean at
   `f07178160c188cccf49ec017e70ee97c2f714057`，缺少
   `scripts\execute_project_container_cutover.py`；冻结 master
   `913111688e1fa1606b6a931ca96d50bd9780357a` 的审核工作树才包含 runner。
2. `backend.r2_production_binding` 的 Windows console adapter 仅显示 candidate
   fingerprint 与 fixed acknowledgement；Issue 39 adapters 未显示动作名称、方向、
   序号或当前受审状态。

相关文档：

- `AGENTS.md`
- `CONTEXT.md`
- `docs/operations/issue39_project_container_cutover_runbook.md`
- `docs/operations/issue39_one_command_cutover_task_brief.md`
- `docs/decisions/0012-issue39-project-container-cutover-orchestration.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`

## 7. 涉及范围

预计新增或修改：

- `scripts/execute_project_container_cutover.py`
- `backend/r2_issue39_orchestrator/` 下的 fixed launch/context projection
- Issue 39 preflight、bootstrap、catalog/recovery 与 terminal confirmation adapters
- `tests/` 中的 portable contract、CLI、confirmation 与 Windows synthetic coverage
- 本任务简报、runbook、ADR、约束文档和生成的 project status log

## 8. 技术方案

1. 将既有已登记路径
   `D:\Projects\email_ai_assistant\.worktrees\issue39-governed-enablement`
   固定为 initial launcher worktree。wrapper 在 import production modules 前验证
   original/resolved current directory、script Repository Root 和 fixed launcher 为同一
   非 reparse directory；不接受参数或 environment redirect。
2. launcher 仍使用 legacy `.venv` 中的 pinned Python 3.12.13。所有 host effects 前，
   既有流程继续把进程切换到 external protected evidence runner。
3. 新增 closed Issue 39 confirmation-context projection，只接受 code-owned enums/
   catalog values 和 bounded integers；输出一行 printable ASCII、content-free context。
4. 每个 preflight、evidence/bootstrap、catalog forward/resume/rollback 和 terminal
   confirmation 都先显示其 bound context，再由既有 V3 console adapter 显示 candidate
   fingerprint 与 exact acknowledgement 并读取两行输入。
5. context 显示失败、字段不在 allowlist、序号/状态不一致或输出流异常均在确认读取和
   host effect 前 fail closed。

## 9. 安全与隐私边界

- context 不包含 raw path、SID、SDDL、Git branch、邮件、附件、数据库内容、PID、
  credential、exception 或 caller-supplied text。
- launcher 路径是 code-fixed constant，不来自 argv、environment、Config 或 manifest。
- 通用 V3 Execution Confirmation schema、300 秒窗口、single-use、durable journal-head
  binding 与 fixed acknowledgement 保持不变。
- 不把普通 stdout 文字当作 authority；authority 仍仅来自随后成功验证的 exact
  candidate fingerprint 与 acknowledgement。

## 10. 测试计划

- 先写 regression tests，证明旧实现：
  - runbook/launcher 指向缺少 runner 的 legacy root；
  - Issue 39 live confirmation 没有 human-readable bound context。
- portable tests 覆盖 fixed launcher identity、wrong cwd/reparse/alternate path rejection、
  strict context grammar、所有 confirmation phase/state projection 和 output ordering。
- Windows tests 覆盖 real console output ordering与既有 TTY identity rules；仅使用
  test-owned synthetic objects，不调用 fixed live CLI。
- 运行 focused tests、`python -m unittest discover -s tests`、maintenance scan、
  `git diff --check` 和项目机械规则。

## 11. 验收标准

- 固定 operator command 从现存 launcher worktree 可找到 versioned runner，并且 wrapper
  在任何 production import/readiness/network/host mutation 前拒绝 wrong launch anchor。
- 每个可能请求 `CONFIRM_R2_ISSUE39_EXECUTION_V1_NOT_CLOSURE_ATTESTATION`
  的 Issue 39 路径，均先显示唯一、严格、可读的 action context。
- context 精确标示 phase、operation、command、direction、current state 和适用序号；
  terminal/evidence/preflight 使用其各自 closed vocabulary。
- 原 V3 candidate/claim contracts、durable recovery、no-replace、no-cleanup 与 provider/
  mailbox/vault exclusion 全部保持。
- 全量测试、CI 五项 required checks 和 post-merge master CI 成功。
- merge 后在新 master 上重新完成 exact LF worktree、closure、protected verifier 和
  Issue 38 fourteen-item final review；真实 cutover 仍需另行授权。

## 12. 回滚方案

代码阶段通过普通 PR 回滚本修复 commit；不得通过现场 copy、manual runner、alternate
cwd 或放宽 confirmation 规则绕过。若 live preflight 或 CI 发现任何 drift，保留全部
现场和证据并停止，不执行真实 cutover。

## 13. 授权记录

2026-08-29，sole maintainer 明确授权：修复 #39 “启动锚点”和“可见动作确认”缺陷，
完成任务简报、实现、测试、PR、CI、merge；新 master 后重新完成 closure、protected
verifier 与 #38 final review；真实 cutover 仍需再次单独授权。
