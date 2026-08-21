---
last_update: 2026-08-21
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 GitHub unattributed-approval guardrail compatibility task brief

## 1. 任务名称

Accept one exact GitHub wire default for zero-approval Solo Maintainer Closure
rulesets without changing the canonical guardrail contract.

## 2. 任务类型

```text
security
```

## 3. 当前状态

```text
publication_authorized_in_progress
```

## 4. 任务目标

修复 GitHub authenticated ruleset detail 为现有和新 ruleset 默认增加
`pull_request.parameters.require_extra_approval_for_unattributed_changes=true`
后，Solo Maintainer Closure 对当前 zero-approval ruleset 产生的兼容性拒绝。
兼容层只可在 `required_approving_review_count` 精确为整数 `0` 时接受字段缺失
或精确布尔值 `true`，删除该 wire-only default 后继续与既有 canonical contract
做完整相等比较。

## 5. 非目标

- 不接受 `false`、非布尔值、非零 approval count 或任何其他 unknown field。
- 不改变 965-byte canonical configuration、其 fingerprint、snapshot schema 或
  fixed rejection code。
- 不创建、修改、禁用或删除 ruleset/classic protection，也不运行 GitHub write。
- 不运行 `prepare`、`confirm`、protected verifier、Issue #38/#39 mutation 或真实
  cutover。
- 不 commit、push、创建 PR 或 merge。
- 不修改 mailbox、provider、vault、private data、runtime 或 public API surface。
- 不读取、打印、记录或向 Python 暴露 GitHub token。

## 6. 背景与依据

2026-08-20 的 authenticated fixed-GET observation 证明 ruleset `20601214` 的
唯一 canonical 差异是新增字段
`require_extra_approval_for_unattributed_changes=true`；当前
`required_approving_review_count=0`。GitHub 官方文档说明该 public-preview setting
对现有和新 ruleset 默认启用，且在 required approvals 为零时没有效果。

相关文档:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md`
- `docs/decisions/0011-authenticated-github-guardrail-observation.md`
- `docs/operations/r2_solo_maintainer_closure_runbook.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/constraints/ci_guardrails.md`
- `docs/security/project_container_cutover_contracts.md`

## 7. 涉及范围

Add exactly:

```text
docs/operations/r2_github_guardrail_unattributed_approval_compatibility_task_brief.md
```

Modify only as required:

```text
AGENTS.md
backend/r2_solo_maintainer_closure/github_guardrail.py
tests/test_r2_solo_maintainer_github_guardrail.py
tests/test_r2_solo_maintainer_closure_architecture.py
tests/test_architecture_constraints.py
tests/test_mechanical_rule_constraints.py
tests/test_static_linter_constraints.py
tests/test_mailbox_transport_constraints.py
tests/test_multimodal_documentation_contracts.py
docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md
docs/decisions/0011-authenticated-github-guardrail-observation.md
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
backend/r2_solo_maintainer_closure/hosted_evidence.py
backend/r2_solo_maintainer_closure/closure.py
backend/r2_solo_maintainer_closure/contracts.py
scripts/close_r2_final_master.py
scripts/verify_r2_final_master_closure.py
.github/workflows/*
requirements.txt
```

## 8. 技术方案

1. 通过现有 `collect_verified_guardrail(reader)` seam 写一个 caller-visible RED
   regression test，使用 injected observation 模拟 GitHub 新字段。
2. 在唯一 pull-request rule 的 strict normalization 中验证:
   - `required_reviewers` 仍只能缺失或精确 `[]`；
   - unattributed-approval field 只能缺失，或在 approval count 精确为整数 `0`
     时为精确布尔值 `true`；
   - 仅删除上述批准的 wire-only values。
3. 保留完整 canonical equality，因此所有其他 nested drift 继续 fail closed。
4. 同步所有机械固定的安全/架构/操作文档和生成状态文本。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

无 public API、HTTP、CLI、closure Interface 或 snapshot schema 变化。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱、provider、vault 或 private data。
- [x] 不发送、删除或归档邮件。
- [x] 不读取、打印或记录 GitHub token。
- [x] 只保留 fixed authenticated GET-only Adapter。
- [x] 新 compatibility 与 zero approvals 和 exact `true` 交叉门禁。
- [x] `false`、错型、非零 approvals 和其他 unknown field fail closed。
- [x] failure output 保持 fixed content-free code。
- [x] tests synthetic/offline，不调用 live closure ceremony。

## 11. Prompt Injection 防护

不适用。本任务不读取邮件、prompt 或 AI output。

## 12. 验收标准

1. 字段缺失继续通过。
2. 字段为 exact `true` 且 approvals 精确为整数 `0` 时通过。
3. `false`、`0`、`1`、`None`、字符串、容器、布尔 approval count 和非零
   approval count 均返回 fixed guardrail rejection。
4. empty-only `required_reviewers`、explicit empty bypass、五个 checks、integration
   id、rule order、classic absence 和 fixed GET/auth contract 均不放宽。
5. canonical configuration 保持 965 bytes，fingerprint 保持
   `5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e`。
6. focused、constraint、status、maintenance、leakage、compile 和 full unittest
   validation 通过；Standards/Spec review 无剩余 finding。

## 13. 测试计划

- 单个 public-seam behavior test先 RED 后 GREEN。
- 增加拒绝矩阵，覆盖 wrong values 与 nonzero/boolean approval count。
- 运行 guardrail focused tests 和相关 architecture/static/mechanical/status tests。
- 生成 project status 后重跑相关约束、maintenance、leakage、compile 和 full suite。

## 14. 回滚方案

改动保留为隔离 worktree 的未提交 diff。失败时停止并保留可审计现场；不修改
远端 ruleset、Issue、closure artifact 或其他 worktree。

## 15. 需要人工确认的问题

无。用户已于 2026-08-21 在 fresh GET-only pre-publication preflight 通过后授权
精确 publication batch：stage 已确认路径、commit、push 新分支并创建 draft PR。
merge、Issue/ruleset mutation、closure confirmation、protected verifier 与真实
cutover 仍不在授权内。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`、`CONTEXT.md`、project status、applicable constraints、
  ADR 0010/0011 和 runbook。
- [x] 已建立 2.2-second deterministic live rejection loop并最小化到唯一新字段。
- [x] 已确认 worktree baseline `2b116ab059ba316d5e30c273c272ebbff99415bb`
  与 raw Git blobs 精确一致。
- [x] 已确认不触碰真实邮箱、provider、vault、private data 或 GitHub write state。
- [x] 已确认测试 seam 与 exact Add/Modify/Delete allowlist。

## 17. Remote provider private-context checklist

不适用。

## 18. Administrator stage-evaluation checklist

不适用。

## 19. Final dataset build and interactive judge checklist

不适用。

## 20. Bounded corpus-to-runtime handoff checklist

不适用。

## 21. Repository placement and operational layout checklist

- [x] Repository placement 和 Project Container semantics 不变。
- [x] 仅隔离 linked worktree发生 source/docs/test 修改。
- [x] 不运行 real-host、closure publication 或 Issue #39 path。

## 22. Issue #110 Solo Maintainer Closure checklist

- [x] Closure public seam 与十文件 package inventory 不变。
- [x] 五个 hosted checks、ruleset id/name/target/enforcement、empty bypass、classic
  absence 和 canonical configuration 均保持 strict。
- [x] 唯一新 wire compatibility 是 zero approvals 下 exact `true` 的
  unattributed-approval default。
- [x] Python token custody、fixed GET endpoints、sanitized environment、no cache 和
  content-free failure contract 不变。
- [x] Closure仍为一名 operator、零 independent reviewer、零 external signer、
  零 Issue #38 approval 和零 Issue #39 authority。

## 23. 执行后记录

```text
实际修改文件:
- AGENTS.md
- backend/r2_solo_maintainer_closure/github_guardrail.py
- docs/constraints/{architecture_constraints,ci_guardrails,linter_constraints,mechanical_rule_translation,tooling_constraints}.md
- docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md
- docs/decisions/0011-authenticated-github-guardrail-observation.md
- docs/operations/{project_status_log,project_structure,r2_solo_maintainer_closure_runbook,testing_checklist}.md
- docs/operations/r2_github_guardrail_unattributed_approval_compatibility_task_brief.md
- docs/security/project_container_cutover_contracts.md
- docs/templates/agent_task_brief_template.md
- scripts/generate_project_status.py
- tests/test_{architecture_constraints,generate_project_status,mailbox_transport_constraints,mechanical_rule_constraints,multimodal_documentation_contracts,static_linter_constraints}.py
- tests/test_r2_solo_maintainer_closure_architecture.py
- tests/test_r2_solo_maintainer_github_guardrail.py

测试结果:
- RED: 新 exact-true/zero-approval public-seam test 按预期以 fixed guardrail code 失败。
- GREEN: guardrail focused file 19/19；初始 constraints/status 集合 152/152；status generator 35/35。
- maintenance scan exit 0，仅 22 个既有 low stale-draft 提示；repository leakage scan 和 compileall exit 0。
- 初始 full discovery: 2848 tests / 4 failures / 4 skipped / 6061.666s。三个本轮契约同步失败已修复并定向 3/3 通过；剩余 Issue #39 Windows fixture 失败已转入独立任务简报处置。
- 独立 Issue #39 fixture 修复在 LF-preserving worktree 中以显式 fixture-only 内容差异取代 EOL 差异；精确 production-flow 测试先 RED 7.095s，再 GREEN 1432.983s 并完成 27 actions。
- 最终 full discovery: 2848 tests / 4 skipped / 7516.969s，`OK`，无 failure/error。
- 修复后 focused/constraint/cross-contract 集合 185/185；review 调整后 guardrail/mechanical/static 集合 67/67；`git diff --check` exit 0。
- LF output RED/GREEN 证明 Windows status generation 从 CRLF 改为固定 LF；generator/mailbox safety 集合 37/37，25 个变更文件 raw CRLF count 为 0。
- Matt Standards review: 0 hard findings，两个重复导航/读取 judgement calls 已修复；Spec review: 0 scope/logic findings。

未完成事项:
- 本地实现与 full-suite 验证已完成；publication batch 已授权，执行结果待记录。
- 未运行或重试 live `prepare`、`confirm`、protected verifier、Issue mutation 或真实 cutover。
- 尚未 stage、commit、push 或创建 draft PR；未执行 merge。

后续建议:
- 完成已授权的精确 publication batch，并在 PR 建立后同步 task brief、状态日志和 PR metadata。
- publication/merge 完成后，任何 fresh closure ceremony 仍需独立行动时授权。
```
