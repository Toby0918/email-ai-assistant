---
last_update: 2026-08-09
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 GitHub guardrail response compatibility task brief

## 1. 任务名称

Implement authenticated, read-only GitHub guardrail response compatibility for
the R2 Solo Maintainer Closure.

## 2. 任务类型

```text
security
```

## 3. 当前状态

```text
in_progress
```

## 4. 任务目标

修复 GitHub authenticated ruleset detail 在 approved pull-request rule 中返回
wire-only beta default `required_reviewers=[]` 时，现有 strict guardrail reader
错误拒绝 canonical configuration 的 closure-enforcement defect。将认证读取、
HTTP/JSON 边界和唯一窄幅 compatibility rule 集中在 private deep module，同时保持
`SoloMaintainerClosure.prepare()` / `confirm()`、965-byte canonical configuration、
configuration fingerprint、snapshot schema 和 fixed failure code 不变。

## 5. 非目标

- 不创建、修改、禁用或删除 GitHub ruleset/classic branch protection。
- 不运行 live closure `prepare`、`confirm` 或 protected verifier。
- 不提交、不 push、不创建 PR、不 merge，不修改 Issue #38、#39 或其他 ticket。
- 不运行 `gh auth token`、`gh auth login` 或任何 GitHub write request。
- 不向 caller 暴露 token、credential、host、repository、path、endpoint 或 Adapter。
- 不放宽 unknown field、nonempty bypass、nonempty reviewer、rule order、required
  checks、integration id、conditions、enforcement 或 classic-protection equality。
- 不增加 dependency、workflow、public HTTP/API、CLI option、schema、fingerprint、
  provider、mailbox、vault、private-data、host-effect 或 Issue #39 authority。
- 不修改批准的 exact allowlist 之外的路径。

## 6. 背景与依据

GitHub 当前 authenticated ruleset detail 明确返回 `bypass_actors=[]`，同时在唯一
`pull_request.parameters` 中增加 beta field `required_reviewers=[]`。只删除该 exact
empty wire default 后，结果与现有 `ruleset_configuration_v1()` 完全相等，canonical
bytes 仍为 965，configuration fingerprint 仍为
`5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e`。

现有 anonymous reader 可能看不到 `bypass_actors`，因此不能把字段缺失推断为 zero。
本任务是显式的 architecture/security contract amendment，依据 operator 批准的第
32 项 exact proposal 与第 33 项 local-only implementation authorization。
当前 GitHub state 已确认 ruleset 已创建，ID 为 `20601214`；该事实不授权运行
live `prepare`、`confirm` 或 protected verifier。

相关文档:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/constraints/ci_guardrails.md`
- `docs/security/project_container_cutover_contracts.md`
- `docs/operations/r2_solo_maintainer_closure_runbook.md`

## 7. 涉及范围

Add exactly:

```text
backend/r2_solo_maintainer_closure/github_guardrail.py
tests/test_r2_solo_maintainer_github_guardrail.py
docs/decisions/0011-authenticated-github-guardrail-observation.md
docs/operations/r2_github_guardrail_response_compatibility_task_brief.md
```

Modify only as needed:

```text
AGENTS.md
backend/r2_solo_maintainer_closure/repository.py
backend/r2_solo_maintainer_closure/hosted_evidence.py
tests/test_r2_solo_maintainer_closure.py
tests/test_r2_solo_maintainer_closure_architecture.py
tests/test_architecture_constraints.py
tests/test_mechanical_rule_constraints.py
tests/test_static_linter_constraints.py
docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md
docs/constraints/tooling_constraints.md
docs/constraints/architecture_constraints.md
docs/constraints/linter_constraints.md
docs/constraints/mechanical_rule_translation.md
docs/constraints/ci_guardrails.md
docs/security/project_container_cutover_contracts.md
docs/operations/r2_solo_maintainer_closure_runbook.md
docs/operations/testing_checklist.md
docs/operations/project_structure.md
docs/templates/agent_task_brief_template.md
scripts/generate_project_status.py
tests/test_generate_project_status.py
docs/operations/project_status_log.md
```

Delete: none.

Explicitly unchanged:

```text
CONTEXT.md
backend/r2_solo_maintainer_closure/__init__.py
backend/r2_solo_maintainer_closure/closure.py
backend/r2_solo_maintainer_closure/contracts.py
scripts/close_r2_final_master.py
scripts/verify_r2_final_master_closure.py
requirements.txt
.github/workflows/*
```

The operator separately approved this one-path allowlist amendment after the
active Issue #110 checklist was found to pin the old nine-file package. The
template change is limited to the ten-file count and the same fixed
authenticated GET-only, no-token-read, and empty-only beta compatibility
boundary; it adds no production capability.

## 8. 技术方案

1. 新增 private deep module `github_guardrail.py`，以一个 verified snapshot
   function 隐藏 authenticated transport、strict wire validation 和 compatibility。
2. production Adapter 只运行 code-fixed absolute Windows GitHub CLI，通过现有
   Windows keyring session 认证；Python 不读取或打印 token。
3. 每轮 observation 前后都运行固定 `gh auth status --active --hostname
   github.com --json hosts` 并严格解析 active account state；JSON-mode exit zero
   不单独证明 auth success。
4. API Adapter 只允许 fixed `gh api --hostname github.com --method GET --include`
   请求 ruleset listing、validated positive-int ruleset detail 和 master classic
   protection；其他同仓库 endpoint 也必须在 process execution 前拒绝。只有 classic
   protection 的 exact HTTP 404 / exit 1 表示 absent；其他非-200 拒绝。
5. subprocess 使用 `shell=False`、`stdin=DEVNULL`、fixed timeout 和 bounded
   stdout/stderr。child environment 删除 ambient GitHub token/host/repository/config
   与 proxy overrides，固定 `GH_PROMPT_DISABLED=1`、关闭 update notifier/extension
   notifier 与 telemetry。唯一允许的 nonempty stderr 是 classic endpoint 的 exact
   content-free `gh: Branch not protected (HTTP 404)\n`，且必须同时绑定 HTTP 404 /
   exit 1；其他 transport/auth/status/size/JSON/schema failure 映射为现有
   content-free guardrail rejection。
6. detail 必须显式包含 `bypass_actors` 且严格等于 `[]`。唯一
   `pull_request.parameters.required_reviewers` 缺失时接受，严格等于 `[]` 时删除；
   非空、错型、duplicate pull-request rule 或错位置全部拒绝。随后继续与 unchanged
   `ruleset_configuration_v1()` exact equality。
7. `repository.py` 保留 remote commit/hosted evidence 的现有 public HTTPS reader，
   仅把 guardrail observation 委托给新 module；每次 prepare/confirm/verifier 都 fresh
   collect，不缓存。
8. tests 通过同一 module Interface 注入 in-memory command/observation Adapter，
   不调用 live GitHub、`prepare`、`confirm` 或 verifier。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

无 public API、HTTP、CLI 或 closure Interface 变化。仅新增 package-private Adapter
seam；production caller 仍使用无参数 `SoloMaintainerClosure()`。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱、provider、vault、private store 或 private data。
- [x] 不自动发送、删除或归档邮件。
- [x] Python 不读取、返回、记录或打印 GitHub token。
- [x] CLI argv、stdout/stderr、exceptions、snapshot 和 manifest 不含 credential。
- [x] 只允许 fixed authenticated GitHub GET，禁止 arbitrary URL/method/field input。
- [x] 缺失或不完整的 authorization evidence fail closed。
- [x] failure output 继续使用 fixed content-free error code。
- [x] tests synthetic/offline，不调用 live GitHub 或 closure ceremony。

## 11. Prompt Injection 防护

不适用。本任务不读取邮件、prompt 或 AI output。

## 12. 验收标准

1. authenticated `bypass_actors=[]` 且 beta `required_reviewers=[]` 通过，canonical
   bytes 与 fingerprint 不变。
2. bypass 缺失/非空、reviewers 非空/错型、duplicate pull-request rule、unknown
   nested drift、rule/check/order/integration drift 均返回 fixed guardrail rejection。
3. auth failure、non-GET/unapproved endpoint、unexpected non-200、oversize、malformed
   JSON、unexpected stderr/timeout 均 fail closed；只有上文 exact classic 404 tuple
   可接受，且没有 raw detail 或 token disclosure。
4. architecture/static/mechanical tests 固定十文件 package inventory、private
   Adapter seam、authenticated GET-only contract 和 no GitHub mutation boundary。
5. focused、affected、constraint、documentation、status、maintenance、leakage、
   compile 和 full unittest matrix 通过。
6. final `git diff --name-status` 是批准 allowlist 的子集；无 commit、push、live
   prepare/confirm/verifier 或 GitHub mutation。

## 13. 测试计划

- 先写 module Interface behavior tests，连续运行两次确认 deterministic RED。
- 逐个实现 strict normalization、auth/transport Adapter 和 repository delegation。
- 运行 focused guardrail、closure、architecture、mechanical、linter、status tests。
- 更新 generated project status 后重跑 documentation/status、maintenance、leakage、
  compile 和完整 `unittest discover -s tests`。
- 最后执行 Standards/Spec read-only code review，修复批准范围内 P1/P2 finding。

## 14. 回滚方案

实现仅存在于隔离 worktree 的未提交 diff。失败时停止并保留可审计 diff；不删除或
覆盖 GitHub state、closure artifact、root worktree 或 published history。

## 15. 需要人工确认的问题

无。第 32 项已批准 exact design/allowlist；第 33 项已批准仅在隔离 worktree 本地
实现和测试。commit、push、live closure 与所有 GitHub mutation 未获授权。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`、`CONTEXT.md`、project status 与相关 constraint/docs。
- [x] 已确认 remote `master` baseline 为
  `aca53da3103cf673fefd5fb427c2114a81ad36c8`。
- [x] 已确认隔离 worktree 初始 clean，root dirty worktree 不在修改范围。
- [x] 已确认 exact Add/Modify/Delete allowlist 和 unchanged files。
- [x] 已确认 `docs/templates/agent_task_brief_template.md` 的单路径补项批准。
- [x] 已确认第二次补项仅增加
  `tests/test_mailbox_transport_constraints.py` 和
  `tests/test_multimodal_documentation_contracts.py`。
- [x] 已确认不触碰真实邮箱、provider、vault、private data 或 GitHub write state。
- [x] 已确认不运行 live `prepare`、`confirm` 或 verifier。

## 17. Remote provider private-context checklist

不适用。本任务不改变 provider、runtime knowledge、privacy transformation 或预算。

## 18. Administrator stage-evaluation checklist

不适用。

## 19. Final dataset build and interactive judge checklist

不适用。

## 20. Bounded corpus-to-runtime handoff checklist

不适用。

## 21. Repository placement and operational layout checklist

- [x] Repository placement、Project Container 与 protected-root semantics 不变。
- [x] root worktree、real host、closure publication 与 Issue #39 path 均不触达。
- [x] credential capability confined to fixed authenticated GitHub guardrail GET Adapter。
- [x] closure evidence 仍不是 Issue #38 approval 或 Issue #39 authority。

## 22. 执行后记录

- 隔离 worktree 固定在 baseline
  `aca53da3103cf673fefd5fb427c2114a81ad36c8`；最终内容差异为 4 Add、23
  Modify、0 Delete，共 27 个批准路径。获批的 `hosted_evidence.py` 只有 checkout
  行尾状态，没有内容 diff。
- 新增 private `github_guardrail.py` 并让 `repository.py` 仅委托 guardrail
  observation。public closure/CLI/schema、965-byte canonical configuration 与
  fingerprint
  `5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e`
  均未改变。
- TDD 覆盖 empty-only beta normalization、显式空 bypass、固定 keyring identity、
  三个 approved endpoint、classic 404 的真实 exit/stderr tuple、独立有界
  stdout/stderr、timeout kill/reap、环境 token 清除、update notifier/telemetry
  禁用和 content-free rejection。实际 CLI parity 只读确认 classic 404 返回 exit 1；
  未运行 closure ceremony。
- 聚焦/约束回归 177 项通过；状态与交叉约束 39 项通过；compile 通过；repository
  leakage total=0；maintenance scan 仅保留 19 个既有 low stale-doc 提醒，无 high。
- Standards 与 Spec 双轴复审在修复 endpoint、stderr 和 CLI side-channel findings
  后均为 remaining findings=0。
- LF-only 短路径验证 clone 运行完整 discovery：2749 项中 2746 通过、0 failure、
  0 error、3 skipped，exit 0，测试时间 2657.986 秒。首轮长 temp clone 的唯一
  失败已证明是 261 字符 Windows 路径工件；相同用例在短 clone 单独通过，短 clone
  完整套件也通过。
- 根 dirty worktree 复核保持 HEAD
  `f07178160c188cccf49ec017e70ee97c2f714057`、13 项状态和 canonical SHA-256
  `f3ee07937cd1d214bdb0b5d215ae15ef273378d1349e8f9154083b6c35e3ef4b`。
- 未 stage、commit、push、运行 live `prepare`、`confirm` 或 verifier；未修改
  GitHub、ruleset、#38 或 #39。上述动作继续需要分别明确批准。
