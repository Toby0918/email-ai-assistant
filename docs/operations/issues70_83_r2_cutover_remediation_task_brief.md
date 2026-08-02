---
last_update: 2026-08-02
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: task_brief
---

# Issues 70-83 R2 Cutover Remediation Task Brief

## 1. 任务名称

Implement the dormant R2 Project Container cutover remediation from Issue #70
through Issue #83.

## 2. 任务类型

```text
feature | security | test | docs
```

## 3. 当前状态

```text
complete
```

## 4. 任务目标

在 governing baseline
`ce039b9188587bbb3f8c9950b228b79910dda429` 上依次实现 #70-#83，把 Spec #69
批准的 R2 设计落实为 complete but dormant、可在 caller-owned synthetic Windows
sandbox 中验证的生产表面。真实 operator entry 在 Issue #39 获得单独授权前继续固定返回
`BLOCKED_NO_APPROVED_COMMAND`，并执行零次真实主机操作。

## 5. 非目标

- 不批准、关闭、改写或重新标记 #38、#50、#69 或 #39。
- 不启动或实现 #39，不执行真实 preflight、publication、cutover、resume、rollback 或 audit。
- 不读取或修改真实 Repository Root、linked worktree、ACL、Runtime、SQLite、CRX、Config、service 或 evidence package。
- 不访问 provider、mailbox、vault、credential、private store、private data、parent project 或 finance project。
- 不提供 external private issuer，不在仓库中生成或保存 private signing key。
- 不添加 umbrella command、caller-selected path/Profile/journal/target、force、shell、PowerShell 或 arbitrary Git command surface。
- 不执行 cleanup、delete、overwrite、clone、fetch、reset、stash、prune、repair 或 remote-dependent recovery。
- 不更改正常邮件分析 API、SQLite schema、browser、prompt、provider routing、private knowledge、mailbox、cleanup 或 scheduler 边界。

## 6. 背景与依据

- GitHub Spec #69 and implementation tickets #70-#83.
- Issue #38 remains the approval surface; #50 is historical prerequisite context; #39 remains unstarted.
- PR #68 merged as `ce039b9188587bbb3f8c9950b228b79910dda429`.
- Accepted prototype fingerprint
  `2923d0940a609b8bb2f9112ba1c1708511de44bd8ecf8611b45603fcbbe49af1`
  is non-authorizing feasibility prior art only.
- `AGENTS.md`, `CONTEXT.md`, `docs/security/project_container_cutover_contracts.md`,
  `docs/constraints/tooling_constraints.md`,
  `docs/constraints/architecture_constraints.md`, and
  `docs/constraints/linter_constraints.md` govern implementation.

## 7. 涉及范围

预计新增或修改：

- `backend/cutover_*` dormant contracts, process roots, journal/state, host-role adapters, managed-publication, lifecycle, audit, and recovery modules.
- `scripts/` only for the three separately fixed operator process entrypoints when required by the ticket.
- `tests/` synthetic public-contract, OS-process, authorization-domain, audit, Windows sandbox, crash-gap, architecture, mechanical, leakage, and full-lifecycle coverage.
- `docs/security/`, `docs/constraints/`, `docs/operations/`, CI guardrails, and project status contracts where explicitly required.

## 8. 技术方案

1. #70 adds canonical immutable R2 vocabulary without changing executable behavior.
2. #71-#73 expose physically separate fixed-verb preflight, evidence, and transaction processes with real-TTY hidden single-use authorization ingress and default real-host locking.
3. #74-#80 implement representative-to-complete repository/ACL, service quiescence, independent managed-unit publication, and independent audit slices in fresh test-owned sandboxes.
4. #81 composes the two-start provider-disabled validation lifecycle.
5. #82 adds journal-derived cross-stage tri-state recovery and final sealing.
6. #83 contracts obsolete R2-reachable paths and proves all four highest seams in one fresh physical NTFS sandbox, while portable tests make no Windows-evidence claim.
7. Each ticket uses vertical RED -> GREEN cycles through its public seam and receives an independent Conventional Commit.

## 9. 数据结构或接口变化

### 数据库变化

No public or production SQLite schema change. Synthetic database state is test-owned only.

### API 变化

No normal HTTP API change. New operator process surfaces are fixed-verb, pathless, and default locked.

### AI 输出 JSON 变化

None.

### Prompt 变化

None.

## 10. 安全与隐私检查

- [x] 不读取真实邮箱数据。
- [x] 不自动发送、删除、归档邮件。
- [x] 不在前端保存或暴露 API key。
- [x] 不改变邮件正文的不可信输入边界。
- [x] 不改变 AI JSON 校验边界。
- [x] public output、receipt、repr、stdout、stderr、log 和 exception 只包含固定 status 与 allowlisted aggregate counts。
- [x] 测试样本只使用 synthetic names、identities、bytes、Git objects、SQLite、Config、service、authorization 和 receipts。

## 11. Prompt Injection 防护

不改变正常分析路径；operator surfaces 不接受邮件正文、自由文本或可执行命令。

## 12. 验收标准

1. #70-#83 的每项 GitHub acceptance criteria 均由 public-seam tests 和相应实现覆盖。
2. 三个 operator roots 物理分离、无 umbrella selector；四个 authorization domains nominally distinct 且 receipts never authorize.
3. 每个 mutation 前有 durable intent；pending effect 只分类为 `EFFECT_ABSENT_EXACT`、`EFFECT_PRESENT_EXACT` 或 `EFFECT_AMBIGUOUS`。
4. rollback 唯一成功为 `LEGACY_FLAT_LAYOUT_RESTORED`；final success 仅在独立 audits fresh 后追加 `CUTOVER_SUCCESS`。
5. 所有真实 entry 在 #39 前保持 `BLOCKED_NO_APPROVED_COMMAND` 与 zero host operations。
6. focused、affected、architecture、mechanical、documentation、maintenance、leakage、full-suite、Standards 和 Spec gates 全部通过。

## 13. 测试计划

- 每个 Issue 先运行 focused RED，再用最小 production implementation 变 GREEN。
- 定期运行受影响的 contracts/journal/composition/Windows synthetic suites 与 `compileall`。
- 每个 Issue 提交前运行其 focused/affected/architecture/mechanical/leakage gates。
- #83 后运行 `python -m unittest discover -s tests`、maintenance scan、repository leakage scan、diff checks，并执行 Standards/Spec 双轴评审和修复复审。
- Windows-specific claims only come from fresh caller-owned NTFS sandboxes; portable suites must state no NTFS/ACL/TTY/process-isolation claim.

## 14. 回滚方案

每个 Issue 使用独立 Conventional Commit；如后续票据发现回归，仅通过新的修复提交恢复，不重写历史，不触碰根目录用户改动，不使用 destructive Git commands。

## 15. 需要人工确认的问题

```text
None. The Issue bodies and Spec #69 define the approved public testing seams and fail-closed boundaries.
```

## 16. 执行前检查

- [x] 已阅读 `AGENTS.md`、`CONTEXT.md` 和 project status log。
- [x] 已阅读 tooling、architecture、linter constraints。
- [x] 已读取 Spec #69、#70-#83 与 #38/#39/#50 实时状态。
- [x] 已冻结 live `origin/master` 为 `ce039b9188587bbb3f8c9950b228b79910dda429`。
- [x] 已建立 isolated sibling `codex/issues-70-83-r2-remediation` worktree。
- [x] 已确认不触碰真实邮箱、provider、密钥、客户数据或真实 cutover host。

## 17. Remote provider private-context checklist

Not applicable: no remote-provider input, runtime private knowledge, privacy transformation, or provider budget change. Provider-disabled behavior remains exact and is verified synthetically.

## 18. Administrator stage-evaluation checklist

Not applicable.

## 19. Final dataset build and interactive judge checklist

Not applicable.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable.

## 21. 执行后记录

```text
实际修改文件：
- Issues #70-#82: thirteen independently committed dormant production slices,
  their focused synthetic/Windows/architecture tests, and synchronized
  security/tooling/architecture/linter contracts.
- Issue #83: `backend/r2_verification_evidence/`, fixed synthetic verifier and
  support scripts, full-topology/semantic-matrix/obsolete-surface tests,
  verification criteria/evidence, project constraints, testing/CI/structure
  guidance, and generated project status.

测试结果：
- Fixed verifier: `R2_SYNTHETIC_VERIFICATION_COMPLETE` and `CUTOVER_SUCCESS`;
  70 semantic gaps, 11 worktrees, 4 managed units, 4 authorization domains,
  3 real-TTY process types, 2 independent audits, and zero provider attempts,
  leakage findings, or real-host operations.
- Final evidence fingerprints: criteria
  `66231770c6d8285f82fae279ce545ef9b60d65d6a398a4a84070e6837a697af7`,
  surface `1f9608611e2454869792dfb4956c074a4d28d7b7e1136fae14970fa2435c9bd6`,
  and package
  `ae741bdd012bea76e2037b32a137ac26b8d96c79bcc734e8634f2095f97d55bc`.
- Final actual-gate/evidence focused set: 26 passed.
- Complete R2 affected suite: 163 passed in 686.776 seconds.
- Final full suite: ran 2557 in 2470.624 seconds, `OK (skipped=3)`.
- Architecture, static, mechanical, status, diff, and exact
  consumer-allowlist gates passed on the final bytes.
- Maintenance: 18 pre-existing low `stale_doc` findings, zero high findings.
- Repository leakage scan: passed with zero findings.

未完成事项：
- The initial Standards/Spec dual review found authorization-gate, audit
  provenance, real-process lifecycle, durable-head, exact-manifest, semantic
  matrix, transitive-surface, physical-topology, quiescence-order, durable
  receipt, semantic-effect, and actual fresh-gate gaps. Those P1/P2 findings
  were repaired. Final Standards and Spec re-reviews are both `CLEAN`.
- No required work remains inside the authorized #70-#83 implementation slice.

后续建议：
- Re-review Issue #38 against the final merged master in a separate approval task. Do not start #39 from this work.
```
