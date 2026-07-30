---
last_update: 2026-07-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Mechanical Rule Translation

本文件定义如何把人工 code review 中反复出现的主观要求，翻译成可执行、可检测、可由 CI 阻止的机械规则。

核心原则：

```text
如果一条规则在 code review 中被提及超过 3 次，就应该被写成 linter 规则或可执行测试。
```

## 1. 为什么需要机械规则

人工 review 适合判断设计质量、业务理解和异常场景，但不适合反复提醒同一类低级错误。

如果同一问题反复出现，说明它不应该继续依赖人工记忆，而应该进入：

```text
docs/constraints/
tests/
CI pipeline
```

这样 Agent 下次犯同类错误时，CI 会直接失败，并给出修复提示。

## 2. 三次提及规则

同一类 code review 评论累计出现次数达到 3 次后，必须执行以下动作：

```text
1. 在 docs/templates/code_review_rule_register.md 记录该规则。
2. 判断该规则是否可以机械化检查。
3. 如果可以机械化检查，新增或更新 tests/ 中的约束测试。
4. 如果暂时不能机械化检查，写入 docs/operations/review_checklist.md。
5. 更新 docs/constraints/mechanical_rule_translation.md 或相关约束文档。
6. 将该检查加入 CI。
```

## 3. 主观规则到机械规则的翻译表

| 人工 review 说法 | 机械化规则 | 推荐实现位置 |
|---|---|---|
| 方法太长 | 单个 Python 函数不超过 50 行 | `tests/test_mechanical_rule_constraints.py` |
| 文件太长 | 单个后端 `.py` 文件不超过 300 行 | `tests/test_mechanical_rule_constraints.py` |
| 日志不规范 | 禁止裸 `print()`、禁止 `traceback.print_exc()` | `tests/test_static_linter_constraints.py` |
| 异常处理太随意 | 禁止裸 `except:` | `tests/test_static_linter_constraints.py` |
| 前端不该碰密钥 | `frontend/` 禁止出现环境变量读取和密钥关键词 | `tests/test_static_linter_constraints.py` |
| 前端不该直接调 AI | `frontend/` 禁止出现 OpenAI 直接调用痕迹 | `tests/test_static_linter_constraints.py` |
| 不要自动处理邮箱 | 禁止自动发送、删除、归档邮件关键词 | `tests/test_static_linter_constraints.py` |
| 架构层次乱了 | 禁止指定模块之间的反向依赖 | `tests/test_architecture_constraints.py` |
| 文档缺少维护信息 | `docs/*.md` 必须包含 YAML front matter | `tests/test_static_linter_constraints.py` |
| 依赖版本冲突 | 同一规范化包名不得出现不同的 `==` 版本 | `tests/test_repo_utils.py` + `tests/test_static_linter_constraints.py` |
| AI 输出不稳定 | AI 结果必须可解析、可校验 JSON | analyzer 相关单元测试 |
| Prompt 边界不清 | Prompt 文档必须写清输入、输出、限制、安全边界 | 文档测试或 review checklist |
| 安全边界被改了 | 修改安全边界必须同步更新 docs 和测试 | CI + review checklist |

## 4. 机械规则设计要求

一条好的机械规则必须满足：

```text
可检测：可以用脚本、AST、正则、schema 或单元测试检查。
可解释：失败信息能说明哪里错。
可修复：失败信息能告诉 Agent 怎么改。
可追踪：能指向对应 docs 文档。
可维护：规则不应过度复杂，不应误伤大量正常代码。
```

## 5. Linter 报错格式

所有自定义机械规则失败信息应尽量使用以下格式：

```text
❌ 什么错：说明违反了哪条规则。
✅ 怎么改：给出最小修复方式。
📖 去哪里看：指向对应 docs 文件。
```

示例：

```text
❌ 什么错：backend/email_agent/api.py 中函数 analyze_current_email 超过 50 行。
✅ 怎么改：拆分请求校验、分析调用和响应构造逻辑。
📖 去哪里看：docs/constraints/mechanical_rule_translation.md
```

## 6. 不能机械化的规则怎么办

不是所有 review 评论都适合立刻变成 linter。  
例如：

```text
这个回复语气不够专业
这个分类规则不够符合业务
这个功能体验不够自然
```

这类问题应先写入：

```text
docs/operations/review_checklist.md
docs/knowledge_base/reply_guidelines.md
docs/knowledge_base/email_categories.md
```

如果后来能总结出明确规则，再翻译成机械检查。

## 7. 规则生命周期

每条机械规则应经历以下状态：

```text
observed
candidate
active
deprecated
```

含义：

```text
observed: code review 中已经出现，但次数不足 3 次。
candidate: 已出现 3 次，正在准备规则化。
active: 已经写入 docs、tests 和 CI。
deprecated: 已不再适用，仅保留历史参考。
```

## 8. Agent 执行要求

Agent 在每次修复 review 评论时必须判断：

```text
这是否是重复出现的问题？
是否已经出现 3 次？
是否可以转成 linter 规则？
需要更新哪个 docs 文件？
需要新增或修改哪个测试？
```

如果用户明确说“这个问题以后不要再犯”，Agent 应优先考虑把它写入机械规则。

## 9. Write-only current-evidence rule

The write-only current-evidence boundary is executable, not a review convention.
`tests/test_current_evidence_handoff.py` proves strict synthetic contract
validation, immutable/redacted values, one append call, and fixed content-free
failures. `test_current_evidence_handoff_is_contract_only_and_write_only` in
`tests/test_architecture_constraints.py` pins the exact package import allowlist,
single public append function, exact import bindings and call-target allowlists,
the fixed full binding-inventory fingerprint (including Store counts and non-name
mutation targets), forbidden-capability references, reader/store/mailbox/authority
markers, and the public exports. Alias, rebinding, augmented/type-alias/global/
delete forms, and dynamic call construction therefore fail even when a forbidden
receiver name is hidden. The handoff function body is structurally pinned to
validated construction, exactly one `append(evidence)` try/except, and a fixed
result, so raw input cannot replace the immutable contract. The
mailbox transport suite tokenizes every administrator script and root wrapper plus
executable normal API, frontend, cleanup, local-service, and workflow surfaces. It
includes surface-root-relative module paths, executable docstrings, bytes,
reassigned/deep-chain constants, constant-valued f-strings, literal `join` calls,
Python format/percent forms, folded single- and multiline Python/frontend literal
concatenations, JS array joins/templates, and decoded constant JS escapes,
path-inherited mailbox context, compact lowercase compounds, natural sync
morphology, contextual refresh/delta/pull/update aliases, quote style,
snake/kebab/camel case, imports, and routes. Only direct
literal status prose at the canonical generator path is ignored, and only while
the sole `build_project_status` call flows through the exact consecutive `Path`
output binding, fixed parent creation, and `output.write_text` statements in
`main`, with exactly one `output` Store, no rebinding, one module-level function
definition, and one direct Load reference. The administrator CLI constants, unique
parser attribute/call, exact command loop, `build_parser` AST, reflection strings,
binding/mutation targets, and runtime choices are also pinned; semantic aliases
such as refresh/delta/pull/update cannot extend issue #10. Contract placeholder and
residual scans use the NFKC validation view, closing compatibility-form PII escapes.
The static-linter governance test keeps the API, security, tooling, logging, task
template, and project-structure descriptions synchronized.

## 10. Project Container protected-root rule

The Project Container boundary is executable. `tests/test_project_layout.py`
proves that `ProtectedLocationPolicy` has no public arbitrary-root constructor,
revalidates Managed/Standalone/flat identity, preserves one Managed container
root, rejects partial Managed placement, and checks original plus resolved
candidate views. Focused private-knowledge, private-evaluation, mailbox-vault,
recovery, and sales-policy tests enumerate the container, `main`, all eight
sibling zones, and descendants while retaining positive synthetic external
cases. A separate cross-domain matrix supplies a validated Standalone placement,
rejects its state root, and retains valid stores outside both Standalone roots;
this policy-only test does not enable any Standalone private capability.

`test_protected_location_policy_has_only_reviewed_internal_consumers` pins the
exact `backend.project_layout` importer list and the narrower exact
`ProtectedLocationPolicy` consumer list, and rejects calls to its private
factory outside the package. `test_public_runtime_and_cli_cannot_supply_protected_roots`
rejects environment names and CLI options that could provide or narrow the
roots. API behavior tests remove `protected_roots` and `project_container`
before both analyzer routes. Private-evaluation keeps a single exact
`backend.project_layout` allowlist entry; no broader backend dependency is
introduced.

Issue #32 adds only `backend/email_agent/managed_runtime.py` to the exact project
layout importer list; it does not enter the narrower
`ProtectedLocationPolicy` consumer list. `tests/test_managed_container_mode.py`
and `tests/test_run_local_debug.py` pin the boolean-only
`--managed-container` route, approved zone mappings, Config key allowlist,
provider-disabled injection, main-root cwd/script, and synthetic
start/health/analysis-persistence/stop behavior. The existing public-surface
guard continues to reject `--project-container` and environment/config aliases
for protected roots.

## 11. Manual content-free ContainerAudit rule

Issue #34 translates the manual audit boundary into three executable layers:

1. `tests/test_container_audit*.py` exercises only strict synthetic evidence
   through `run_container_audit(policy=..., adapters=...)`. It pins exact
   policy/evidence types, seven injected callbacks, two stable reads, fixed
   pass/fail results, first-error short circuit, and every adapter's positive
   and negative paths.
2. `test_container_audit_has_only_pure_injected_metadata_capability` pins the
   exact package file list, standard-library import allowlist, and forbidden
   host/content/mutation calls. Adding a CLI, default adapter, host probe,
   content reader, logger, scheduler, repair helper, or composition root fails.
3. `test_container_audit_has_no_runtime_or_workflow_consumer` recursively
   rejects audit references from every other backend module, all scripts
   including maintenance/leakage tooling, root wrappers, frontend/browser
   files, and workflows, except the exact Issue #36 synthetic bridge and the
   exact Issue #53 read-only `backend/real_host_preflight/audit_bridge.py`.
   The #53 bridge only binds the existing seven callbacks; it cannot change
   the nine-zone policy or add host imports to the audit core.

These checks deliberately do not expand repository leakage scanning above the
Repository Root and do not make maintenance scanning traverse the Project
Container. Executable real preflight and post-cutover audit remain separately
approved boundaries. Issue #53 may compose its locked read-only bridge and
readiness proof, but it may not run a pre-cutover final audit or claim that the
future final layout passed.

## 12. No-clobber migration evidence package rule

Issue #35 translates evidence preservation into four executable layers:

1. `tests/test_migration_evidence_review.py`,
   `test_migration_evidence_policy.py`, and
   `test_migration_evidence_git_guardrails.py` pin exact review inputs,
   sanitized local Git discovery with incrementally bounded stdout and
   whole-process-tree timeout cleanup, content-free Git/ACL/volume baselines,
   root/linked worktree selection, special-index rejection, ancestor-bound
   source reads, and the mechanical inclusion/exclusion veto before content
   reads. `test_migration_evidence_process_tree.py` additionally proves
   suspended-create/job-assign/resume ordering and fail-closed cleanup on
   Windows, plus process-group closure before parent reap on POSIX. The
   verifier independently replays the same veto instead of trusting manifest
   labels.
2. `test_migration_evidence_restore.py` creates only temporary synthetic
   repositories, bundles exact local refs, restores staged/unstaged index and
   worktree layers plus deletion/rename/untracked state, compares porcelain and
   stage records byte-for-byte, verifies objects, and reconstructs linked
   worktree branch/HEAD identity.
3. `test_migration_evidence_no_clobber.py` pins absent-target publication,
   descriptor/stage/parent identity, pre-publication semantic validation,
   partial-write cleanup, stage-swap rejection, and exact commit recognition.
   No test target is inside the real Repository Root or any real worktree.
4. `test_migration_evidence_verification.py`, architecture guards, static
   linter, and repository leakage tests require all Git/host/selection/snapshot
   evidence, canonical manifest and file hashes, independent bundle verify,
   fixed code/count receipts, only the exact Issue #36 synthetic evidence bridge
   plus Issue #53's exact `backend/real_host_preflight/baseline_bridge.py`, and
   no runtime/workflow consumer, a reserved ignored suffix, and name-only
   leakage rejection. The #53 bridge may import only `HostBaseline`; it cannot
   invoke review, creation, publication, verification, or package I/O.

Every backend file remains at most 300 lines and every function at most 50
lines. The module adds no CLI, default target, provider/mailbox/private-store
adapter, service action, real directory migration, ACL mutation, or Issues
#37–#40 implementation. Real review values and package generation are not
automated;
after presenting the exact target, content-free inclusion/exclusion manifest,
reviewed refs, and worktree selection, execution must stop for separate
confirmation.

## 13. Synthetic repository reparenting rehearsal rule

Issue #36 translates the approved temporary rehearsal into four executable
layers:

1. `test_reparenting_rehearsal_contract.py` pins the closed enum/request/result
   contract, complete reviewed choice set, keyword-only no-default public seam,
   and fixed aggregate-only failure before sandbox creation.
2. `test_reparenting_rehearsal_success.py` and
   `test_reparenting_rehearsal_safety.py` build only a marker-bound OS-temporary
   scenario. They prove a non-trivial local branch/ref/remote/ahead baseline,
   approved source hashes, metadata-only excluded canaries, exact Issue #35
   package reads, no-clobber target handling, existing `.git` identity,
   marker plus the sole synthetic scope-control hard-link identity anchor,
   simulated inode-reuse/marker-anchor reparse/non-local-remote rejection,
   repair/recreate preservation, clean linked worktrees, Managed placement,
   preserved public topology and an actual synthetic ContainerAudit pass. The
   anchor is not source content and does not authorize content hard links.
3. `test_reparenting_rehearsal_rollback.py` injects one failure after each of
   the six fixed publication boundaries. Every case must preserve either the
   original source identity or a complete Container moved to the one sibling
   rollback path plus an independently verified Issue #35 package. Tests inspect
   the filesystem and Git state before caller-owned teardown rather than trusting
   the aggregate result; the algorithm has no deletion or overwrite operation.
4. Architecture/static guards pin the exact package files and import roots,
   exact audit/evidence/layout bridges, sole subprocess owner, fixed Git verb
   allowlist, the sole direct `os.link` marker-anchor call while rejecting
   aliases and `Path.hardlink_to`/`Path.link_to`, absence of
   clone/fetch/pull/push/prune/destructive verbs, and zero normal-runtime/script/
   frontend/cleanup/leakage/workflow consumers.

The public seam cannot accept or discover the real Repository Root and does not
clean up any synthetic source, legacy source, worktree, target, or rollback
path. Test-only caller-owned teardown happens after independent assertions.
This rule creates no real evidence package, audit, Container, ACL, runtime,
database or worktree mutation and does not implement Issues #38–#40.

## 14. Synthetic Managed runtime activation rehearsal rule

Issue #37 translates the approved activation rehearsal into five executable
layers:

1. `test_runtime_activation_rehearsal_contract.py` pins the single keyword-only,
   no-default public seam, exact five-field adapter bundle, frozen evidence and
   aggregate-only fixed results.
2. Runtime and Managed-zone tests pin exact Python/SQLite/dependency evidence,
   stable lock identity/hash, sibling fixed-runtime and Windows venv topology,
   actual venv executable binding, exact writable roles and no signing
   capability.
3. SQLite and artifact tests require lifecycle-manager stop plus independent
   `pre_publication` proof, create-only publication, source/destination identity,
   SHA-256, integrity, schema, sidecars, counts, a pre-frozen reviewed CRX hash,
   two destination observations and source preservation.
4. Service tests require one activation token across start, health, exactly one
   user-confirmed persisted `rule_fallback` analysis and the
   `post_activation` stopped proof. The final proof binds the same service,
   rejects stale replay, uses a fresh stop token and precedes final source
   checks；both providers remain disabled with no key/client/private knowledge.
5. Temporary integration and architecture tests bind evidence to actual
   `issue37-synthetic-*` topology, inject every approved failure class, inspect
   source/legacy/competitor preservation, and enforce exact imports plus zero
   real-host consumers.

All evidence version/count fields use exact integer types; `bool` cannot satisfy
them. The production deep module owns no filesystem, SQLite, process, network,
provider, mailbox, vault, private-store, credential, signing, audit, migration
evidence, destructive or cleanup capability. No real activation or migration
evidence package is produced, and Issues #38–#40 remain separate.

## 15. Locked Cutover Profile, authorization, and receipt rule

Issue #51 translates the contract-only cutover boundary into four executable
layers:

1. `tests/test_cutover_profile_contract.py` pins the exact closed
   `CutoverProfileV1` mapping, eleven ordered worktree roles, Runtime/SQLite/CRX/
   Config/ACL/maintenance/rollback bindings, immutable canonical round-trip,
   deterministic SHA-256 identity, hostile parsing rejection, and absence of
   paths or open text.
2. `tests/test_cutover_authorization_contract.py` pins four distinct,
   phase-specific externally supplied real-host authorization types, exact
   operation/profile/master/operator/validity bindings, fixed aggregate
   allow/block results, and exact-type rejection of missing, test, receipt,
   mapping, subclassed, and duck-typed inputs. It also proves that canonical
   Profile and authorization integrity is revalidated before `AUTHORIZED`,
   including hostile keys/values and cyclic tampered state.
3. `tests/test_cutover_receipt_contract.py` pins the twelve closed receipt
   families, exact type/status/operation/producer/subject/input/count/detail
   compatibility matrix, strict canonical JSON, deterministic receipt
   fingerprint, hostile comparison/key and lone-surrogate rejection,
   content-free values, and the rule that no receipt is authorization.
4. `tests/test_cutover_contract_architecture.py` pins the exact package files
   and public exports, recursive package-file closure, exact pure
   standard-library imports, forbidden host I/O loads/aliases and
   ambient-authority calls including `breakpoint`/`delattr`/`setattr`, exact
   sibling-only relative imports, package-wide absence of authorization
   issuer/mint/clock helpers, static/dynamic zero-consumer checks including
   dynamic-import call aliases across other
   `backend/`/`scripts/`/`frontend/` files, bounded files/functions, and the
   zero-argument always-blocked operator entry.

These checks create no authority and execute no preflight, migration, cutover,
resume, rollback, recovery, or cleanup. The package contains no path, adapter,
composition root, CLI, host reader, filesystem, SQLite, process, network, Git,
ACL, mailbox, provider, vault, private-store, credential, signing, random,
secret, clock, or mutation capability. A SHA-256 profile, authorization, or
receipt fingerprint is only a canonical integrity identity; it is not a
signature, issuer, or permission to act on a real host.

## 16. Synthetic crash-safe journal and recovery classification rule

Issue #52 translates the journal/state boundary into six executable layers:

1. `tests/test_cutover_journal_record_contract.py` pins strict canonical
   `JournalRecordV1`, closed step/direction/event/outcome values, exact binding
   fields, duplicate/unknown/non-canonical rejection, and deterministic record
   hashes.
2. `tests/test_cutover_journal_durability.py` pins create-only pending/final
   publication, Windows/Linux file and namespace barrier order, exact lost-ack
   retry, per-claim owner leases, stale-handle rejection, complete-chain recovery
   ownership, round-trip record integrity, and transition-before-write
   rejection.
3. `tests/test_cutover_journal_chain.py` pins sequence/previous-hash/binding/
   barrier/transition verification and fixed `JOURNAL_CHAIN_INVALID` behavior
   for hostile or corrupt snapshots.
4. `tests/test_cutover_journal_recovery.py` pins pre-bound recovery authority,
   fresh phase-specific resume/rollback validation, exact pre/post
   reconciliation, fresh `RESUME_BOUND` renewal, non-copyable/non-serializable
   exact-head permits backed by shared single-use atomic-token issuances,
   medium-gated first-mint/consume competition and stable-head continuation,
   Profile/master/operator binding, direction-aware pending recovery,
   no blind retry, LIFO reverse derivation, read-only restart inspection, and
   closed public results.
5. `tests/test_cutover_journal_crash_matrix.py` covers every before/after
   forward and reverse intent/effect/observation/commit cut plus every synthetic
   durability cut on both platform traces. It also pins continuation after
   namespace lost-ack for `INTENT`, `RESUME_BOUND`, `EFFECT_OBSERVED`, and
   `COMMITTED`, authoritative observed outcomes, identity/mapping substitution
   rejection, and post-effect re-observation.
6. `tests/test_cutover_journal_architecture.py` pins exact package files/exports/
   imports/signatures/consumer absence, forbidden capabilities, and the 300/50
   bounds.

The Issue #51 consumer allowlist is limited to
`backend/cutover_journal/contracts_bridge.py` and
`backend/real_host_preflight/contracts_bridge.py`, plus Issue #54's exact
`backend/migration_evidence_publication/contracts_bridge.py`, each with its
exact imported symbol set. The #53 bridge may only validate the locked
Profile/authorization values, construct closed preflight receipts, and reuse
fixed operator-entry values. The #54 bridge may only validate exact
review/publication/verification authorization phases. Neither can issue
authority or change the #51 schemas.
No test or implementation opens a real filesystem target, service, ACL,
repository/worktree, Runtime, SQLite, provider, mailbox, vault, private store,
or private data. `SAFE_ABORT`, `ROLLBACK_REQUIRED`, `INCIDENT_STOP`, and
`CUTOVER_SUCCEEDED` are distinct classifications; a result or fingerprint is
not host authority. Issues #57 through #59 remain separate.

## 17. Content-free Windows real-host preflight composition rule

Issue #53 translates the locked read-only host-preflight boundary into seven
executable layers:

1. `tests/test_real_host_preflight_portable.py` pins exact frozen/slotted/
   repr-redacted observation values, canonical fingerprints, 128-bit file-ID
   validation, exact object/parent/name/volume/reparse fields, hostile-type
   rejection, and non-Windows import behavior without claiming NTFS, Windows
   ACL, or real-host evidence.
2. `tests/test_real_host_preflight_windows.py` and
   `tests/test_real_host_preflight_windows_composition.py` use only an exact
   in-memory `TestSandboxAuthorizationV1` and caller-owned Windows
   `TemporaryDirectory`. A package-private root/marker identity permit is
   consumed once. Opened-handle observations and no-follow controlled
   components must fail closed on missing/replaced markers, permit replay,
   hard-link alias/reparse, unreadable or unexpected volume/filesystem state,
   parent replacement, target appearance, file-ID drift, normalized-name
   drift, and scope escape.
3. `tests/test_real_host_preflight_topology.py` requires two complete,
   identical current-topology passes before an accepted content-free receipt.
   Source, target parent, target absence, reparse, Git, ACL, and volume
   evidence must all be reconstructed and repeated; no partial second pass is
   sufficient. Source/parent/finance/target names must match the exact Profile
   role-selection projections, so a decoy absence cannot substitute.
4. `tests/test_real_host_preflight_gate.py` pins a fresh UUIDv4 nonce, exact
   operation and prior-topology binding, short half-open validity, repeat
   source/parent/absence/reparse/Git/ACL/volume checks, and one consumed gate
   attempt. The prior topology receipt is atomically single-claim; nominal
   receipt/gate state is module-owned and cannot be minted from a public
   envelope or reset through caller state. Stale, replayed, retargeted, or
   drifting evidence fails closed.
5. `tests/test_real_host_preflight_baseline.py` keeps source root, projects
   parent, finance project, volume, operator-SID, and each ACL observation
   separate, then independently verifies their deterministic content-free
   aggregate projection into the existing `HostBaseline`.
6. `tests/test_real_host_preflight_composition.py` binds only the exact seven
   callbacks through the #53 audit bridge. One synthetic assertion runs the
   unchanged audit core; the separate readiness proof invokes no callback or
   audit and never reports a final-layout pass. The existing final nine-zone
   policy remains unchanged. Bound callbacks and their identical adapter
   readers are revalidated before readiness.
7. `tests/test_real_host_preflight_architecture.py` and leakage tests pin exact
   files/exports/imports/bridges, read-only Windows API allowlists, zero normal
   consumers, forbidden capabilities, fixed error/result surfaces, and absence
   of raw path, SID, SDDL, account, Git name/ref, file ID, command, callback
   exception, and native error text in receipts, stdout, stderr, repr, or logs.

The real operator entry remains zero-capability and returns only
`BLOCKED_NO_APPROVED_COMMAND`, `blocked=1`, and `executed=0`; it cannot accept
test authorization. Issue #53 does not mint real authorization and does not
run against the real Repository Root or any real host target. It has no
service-control, ACL-apply, rename, worktree mutation, Runtime build, database
copy, artifact, Config, provider, mailbox, vault, private-store/private-data,
evidence publication, migration, cutover, resume, rollback, recovery, or
cleanup capability. Issues #57 through #59 remain separately authorized.

## 18. Reviewed Migration Evidence publication and verification rule

Issue #54 translates the profile-bound review/create/verify workflow into five
executable layers:

1. `tests/test_migration_evidence_publication_review.py` pins one opaque
   `ProfileBoundEvidenceSelectionV1`, exact `CutoverProfileV1` role/Git/worktree
   bindings, fresh `RealHostBaselineCollector` composition, complete in-memory
   review ownership, and a content-free `MigrationEvidenceReviewReceiptV1`.
   Arbitrary replacement values, mismatched Profile bindings, incomplete host
   evidence, target-parent identity collision/inode reuse, or review
   serialization/persistence fail closed. The test-only binder's fixed marker
   hard-link anchor makes the parent replacement regression deterministic on
   Windows and POSIX.
2. `test_migration_evidence_publication_create_verify.py`,
   `test_migration_evidence_publication_commit_binding.py`, and
   `test_migration_evidence_publication_package_observation.py` require exact
   `EvidencePublicationAuthorizationV1`, the confirmed review fingerprint,
   complete rediscovery, fresh HostBaseline equality, absent-target create-only
   publication, creator-owned source-snapshot and staged identity bindings,
   stable package identity, and exact package/manifest hashes and counts.
   Selection, source bytes, dirty-source, ref, worktree, Git, host, target,
   review, receipt, authorization, or post-commit replacement drift is rejected.
3. `test_migration_evidence_verifier_process.py` reads only a test-owned
   synthetic package through the fixed sanitized child process, verifies the
   exact first-read bytes through the independent payload verifier, requires an
   identical target reread, independently recomputes hashes/counts, and rejects
   transient ABA replacement, timeout, non-zero exit, malformed, duplicate, or
   unknown output, corruption, collision, or manifest mismatch without
   returning child exception text.
4. `test_migration_evidence_publication_receipts.py` requires
   `MigrationEvidenceReviewReceiptV1`,
   `MigrationEvidenceCreatedReceiptV1`, and
   `MigrationEvidenceVerifiedReceiptV1` to agree exactly on operation, Profile,
   master, review/selection/Git/host bindings, hashes, package identity, and
   counts before `MigrationEvidenceReceiptSetV1` can exist. The Set remains
   content-free evidence and never satisfies authorization.
5. `test_migration_evidence_publication_architecture.py`,
   `test_migration_evidence_verifier_architecture.py`, operator tests,
   static/mechanical checks, and leakage tests pin the creator/verifier
   dependency wall, read-only verifier package, exact bridges, fixed worker
   launch/environment/process-tree cleanup, locked real entries, zero
   normal-runtime consumers, the sole direct
   `os.link(marker, anchor, follow_symlinks=False)` call while rejecting
   imported/rebound/`getattr`/`Path.hardlink_to`/`Path.link_to` variants, and
   absence of path/ref/object/worktree/command/content/error leakage.

The creator may use shared pure archive-format validation but cannot import or
call the independent verifier capability. The verifier cannot import
publication/create modules or modify a package. Missing, wrong-phase, malformed,
and test authorization remain rejected before Issue #39. All executable tests
stay in test-owned temporary synthetic sandboxes; no real package, host
preflight, service, repository/worktree move, ACL apply, Runtime build, database
copy, provider, mailbox, vault, private store, or private data is accessed. A
Migration Evidence Package is evidence, not backup, Runtime artifact,
private-data container, or authorization to migrate.

## Issue #55 fixed-role ACL and filesystem rules

1. `WindowsAclAdapter` has exactly `capture`, `compare`,
   `apply_new_container_policy`, and `verify_fixed_zone_inheritance`.
2. Source-tree compatibility is complete, two-pass, read-only, bounded, and
   rejects protected or non-allowlisted descriptors.
3. Parent and finance baseline equality includes object identity, canonical
   SDDL fingerprint, and binary descriptor fingerprint.
4. Only a guarded create-only directory observation can authorize the empty
   Container DACL apply; the claim is single-use and requires a durable ACL
   INTENT. Its protected construction DACL has no child-creation right and its
   root/marker/parent/target handles remain held through final apply.
5. `SetSecurityInfo` receives only DACL/protected-DACL information with null
   owner, group, and SACL pointers.
6. Create-only directory uses parent-handle-relative `NtCreateFile` with
   `FILE_CREATE`; directory/file operations reject all existing targets. Native
   publication holds source and parent handles, sets no-replace, rejects
   reparse/cross-volume/identity drift, and proves the same 128-bit file ID.
7. Every mutation returns a content-free observation bound to the consumed
   journal INTENT and expected after fingerprint.
8. Architecture tests reject shell/PowerShell/`icacls`, replayable ACL
   transcripts, replace-capable moves, production consumers, and unlocked real
   constructors.

## Issue #56 reversible repository transaction rules

1. `test_cutover_repository_transaction_contracts`,
   `windows_scope`, and `architecture` pin the exact 8 embedded + 3 external
   roster, reviewed Git/common/admin/physical bindings, opaque pathless public
   seams, fixed imports, and absence of forbidden capabilities.
2. `durable_store` and journal tests pin strict canonical create-only records,
   sequence/hash chaining, INTENT/effect/OBSERVED/COMMITTED ordering, stable
   reread, exact `ABORTED/NOT_APPLIED` before-effect reconciliation, missing
   fact-only after-effect completion, corruption rejection, and content-free
   persistence.
3. `windows_round_trip` and `windows_boundary_reverse` prove the original
   Repository Root becomes `main`
   through same-volume identity-preserving relocation, every original
   physical/admin object is preserved first, exactly eleven reviewed
   counterparts are recreated with safe same-name admin reuse, and every
   completed forward boundary reverses while retaining any published failed
   evidence and restoring all twelve original repository/worktree physical
   identities plus all eleven original administrative identities.
4. `crash_gaps` covers after-INTENT, after-effect, after-OBSERVED, and
   after-COMMITTED gaps in both directions. Exact before state is `SAFE_ABORT`;
   exact expected-after state may be `SAFE_COMMIT_FACTS`; ambiguity is
   `INCIDENT_STOP`. Explicit reverse reconciles only exact safe forward gaps;
   an explicitly repeated reverse call also reconciles each safe reverse gap,
   validates its exact checkpoint, and runs only remaining mutations. No effect
   replay, background resume, or ambiguous resume exists.
5. `fail_closed` covers target/admin collision, after-INTENT target race,
   reparse, scope/volume escape,
   ref, dirty state, Git executable, physical identity, opaque administrative
   content, actual #55 observation, hostile Git config/hook, exact admin
   namespace, zone inventory, and unexpected worktree drift without clobber.
6. `real_lock` proves missing/test/malformed authority constructs nothing and
   exact real execution authority still returns
   `BLOCKED_NO_APPROVED_COMMAND` before Issue #39.
7. The final forward verifier composes unchanged ContainerAudit
   filesystem/Git/embedded-worktree validators over actual synthetic metadata;
   exact #56 Git verification separately covers all three external worktrees.

## Issue #57 managed publication rules

1. `test_cutover_managed_activation_contracts` pins the exact four adapters,
   strict receipt types, fixed order, same-operation/Profile/master/
   authorization chain, and a fingerprinted set that revalidates all four
   complete typed receipt mappings.
2. Runtime tests require an exact canonical manifest for the complete
   in-sandbox Python 3.12.13 distribution tree, including executable hash,
   entry count, total bytes, and tree fingerprint, a
   dependency lock that enumerates the complete installed closure, an exact
   offline wheelhouse, captured reviewed wheel bytes, a fresh target, and
   self-verification of Python, SQLite, the complete installed set, lock, and
   every import fingerprint.
3. Static and failure tests reject network, pip/index/PATH, system Python,
   user-site/cache, legacy venv reuse, unreviewed wheel, live resolution,
   `.pth`/`sitecustomize.py`/`usercustomize.py`, source/lock/wheel drift,
   path-swap races, child junction/reparse escape, alternate data streams,
   extra/missing Runtime entries, collision, and verification spoofing.
4. Database tests require the exact stopped-service receipt, a held
   write-blocking source handle, absent WAL/SHM/rollback journal before and
   after copy, read-only integrity verification without application-row
   inspection, durable create-only copy, stable hash, and unchanged held
   identity.
5. Artifact and Config tests require profile-bound CRX identity/format/size/
   hash and deterministic closed-schema Config bytes; build/sign/install/load,
   browser-profile access, environment/registry/credential/clipboard/hidden
   readers, alternate targets, overwrite, repair, and cleanup are absent.
6. Failure injection proves every partial target remains. Leakage tests pin
   content-free receipts, errors, repr, stdout, and stderr.
7. `real_lock` proves missing or test authority constructs nothing and exact
   real execution authority still returns `BLOCKED_NO_APPROVED_COMMAND`
   before Issue #39.
8. Exact package/export and consumer tests pin the complete implementation
   surface. Immutable scope snapshots plus held root/marker/target-parent
   handles require handle-relative `NtCreateFile(FILE_CREATE)`; created file
   handles deny concurrent writers until final verification.
9. A held Runtime-tree manifest captures only the CPython distribution streamed
   from held source handles plus every captured-wheel/lock addition. Mutable
   source namespace entries are never executed. Child creation is
   handle-relative, every
   baseline and created entry remains held, and exact scans reject reparse,
   ADS, extra, missing, or changed entries. Database and CRX tests inject drift
   after target verification to prove their final held-window gates.
10. Wheel capture/extraction and Runtime scans enforce fixed aggregate,
    member, expanded-size, compression-ratio, entry, file, byte, path, and
    depth budgets before unsafe allocation or growth. Held-handle size checks,
    pre-`ZipFile` central-directory bounds, pre-sort enumeration bounds, and
    bounded streaming extraction/hash are required.
11. New-Runtime import proof hashes exact installed import leaves without
    importing installed code. A recursive directory-change guard spans
    verification and receipt construction; the transient add/remove test
    requires a fixed failure, no receipt, and zero marker execution.
12. The harness materializes the approved Python distribution inside each
    test-owned sandbox; scope review rejects any external source executable.
13. Exact scans cover the Runtime root stream. The recursive change guard
    watches the Runtime parent from sealing through receipt construction and
    rejects transient child or NTFS stream mutation.
14. Before `venv` executes, every CPython source-tree entry is reparse/ADS
    checked, held against write/delete sharing, and recursively monitored.
    Post-authorization source drift must fail before marker code executes.
15. Runtime subprocess stdout is read incrementally; reaching the fixed byte
    ceiling terminates the child instead of buffering additional output.
    Wheelhouse enumeration stops at the expected-count ceiling before
    collecting an unbounded set.
16. Windows component validation rejects the superscript `COM¹/²/³` and
    `LPT¹/²/³` reserved-device aliases before any native create call.
17. Before target execution, the complete held-source `Lib/encodings` package
    is streamed into a bounded deterministic ZIP_STORED
    `managed-startup.zip`. Code-fixed create-only held `python312._pth` and
    `python._pth` sentinels order that immutable archive before `Lib` and
    `DLLs`; neither contains `import site`. Collision or replacement yields no
    execution or receipt, and transient `sitecustomize.py` creates no marker.
18. The verifier runs with fixed `-X frozen_modules=on`, imports only built-in
    `sys`, `nt`, `_sha2`, and `_imp`, proves `_imp.is_frozen("codecs")`, then
    blocks every later import. A transient `Lib/hashlib/__init__.py` package must
    create no marker and must be rejected only by the exact-tree change gate.
    New-Runtime hashes for `python.exe`, `_sqlite3.pyd`, and `sqlite3.dll` are
    compared with the approved held source entries.
19. A transient `Lib/encodings/aliases/__init__.py` package injected after the
    final scan must never execute before the verifier audit hook; CPython must
    resolve `encodings` and its children from `managed-startup.zip`, and the
    exact-tree change gate must reject the publication with no marker.
20. A transient `Lib/codecs/__init__.py` package must never execute before the
    verifier hook because fixed frozen-module mode resolves `codecs` through
    FrozenImporter; the new Runtime must report that proof and the exact-tree
    gate must reject the added package with no marker.

## Issue #58 provider-disabled lifecycle rules

1. Contract tests pin exact new/legacy service roles, dedicated legacy Config,
   fresh UUIDv4 nonces, PID/start time/executable/port-owner/Profile/Runtime/
   Config/data-role equality, and disabled providers.
2. Controller tests rebuild the complete Issue #57 receipt set, issue one
   code-owned synthetic request, accept only `deterministic_rules`, require
   provider attempts zero, and require exactly one matching new LocalData row.
3. Start and health identity drift, stale process/nonce, wrong port owner,
   provider attempt, arbitrary adapter, or non-nominal evidence fails closed.
4. Known typed pre-mutation start rejection becomes `SAFE_ABORT` with no stop
   or rollback. Known typed post-mutation health/result/persistence failure becomes
   `ROLLBACK_REQUIRED`; forward resume and unauthorised rollback are rejected.
5. Identity, journal, reparse, provider-boundary, safety, untyped start, or
   unexpected post-start adapter ambiguity becomes `INCIDENT_STOP`. Stop
   containment is invoked only when the exact new-service identity has already
   passed validation.
6. Rollback tests require fixed order: exact stop, preserve three external
   worktrees and eleven Git records, seal failed Container, restore main/Git/
   eight embedded plus three external worktrees, then reverify legacy
   prerequisites. Every stage binds the committed journal head, immutable
   committed-record/topology/ACL/database/sidecar/Runtime/repository plan, and
   previous observation or receipt; restoration also binds the actual #56
   reverse receipt.
7. Windows sandbox coverage composes the actual #56 full forward transaction,
   interrupts and resumes every committed reverse boundary, seals the failed
   Container before main extraction, rejects a pre-existing failed-Container
   collision, and proves exact original physical/admin identities for all
   eleven worktrees.
8. Legacy recovery uses one dedicated environment-independent disabled Config,
   a fresh distinct nonce, one start, one health check, and no analysis method.
   Failure is fixed
   `INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED` with no retry.
9. Synthetic SQLite coverage proves exactly one retained new activation row and
   zero writes to the legacy analysis table.
10. Architecture/leakage tests reject host/process/network/database/path/command
    capabilities and bound result/receipt/error/repr/stdout/stderr surfaces to
    fixed codes, fingerprints, and allowlisted counts.
11. Real-lock tests require both exact authorization types and prove missing,
    test, invalid, or even fully valid pre-#39 inputs construct nothing.
12. Exact public-export, per-module import, all-backend/script/frontend/workflow
    consumer, and dynamic-import guards prevent an unreviewed lifecycle
    capability or consumer from being added.

## Issue #59 final composition rules

1. Exact file/export/import guards pin one pure composition-contract package
   and three mutually isolated operator roots.
2. Every nominal role bundle carries the exact composition-binding fingerprint;
   extra, missing, mapping, subclass, duck-typed, or dynamically selected roles
   fail before a callback.
3. Real constructors and entries validate one exact phase authorization,
   reject test authority, and remain `BLOCKED_NO_APPROVED_COMMAND` before #39.
4. The receipt chain accepts only the code-fixed success or recovery sequence
   or an exact nonempty prefix, and binds one operation, Profile, governing
   master, operator,
   authorization sequence, review, package verification, ACL baseline, fresh
   gate, journal owner, linked prior/current heads, terminal receipt,
   activation, final audit, and recovery state.
5. Transaction execute/resume/rollback each consume one single-action claim.
   The journal owner atomically claims the fresh gate across composition
   objects and supplies the clock rechecked before every role. Resume accepts
   only an exact longer journal continuation; drift or replay returns the
   fixed rejection.
6. A stale pre-mutation receipt stops before ACL publication. Wrong
   predecessor, role, binding, receipt, owner, head, terminal state, or
   authorization expiry fails closed.
7. Coverage guards retain tests for reparse insertion, parent/source
   replacement, target appearance, service/database/worktree/ACL/receipt
   drift, every forward/reverse intent/effect/observation/commit gap, and each
   package/journal/directory/worktree/Runtime/database/CRX/Config/failed-
   Container/recovery no-clobber target.
8. Receipt, chain, result, error, repr, JSON, stdout, stderr, and log tests
   reject paths, SID/SDDL, Git names/IDs/commands, exceptions, credentials,
   mailbox/provider/vault/private content, database rows, and dynamic fields.
9. The complete E2E is `win32`-gated and executes only existing #53-#58
   test-sandbox seams. Its forward path passes through transaction `execute()`
   before journal-bound rollback. Portable/Linux tests claim no NTFS, Windows
   ACL, service, or native durability evidence.
10. Backend packages contain no executable test binder. Test-only assembly
    owns an internally created temporary scope, accepts no caller-selected
    root, and is invalid after close.
11. Issue #38 and its non-executable R1 remain unchanged; Issue #39 has no
    command or authorization. A merged final master requires a fourteen-item
    #38 re-review and a new R2 before #39.
