---
last_update: 2026-08-08
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 Solo Maintainer Closure implementation task brief

## 1. 任务名称

Implement Issue #110 Solo Maintainer Closure V1 and dormant Execution Confirmation V1.

## 2. 任务类型

```text
security
```

## 3. 当前状态

```text
in_progress
```

## 4. 任务目标

在冻结的 `master` commit
`8f12b21a7597b7ffa51422bfef3e38047e20153a`、tree
`feefb8c29a832fcf2def11b95a8a5ef244d893c9` 上，以
`ISSUE110-PROPOSAL-V1` 精确替换不可满足的外部签名 closure 模型。新增一个
`SoloMaintainerClosure.prepare()` / `confirm()` 深模块，并把后续 production
command authority 迁移到 V3 binding 与尚不可达的 fresh real-TTY Execution
Confirmation primitive。

## 5. 非目标

- 不创建、修改、禁用或删除 GitHub ruleset/classic branch protection。
- 不运行 live closure `prepare`、`confirm` 或 protected verifier。
- 不修改、关闭或重新标记 Issue #105、#38 或 #39。
- 不启用任何 #39 command，不触达真实主机、provider、mailbox、vault 或私有数据。
- 不读取、生成、保存或使用 private key，不保留 V1 signature/envelope fallback。
- 不 push、不创建 PR、不 merge；发布与所有 GitHub-state mutation 另行批准。
- 不 cleanup、overwrite、delete 或迁移任何 existing/stage/legacy artifact。
- 不修改批准的 Add/Modify/Delete allowlist 之外的路径。

## 6. 背景与依据

Issue #105 的 original external-signature contract 从未满足: 项目只有一个
maintainer，没有 approved independent reviewer、external signer 或十四个 gate
private keys。#110 诚实记录 `SOLE_MAINTAINER_SELF_REVIEW`，并保持
`independent_reviewer_count=0`、`external_signer_count=0`、
`issue39_authority_count=0`。

实现依据:

- `AGENTS.md`
- Issue #110 body
- `ISSUE110-PROPOSAL-V1` comment body SHA-256
  `5a2dcff2e3d7274b29fe75c4e46acc8ef8fadda1e0b3a30076632947f73ab956`
- #110 exact allowlist amendment 01, comment `5217097480`, body SHA-256
  `11cb2844a39ed2ac383e7efaf1bd5d5e60d4391bf99136475f24eba494216ec8`
- #110 exact allowlist amendment 02, comment `5218863665`, body SHA-256
  `bcc4fa392d17019ce91d99d8d245f8f9af076bfc1868fa255dd5b2c5f8c91507`
- #110 exact allowlist amendment 03, comment `5219249614`, body SHA-256
  `a98b090f0443ae01616d36e5e70903dcab6e942da5c2c24aa70a80b5d26e7ae4`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/constraints/ci_guardrails.md`
- `docs/security/project_container_cutover_contracts.md`

## 7. 涉及范围

实施范围严格等于 #110 proposal 第 6 节的 exact Add/Modify/Delete 集合:

- 新增 `backend/r2_solo_maintainer_closure/` 九个固定文件、一个
  `backend/r2_production_binding/execution_confirmation.py`、一个固定 CLI、五个
  test modules、一个 fixture、两个 operations 文档和 ADR 0010。
- 修改批准的 production binding/composition、三条 process、journal genesis、
  runbook、verifier、status generator、约束/安全/状态文档和 guard/affected tests。
- 删除旧 `backend/r2_final_master_closure/`、
  `backend/r2_external_artifacts_v1/`、旧 preparation CLI、旧 active issuance
  runbook、旧 signature/closure tests、三条 legacy entry/fixture 与
  operator envelope/dormant context。

任何额外路径都属于 contract change，必须停止并请求新的 allowlist decision。

Amendment 01 另批准将以下 retained V2 consumers 加入 Modify 集合，以便在不保留
V2 alias/dual parser 的前提下迁移到 V3 binding/Execution Confirmation:

```text
backend/r2_foundation_publication_v2/plan.py
backend/r2_foundation_publication_v2/progress.py
backend/r2_managed_unit_publication_v2/plan.py
backend/r2_managed_unit_publication_v2/progress.py
backend/r2_managed_unit_publication_v2/recovery.py
backend/r2_operator_runbook_v2/receipt.py
backend/r2_repository_manifest/git_byte_receipt_v2.py
backend/r2_repository_manifest/git_byte_state_v2.py
backend/r2_retention_ledger_v2/ledger.py
backend/r2_retention_ledger_v2/proof.py
backend/r2_rollback_recovery_v2/evidence.py
backend/r2_rollback_recovery_v2/plan.py
backend/r2_rollback_recovery_v2/progress.py
backend/r2_rollback_recovery_v2/seal.py
backend/r2_transaction_journal_v2/inspection.py
backend/r2_transaction_journal_v2/journal.py
backend/r2_transaction_journal_v2/record.py
backend/r2_two_start_validation_v2/evidence.py
backend/r2_two_start_validation_v2/plan.py
backend/r2_two_start_validation_v2/progress.py
backend/r2_two_start_validation_v2/seal.py
```

Amendment 02 另批准以下 Modify 路径:

```text
tests/test_cutover_contract_architecture.py
```

Amendment 03 另批准一个 private local-evidence module 和两个 CI suite registry
Modify 路径；它不增加 public caller evidence、workflow、GitHub mutation 或 Issue #39
authority:

```text
backend/r2_solo_maintainer_closure/local_evidence.py
backend/r2_ci_provenance_v2/suites.py
tests/test_r2_ci_provenance_v2.py
```

Amendment 04 另批准以下 Modify 路径，以补齐 rollback/recovery crash-matrix
调用所需的 dual-clock observation:

```text
tests/test_r2_rollback_recovery_v2_crash_matrix.py
```

Amendment 05 另批准以下 Modify 路径，以同步本次架构边界到任务简报模板:

```text
docs/templates/agent_task_brief_template.md
```

Amendment 06 不增加路径；它澄清 publication 的 linearization point 是 final stable
parent/child/DACL/oplock observation，immediately followed by the exact-target
no-replace rename。Arbitrary legacy/other-stage sibling created
strictly after that linearization is classified as a subsequent incident rejected by
the verifier。本实现作 no atomic arbitrary-sibling exclusion claim against an
uncooperative writer，也不授权 Git-common DACL mutation, kernel filter, or volume lock。

Amendments 04、05、06 已记录在 #110 comment id `5224508400`，comment body SHA-256
为 `8d23bc6aa9f0ddb7ef1f233c5b848db17c8c3c7a8c5824d714af73861cc313c7`。
Amendment 07 另批准以下 Modify 路径，使 rollback/recovery architecture guard 接受
private local evidence 对冻结源码 blob 的只读绑定；该模块不导入或调用 rollback
runtime:

```text
tests/test_r2_rollback_recovery_v2_architecture.py
```

Amendment 07 已记录在 #110 comment id `5224816599`，comment body SHA-256 为
`e0b9c955f6bf7909f8e099000ad0744574024d8b0d2b0b29fd08bad3f5c4320b`。
Amendment 03 后的历史 checkpoint 为 179 paths (`A20/M120/D39`)；
七次 amendment 后的精确集合为 182 paths (`A20/M123/D39`)。

## 8. 技术方案

1. 以 strict canonical ASCII JSON 和 domain-separated SHA-256 构造 closed
   candidate、manifest、hosted/guardrail/local evidence 与 attestation receipt。
2. `SoloMaintainerClosure` 内部固定 repository/GitHub/storage ports；public API
   只暴露无参数 `prepare()` 与两个 exact string 参数的 `confirm()`。
3. `prepare()` 只读且不写；`confirm()` fresh rederive、验证 Windows 三 console
   handle、双时钟 300 秒半开窗口、两个一次 visible exact inputs，并 create-only
   发布 manifest + receipt。发布在 final stable parent/child/DACL/oplock observation
   后以 exact-target no-replace rename 线性化；失败保留 partial stage，绝不自动清理。
4. no-arg isolated verifier 只接受新 fixed directory 的两份 canonical 文件，并在
   current Git/ruleset/hosted evidence revalidation 后最多返回
   `ELIGIBLE_FOR_ISSUE38_FINAL_REVIEW`；拒绝所有 legacy V1 输入。
5. `ApprovedCutoverBindingV3` 删除 public-key/signature/envelope fields；
   `ExecutionConfirmationCandidateV1`/`ClaimV1` 是纯、single-action、current-journal
   bound、fresh real-TTY contract primitive。
6. preflight/evidence/transaction production roots 在 TTY、candidate、artifact 或
   Adapter 之前无条件返回 `DORMANT_NO_ISSUE39_APPROVAL`。本轮代码图不存在 unlock
   path；future #38/#39 需要独立 exact code allowlist。
7. 保留 #104 Adapter owning-module identity/reverification、real-host preflight、
   rollback/recovery、retention/no-deletion 和 provider-disabled 边界。

## 9. 数据结构或接口变化

### 数据库变化

无。

### API 变化

无 public HTTP/API 变化。Repository-internal API 由 V1 external signature 与 V2
authority envelope 替换为 `SoloMaintainerClosure`、`ApprovedCutoverBindingV3` 和
dormant `ExecutionConfirmationV1`。

### AI 输出 JSON 变化

无。

### Prompt 变化

无。

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除、归档邮件。
- [x] 不在前端或 repository surface 保存/暴露 API key 或 private key。
- [x] 不改变邮件/AI/runtime/provider 数据流。
- [x] 日志、errors 与 CLI failure output 仅使用 fixed content-free code。
- [x] 测试只使用 synthetic、temporary、offline evidence。
- [x] 不触达 real host、mailbox、vault、provider、private store 或 ignored data。
- [x] create-only publication 不 overwrite/delete/cleanup existing state。

## 11. Prompt Injection 防护

不适用。本任务不读取邮件正文、不调用 AI、不处理 prompt，也不改变现有不可信
邮件输入边界。

## 12. 验收标准

1. exact new schemas、domains、status、acknowledgements、300 秒 freshness、TTY facts
   和 assurance counts 均由 focused tests 验证。
2. hosted checks、workflow bytes、ruleset snapshot、frozen Git bytes 与 typed local
   evidence 在 prepare/confirm/verifier 三处 fail closed。
3. publication fixed/create-only/no-clobber；linearization boundary、后续 sibling
   incident 与非原子 arbitrary-sibling exclusion 限制符合 Amendment 06；legacy
   target/stage/V1 artifact 不迁移、不兼容、不读取、不删除。
4. V3 binding 无 public keys/signatures/envelopes；Execution Confirmation 绑定 one
   action/current journal head/sequence/reverse plan，并保持 production unreachable。
5. 三条 production roots 精确返回 `DORMANT_NO_ISSUE39_APPROVAL`，且在任何输入、
   clock、TTY、candidate、claim 或 Adapter 前返回。
6. exact A/M/D name-status 集合与批准 allowlist 完全相等。
7. focused、affected、architecture、mechanical、documentation、maintenance、leakage、
   compile 和 full suite 全过；Standards/Spec review 均 CLEAN/PASS。
8. #105 original contract 明确为 never passed/superseded historical evidence；#38/#39
   仍 open/blocked 且 authority count 为零。

## 13. 测试计划

- 先为五个 pre-agreed seams 写 behavior-first RED tests，再实施最小 GREEN。
- 反复运行 focused modules 和受影响单文件 tests。
- 定期运行 `compileall` 作为 Python type/syntax gate。
- 运行 proposal 第 8 节全部 affected、guard、documentation 与 security tests。
- 运行 maintenance scan，要求 `high=0`；运行 leakage scan，要求 `total=0`。
- 生成 project status 后重跑 documentation/status、maintenance、leakage 与 full suite。
- 最终运行 pinned `.venv` 的完整 `unittest discover -s tests` 两次。

## 14. 回滚方案

未发布实现仅在本隔离分支继续 forward patch；不 reset/rebase published history。
合并后的 defect 只能在 #110 exact allowlist 内另做 forward corrective change。
Contract-changing finding、baseline drift、extra path 或 protection drift 必须停止。
不通过删除 ruleset、target、stage、legacy artifact 或 evidence 来回滚。

## 15. 需要人工确认的问题

无。`ISSUE110-PROPOSAL-V1` 已获 exact approval，#110 已获 Agent implementation
authorization；本轮用户点名 `$implement` 另行授权按该 skill 在隔离分支 commit。
Push、PR、ruleset、live closure、#105/#38/#39 仍未授权。

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md` 与适用 skills。
- [x] 已阅读 project status 与 tooling/architecture/linter/mechanical/CI/docs 规则。
- [x] 已复核 #110 label/state/comments 与 #105/#38/#39 不变。
- [x] 已复核 remote master/tree、五个 hosted checks、ruleset `[]` 与 classic 404。
- [x] 已在独立 `codex/issue-110-solo-maintainer-closure` worktree 冻结基线。
- [x] 已确认不触碰真实邮箱、密钥、客户数据、真实主机或 GitHub protection。
- [x] 已确认 exact file scope 和 stop conditions。

## 17. Remote provider private-context checklist

不适用。本任务不改变 remote AI input、runtime knowledge、privacy transformation 或
provider budget；provider 默认与所有现有 runtime boundaries 保持不变。

## 18. Administrator stage-evaluation checklist

不适用。

## 19. Final dataset build and interactive judge checklist

不适用。

## 20. Bounded corpus-to-runtime handoff checklist

不适用。

## 21. Repository placement and operational layout checklist

- [x] Repository placement、Project Container 和 protected-root semantics 不变。
- [x] 本实现不执行 real preflight/evidence publication/migration/cutover/recovery。
- [x] #104 Adapter identity 与三 physical production roots 保持隔离。
- [x] 所有 real constructors 在 Issue #39 前无条件 dormant。
- [x] receipts/evidence 不是 authorization；#38/#39 不自动批准或执行。
- [x] rollback/recovery/retention/no-deletion mechanics 不削弱。

## 22. 执行后记录

完成验证与 code review 后填写实际 modified paths、测试结果、未完成外部步骤和后续
separate approval boundaries。
