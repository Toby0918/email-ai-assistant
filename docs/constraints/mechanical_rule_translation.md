---
last_update: 2026-07-25
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
   files, and workflows.

These checks deliberately do not expand repository leakage scanning above the
Repository Root and do not make maintenance scanning traverse the Project
Container. Real preflight/post-cutover composition remains a separately
approved later Issue.

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
   and no runtime/workflow consumer, a reserved ignored suffix, and name-only
   leakage rejection.

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
database or worktree mutation and does not implement Issues #37–#40.
