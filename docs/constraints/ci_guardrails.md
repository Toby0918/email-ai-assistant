---
last_update: 2026-07-27
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# CI Guardrails

本文件定义项目的 CI 护栏策略。  
CI 的目标不是替代人工 review，而是把已经明确的工程规则变成自动检查。

## 1. CI 文件位置

CI 配置文件：

```text
.github/workflows/agent_guardrails.yml
```

## 2. CI 运行时机

CI 应在以下场景运行：

```text
pull_request
push to main
push to master
```

## 3. CI 检查内容

CI 至少运行以下检查：

```text
tests/test_architecture_constraints.py
tests/test_static_linter_constraints.py
tests/test_mechanical_rule_constraints.py
tests/test_maintenance_scan.py
tests/test_generate_project_status.py
tests/test_migration_evidence_*.py
tests/test_migration_evidence_publication_*.py
tests/test_migration_evidence_verifier_*.py
tests/test_runtime_activation_rehearsal_*.py
tests/test_cutover_contract_*.py
tests/test_cutover_journal_*.py
tests/test_real_host_preflight_*.py
python -m unittest discover -s tests
python scripts/maintenance_scan.py
```

## 4. 检查目标

CI 必须防止以下问题进入主分支：

```text
架构分层被破坏
前端直接调用 OpenAI
前端保存或暴露密钥
出现自动发送、删除、归档邮件能力
后端业务代码使用裸 print()
后端业务代码使用 traceback.print_exc()
出现裸 except
backend/*.py 单文件超过 300 行
backend/*.py 单函数超过 50 行
docs/ 下 Markdown 缺少 YAML front matter
后台清理 Agent 无法生成报告
项目状态日志生成器无法生成 Agent 可读快照
维护扫描脚本发现高风险项目卫生问题
migration evidence package 出现在 Repository Root、覆盖目标、缺失必备 evidence、
或无法在 synthetic temporary repository 中独立恢复
reparenting rehearsal 接受外部 path、出现非 reviewed bridge/consumer、使用
clone/prune/delete/overwrite，或任一 synthetic publication boundary 无法验证 rollback
runtime activation rehearsal 接受 path/default host adapter、出现真实 host consumer、
未在 `pre_publication` stopped proof 后 create-only 发布、未用 activation token
绑定 start/health/analysis/`post_activation` fresh-stop proof、放宽 provider-disabled/
Managed-role/source-preservation 门禁，或访问真实 runtime/SQLite/artifact/evidence/
private capability
cutover journal 出现真实 path/adapter/host consumer，pending/unbarriered record
可授权 effect，candidate transition 在写入后才失败，restart inspection 发生写入或
自动动作，stale owner handle 仍可操作，effect 不消费 exact durable-intent permit，
durable observed fact 可被覆盖或重放，pending direction 被猜测，Profile/identity/
transition mapping 未 fail closed，expected-post 被 blind retry，resume/recovery
authority 未 fresh revalidate，reverse 非 journal-derived LIFO，public result 泄漏
observation/path/command/exception，或任一 forward/reverse/durability crash boundary
未被分类
```

### Issue #53 Windows real-host preflight gate

CI must reject any Issue #53 change when:

- Windows observation runs outside a test-owned `TemporaryDirectory`, lacks an
  exact root/marker identity-bound single-use permit, accepts a wrong
  authorization phase or permit replay, accepts an absolute or parent-relative
  escape, follows a hard-link alias/reparse component, or accepts unexpected
  volume/filesystem, unreadable, incomplete, or drifting identity evidence;
- `CurrentTopologyPreflight` does not perform two complete identical passes, or
  accepts callback evidence that fails exact factory reconstruction or Profile
  role-selection binding, or `PreMutationGate` is not bound to a fresh UUIDv4
  nonce, exact operation, atomically single-claimed prior topology, short
  validity, single use, and repeated source,
  target-parent, target-absence, reparse, Git, ACL, and volume checks;
- `RealHostBaselineCollector` merges or substitutes source, parent, finance,
  volume, operator-SID, or ACL evidence, exposes a raw value, or produces a
  non-canonical/incomplete/content-observed `HostBaseline`;
- final-audit readiness invokes the current pre-cutover `ContainerAudit`,
  claims a final-layout pass, changes the final nine-zone policy, or binds
  anything other than the exact seven intact read-only callbacks and their
  identical composed adapter readers;
- a public canonical envelope, direct allocation, attribute mutation, copy,
  serialization, or concurrent replay can mint, replace, or reset a nominal
  receipt or gate capability;
- the operator entry accepts test authorization, path, callback, command, or
  executable capability, or returns anything other than
  `BLOCKED_NO_APPROVED_COMMAND`, `blocked=1`, and `executed=0`;
- the package gains service-control, ACL-apply, rename, repository/worktree
  mutation, Runtime-build, database-copy, artifact, Config, provider, mailbox,
  vault, private-store/private-data, evidence-publication, cutover, recovery,
  or cleanup capability; or
- a receipt, result, `repr`, stdout, stderr, or log contains a raw path, SID,
  SDDL, account, Git name/ref, file ID, command, callback exception, or native
  error text.

Windows jobs may execute native observation only beneath the caller-owned
sandbox created by the test fixture and bound to an exact in-memory
`TestSandboxAuthorizationV1`. Linux jobs run the portable contract, topology,
gate, baseline, composition, architecture, and leakage tests only; a Linux pass
does not claim NTFS, Windows file-ID, Windows ACL, or real-host evidence.

Both platforms run the focused Issue #53 suite, affected ContainerAudit,
migration-evidence and cutover-contract suites, architecture/static/mechanical/
documentation/leakage checks, the full unit suite, and the read-only
maintenance scan. Green CI proves only the locked read-only composition and
test-sandbox behavior. It does not authorize or execute Issues #55 through #59,
Issue #39, a final ContainerAudit, migration, cutover, recovery, or cleanup.

### Issue #54 reviewed evidence publication and verification gate

CI must reject any Issue #54 change when:

- review accepts a dirty-source, local-ref, worktree, package-target, Git, or
  HostBaseline replacement that is not bound to the exact `CutoverProfileV1`,
  or persists the complete `MigrationEvidenceReview` as alternate authority;
- create accepts anything other than the exact
  `EvidencePublicationAuthorizationV1`, exact review receipt, and confirmed
  review fingerprint, skips complete rediscovery/fresh HostBaseline collection,
  accepts any reviewed-state drift, or publishes to an existing target;
- the creator can import, construct, or call the independent verifier, or the
  verifier imports publication/create capabilities or can write, create,
  replace, rename, link, unlink, remove, or delete a package;
- verification is not a separate fixed read-only process, does not verify the
  exact bytes from its first bounded descriptor read, does not require an
  identical target reread and independently recompute package/manifest hashes
  and counts, or accepts timeout, non-zero exit, malformed/duplicate/unknown
  response, corruption, collision, ABA replacement, or manifest mismatch;
- the review, created, and verified receipts can form
  `MigrationEvidenceReceiptSetV1` without exact agreement on operation,
  Profile, governing master, review/selection/Git/host bindings, package and
  manifest hashes, package identity, and applicable counts;
- a real entry accepts missing, wrong-phase, malformed, or
  `TestSandboxAuthorizationV1` input before Issue #39, or gains an executable
  host command;
- a package test escapes its test-owned temporary synthetic sandbox, accesses a
  real Repository Root or existing worktree, or performs real host preflight,
  service, repository/worktree move, ACL apply, Runtime build, database copy,
  provider, mailbox, vault, private-store, or private-data work; or
- any receipt, result, `repr`, stdout, stderr, or log exposes a path, ref, object
  ID, worktree name, command, content, native error, or exception text, or
  describes the package as backup, Runtime artifact, private-data container, or
  migration authorization.

Windows and Linux jobs run the focused Issue #54 synthetic suite, affected
Issue #35/#51/#53 suites, exact architecture/static/mechanical/documentation/
leakage checks, the full unit suite, and read-only maintenance scan. Green CI
would prove only the synthetic composition and locked-entry boundary. It would
not create or authorize a real package, migration, mutation, cutover, rollback,
or cleanup, and it does not replace human Standards/Spec review.

## 5. 失败处理原则

如果 CI 失败，Agent 必须先阅读失败信息。  
每条失败信息应尽量包含：

```text
❌ 什么错
✅ 怎么改
📖 去哪里看
```

Agent 不得通过以下方式修复 CI：

```text
删除测试
注释测试
放宽规则但不更新文档
跳过失败检查
把违规代码移到未被检查的目录
```

如果确实需要修改规则，必须同步更新：

```text
AGENTS.md
docs/constraints/architecture_constraints.md
docs/constraints/linter_constraints.md
docs/constraints/mechanical_rule_translation.md
docs/constraints/ci_guardrails.md
tests/
```

## 6. 版本说明

CI 使用 Python 3.12.13。  
SQLite 运行时版本由 CI 环境提供，CI 会打印 SQLite runtime 版本用于排查，但第一阶段不把 SQLite runtime 精确版本作为强制失败条件。
