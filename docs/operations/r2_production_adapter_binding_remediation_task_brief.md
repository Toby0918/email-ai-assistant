---
last_update: 2026-08-06
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 Production Adapter Binding Remediation Task Brief

## 1. Task name

Remediate Issue #104 post-merge live Adapter surface binding.

## 2. Task type

```text
fix | security | test | docs
```

## 3. Current status

```text
implemented
```

## 4. Objective

Replace the production callback binding with exactly three nominal stateful
Adapter slots for preflight, evidence publication, and transaction. Bind every
fixed command to the exact Adapter type identity and command domain, add the
deterministic `ApprovedCutoverBindingV2` candidate builder, and reconnect the
three production process bootstraps without making any operator path executable.

The post-merge closure audit found that the nominal fingerprint binds the
owning module's stored source but not the live Adapter method surface. This
remediation must make runtime class-method substitution fail during the existing
per-call Adapter reverification, before the substituted method can act or a
completion can be created.

## 5. Non-goals

- Do not implement, modify, claim, or otherwise start Issue #105.
- Do not modify Issue #38 or Issue #39, and do not run an Issue #39 operation.
- Do not access VeraCrypt, `M:`, a private key, credential, mailbox, provider,
  vault, private data, or a real host.
- Do not generate keys, signatures, `reviewed-production-binding-v2.json`, gate
  evidence, or any other production artifact.
- Do not run `scripts/verify_r2_final_master_closure.py`.
- Do not modify the three historical composition roots, final-master closure
  package, final operator runbook, workflows, or `AGENTS.md`.
- Do not add a second callback interface, retain a compatibility layer, widen a
  command surface, or add an arbitrary Adapter/callback/operation selector.
- Do not push, create a PR, merge, close Issue #104, or publish tracker changes
  without separate authorization.
- Do not modify the dirty primary worktree at
  `D:\Projects\email_ai_assistant`.

## 6. Background and authority

- GitHub Issue #104 is the sole implementation authority and the source of
  truth for the exact add/modify/delete allowlist, protected surfaces,
  acceptance criteria, and validation categories.
- Governance authority is limited to `R2-GOV-EXT-07A` for claiming and
  implementing Issue #104. Earlier decisions `R2-GOV-EXT-05A`,
  `R2-GOV-EXT-05B`, `R2-GOV-EXT-06A`, and `R2-GOV-EXT-06B` fix the remediation
  contract but do not authorize Issue #105, publication, or execution.
- The original implementation baseline was remote
  `master@7a97afb53133b6a2bae31e8838fb234b800f8021`, tree
  `47b30c83af6693f8efedaae574c1a2b92b0305ac`; PR #106 merged that
  implementation as `153336142e52f712e1930e9cf70fff8ea1b8523a`.
- The post-merge remediation baseline is current remote
  `master@7615be47368acbdfe8d12e4bebd3910cfcf35680`, tree
  `a4905316ff275ec7afe6e3c55e438df6b1b33a00`.
- The post-merge remediation worktree is
  `D:\Projects\email_ai_assistant_issue_104_live_adapter_surface_fix_7615be47`
  on `codex/issue-104-live-adapter-surface-fix`.
- Required references are `AGENTS.md`, `CONTEXT.md`,
  `docs/operations/project_status_log.md`, the tooling, architecture, linter,
  mechanical, security, testing, structure, logging, and documentation
  constraints, plus the Issue #104 body.

## 7. Exact scope

Only the paths in the live Issue #104 `Exact allowlist` may be added, modified,
or deleted. This task brief is the first allowlisted addition. The following
surfaces remain explicitly protected and unchanged:

```text
backend/real_host_preflight_composition/
backend/migration_evidence_publication_composition/
backend/cutover_transaction_composition/
backend/r2_final_master_closure/
scripts/verify_r2_final_master_closure.py
docs/operations/r2_final_operator_runbook.md
.github/workflows/
AGENTS.md
```

Before completion, the Git diff must contain no path outside the Issue #104
allowlist and must not contain a change to any protected surface.

The post-merge remediation expects changes only to the following already
allowlisted paths unless a failing required guard proves another allowlisted
owner must be synchronized:

```text
backend/r2_production_binding/_adapter_identity.py
backend/r2_production_composition/adapter_binding.py
backend/r2_production_composition/catalog.py
tests/test_r2_production_adapter_binding_v1.py
tests/test_mailbox_transport_constraints.py
docs/operations/r2_production_adapter_binding_remediation_task_brief.md
docs/operations/project_structure.md
docs/operations/project_status_log.md
scripts/generate_project_status.py
```

## 8. Technical approach

1. Replace the callback identity implementation with one Adapter type identity
   implementation. Delete the obsolete callback binder and its obsolete tests;
   do not layer a compatibility interface over the new seam.
2. Create one deep production-composition Module with a small Interface. Its
   exact catalog maps ten fixed commands across exactly three stateful Adapters:
   preflight, evidence publication, and transaction.
3. Bind each command fingerprint to the exact nominal Adapter type identity,
   command domain, and reviewed behavior surface. Substitution, code drift,
   registry drift, and surface mismatch must fail before the Adapter acts.
4. Add one deterministic binding-candidate builder that accepts only the frozen
   final-master binding and four exact public authority verification keys. It
   derives operation, operator-role, and production-role fingerprints and
   exposes no caller-supplied fingerprint override.
5. Replace the three process-root callback compositions with the three
   stateful Adapter compositions. Keep exactly one production Adapter and one
   synthetic test Adapter at each seam.
6. Preserve `BLOCKED_NO_APPROVED_COMMAND` for every existing stateful real
   composition constructor and `DORMANT_NO_EXTERNAL_ISSUER` for every default
   process root. Reject testing Adapters in production bootstraps.
7. Emit a completion only after the selected Adapter returns and the exact
   composition outcome validates.

### Post-merge remediation slice

1. Add one regression test at the existing Adapter binding/reverification
   Interface. Replace the live reviewed Adapter's `invoke` method after binding
   and require reverification to fail before the substitute can run.
2. Extend the existing nominal Adapter identity with a deterministic projection
   of the exact live class surface. When the closed catalog loads the reviewed
   Adapter definitions, freeze both their exact member objects and deterministic
   surface digests so substitution before binding cannot become a new baseline.
   Do not execute custom descriptors, include mutable Adapter instance state,
   or introduce a second Adapter Interface.
3. Bind the catalog-frozen surface and capture `invoke` directly from that
   snapshot. Reuse the existing stored per-command implementation fingerprints
   and per-call reverification, comparing both object identity and deterministic
   content before and after recomputing fingerprints; no process caller gains a
   new selector or callback.
4. Confirm a forged nominal outcome cannot reach completion through a
   substituted live method, then rerun the full approved validation matrix.

The pre-approved TDD public seams are, in order: Adapter identity, the three
stateful Adapters, deterministic binding candidate, and the three process
bootstraps. Tests cross those Interfaces and do not mock internal Modules.

## 9. Data structure and interface changes

### Database changes

None.

### HTTP API changes

None.

### AI output JSON changes

None.

### Prompt changes

None.

### R2 internal interface changes

- Remove the callback identity and callback role-binding Interfaces.
- Add nominal stateful Adapter identity and three stateful Adapter Interfaces.
- Add a deterministic `ApprovedCutoverBindingV2` candidate builder.
- Replace the three process bootstrap composition fields with exact Adapter
  values while preserving dormant and locked behavior.

## 10. Security and privacy checks

- [x] No mailbox or real email data is read.
- [x] No provider, network model, credential, vault, private store, or private
  data is accessed.
- [x] No private key is read, generated, copied, signed with, or represented in
  a production artifact.
- [x] No real host, service, ACL, repository migration, Runtime, SQLite, CRX,
  Config, or cutover operation is executed.
- [x] Tests use only synthetic public values and in-memory/test-owned Adapters.
- [x] Public results, exceptions, repr, stdout, stderr, and logs remain
  content-free.
- [x] Receipts, tests, and Adapter binding evidence remain non-authorizing.
- [x] Issue #38, Issue #39, and Issue #105 remain unchanged.

## 11. Prompt injection protection

Not applicable. This task does not consume email content, prompt text, provider
input, or free-form executable input.

## 12. Acceptance criteria

1. The old production callback binder and its public exports are absent; no
   layered compatibility callback Interface exists.
2. Exactly three nominal stateful Adapter slots cover exactly ten fixed
   production commands.
3. Every command fingerprint commits its exact Adapter type identity and
   command domain; substitution, behavior drift, registry drift, and surface
   mismatch fail before action.
4. The deterministic candidate builder accepts no caller-supplied operation,
   operator-role, or production-role fingerprint.
5. Four authority verification keys are exact, unique, and disjoint from the
   fourteen pinned gate-producer keys.
6. Existing stateful composition implementations stay unchanged and their real
   constructors remain `BLOCKED_NO_APPROVED_COMMAND`.
7. Default process roots remain `DORMANT_NO_EXTERNAL_ISSUER`; a synthetic test
   Adapter cannot enter a production bootstrap.
8. Completion values are returned only after the exact Adapter result is
   validated.
9. Private-key access, key generation, signing, real-host operations, provider
   attempts, and Issue #39 changes remain zero.
10. The focused, affected, architecture, mechanical, documentation,
    maintenance, leakage, compile, diff, and full repository validation matrix
    passes.
11. No artifact targeting the frozen baseline is created or reused. A fresh
    remote master remains required only after a separately authorized merge.

## 13. Test plan

Use strict vertical RED to GREEN slices through the approved public seams:

0. Post-merge live surface regression: replace a reviewed Adapter method after
   binding, confirm reverification currently accepts it and the focused test is
   RED, then implement only enough identity hardening for GREEN.

1. Adapter identity: add one public-behavior test, run it and confirm the
   expected RED, implement only enough for GREEN, then rerun it.
2. Stateful Adapters and catalog: add one behavior slice at a time for exact
   command coverage, identity binding, state, failure-before-action, and
   completion validation.
3. Binding candidate: add one behavior slice at a time for deterministic
   derivation, four-key uniqueness/disjointness, and rejection of supplied
   fingerprints.
4. Process bootstraps: add one behavior slice at a time for exact production
   Adapter binding, synthetic exclusion, dormant default entry, and unchanged
   real locks.

After each slice, run its focused test. After all slices, run the complete
Issue #104 focused and affected test set, architecture/mechanical/static tests,
documentation tests, status generation and its tests, `compileall`,
`git diff --check`, the full `python -m unittest discover -s tests` suite,
read-only maintenance scan, and repository leakage scan. Never run the
final-master verifier.

## 14. Rollback approach

Do not use destructive Git commands and do not alter the dirty primary
worktree. If a slice fails, repair it with an allowlisted patch in the dedicated
worktree or stop and report the exact blocker. Any later rollback is a separate
forward corrective commit after separate authorization; history is not
rewritten.

## 15. Human confirmation boundaries

No additional clarification is required for the Issue #104 implementation
seams because the Issue and verified handoff already approve them. Separate
human authorization remains mandatory before push, PR creation, merge, Issue
closure, Issue #105 work, artifact issuance, final-master verification, Issue
#38 action, or Issue #39 action.

## 16. Pre-execution checks

- [x] Read `AGENTS.md`, `CONTEXT.md`, and project status.
- [x] Read complete tooling, architecture, and linter constraints.
- [x] Read task-brief and documentation rules.
- [x] Read the required TDD testing/mocking and deep-Module design references.
- [x] Revalidated Issue #104 and Issue #105 state and native dependency.
- [x] Revalidated remote master and the clean dedicated worktree HEAD, tree,
  branch, staged, unstaged, and untracked state.
- [x] Revalidated that the dirty primary worktree exactly matches the handoff.
- [x] Confirmed the exact allowlist, protected surfaces, non-goals, and public
  seams.

## 17. Remote provider private-context checklist

Not applicable. Provider routing, private context, deidentification, budgets,
and frontend disclosures are unchanged. Providers remain disabled and all
verification is offline.

## 18. Administrator stage-evaluation checklist

Not applicable.

## 19. Final dataset build and interactive judge checklist

Not applicable.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable.

## 21. Repository placement and operational layout checklist

- [x] The dedicated linked worktree is the only mutable workspace for this
  task.
- [x] No Repository Root, Project Container, operational path, host Adapter,
  path selector, or private capability is added.
- [x] Existing composition real constructors remain locked before Issue #39.
- [x] Tests are synthetic and offline and perform no real migration, cutover,
  host, provider, mailbox, vault, private-store, or credential operation.

## 22. Post-execution record

```text
Historical implementation record:
- PR #106 merged the original 47-path Issue #104 implementation as
  `153336142e52f712e1930e9cf70fff8ea1b8523a`.
- Its original validation record remains historical evidence only; it did not
  prove binding-time versus call-time live Adapter descriptor identity.

Current remediation changed files:
- Nine Issue #104 allowlisted paths are modified in the dedicated worktree:
  three binding implementation files, the live-surface regression test, the
  status-generator AST guard, this brief, project structure, generated project
  status, and its generator.
- No path is staged, committed, pushed, or published.

Test results:
- Direct live `invoke` replacement was observed RED before the first GREEN.
- A metadata-preserving function-object replacement then exposed a second RED;
  exact binding-time member identity plus deterministic code-surface checking
  made that stronger regression GREEN.
- Spec review then exposed a pre-binding substitution window as a P1. A third
  RED now proves catalog-frozen reviewed identity rejects a metadata-preserving
  replacement before binding; the invocation target comes directly from that
  reviewed snapshot.
- Both review axes then exposed forged `_invoke` state as a P1. A fourth RED now
  proves each reverification requires the bound invocation target to remain the
  exact catalog-frozen `invoke` member before it can act.
- Publication-session dual review exposed registry rebasing as a P1: replacing
  `invoke` and then rebuilding the module registry could make the substituted
  member a new baseline. A fifth RED reproduced the bypass. The catalog now
  captures the original registry object independently and rejects any later
  module-registry rebinding before binding or reverification; both review axes
  independently replayed the pre-binding and post-binding probes and returned
  CLEAN.
- In-memory probes reject metadata-preserving descriptor replacement before and
  after binding, bound-target replacement, in-place function-code mutation, and
  class-namespace addition.
- The pre-publication focused and affected R2 matrix passed 93 tests. The
  publication-session registry-rebinding regression adds one independently
  demonstrated RED-to-GREEN case; the final direct affected selection passes
  50 tests, and the full suite includes it.
- The pre-publication architecture, mechanical, static, documentation,
  transport, and obsolete surface matrix passed 136 tests after pinning the
  reviewed status-generator AST. The publication-session architecture,
  mechanical, static, documentation, transport, and affected architecture
  selection passes 155 tests after the final documentation and AST-fingerprint
  update.
- Final Standards and Spec rereviews report zero actionable P0-P2 findings after
  both P1 live-target findings were repaired and re-reviewed.
- The final full repository suite passes on the required repository Python
  3.12.13 virtual environment: `Ran 2729 tests in 2550.324s` and
  `OK (skipped=3)`.
- An earlier publication-session full run used the dependency-free bundled
  interpreter and ended with 38 collection import errors for missing `bs4`,
  `openai`, and related installed packages. A minimal interpreter comparison
  reproduced that environment-only failure; the repository `.venv` contains
  the pinned dependencies and produced the clean full-suite result above.
- One first-pass Windows-only failure was exact CRLF worktree expansion of the
  protected operator runbook. Its index and `HEAD` both named blob
  `03b0550bd3ff7998aca995c1661523413561f7ec`; restoring those exact LF blob
  bytes created no Git diff, the failed test passed, and the complete suite then
  passed.
- Post-suite maintenance passes with only the pre-existing low stale-draft
  findings; repository leakage is zero, isolated compileall succeeds for
  `backend`, `scripts`, and `tests`, and `git diff --check` passes.
- The read-only closure audit sees remote
  `master@7615be47368acbdfe8d12e4bebd3910cfcf35680`, exact 3/10 slot-command
  allocation, all live-surface and registry-rebinding adversarial probes
  rejected, nine allowlisted
  worktree paths, no staged path, and no protected-surface diff. The dirty
  primary repository and historical Issue #104 worktree remain unchanged.
- Live Issue #104 remains OPEN and is the exact native blocker of OPEN Issue
  #105. This remediation is locally closure-ready, but Issue #104's formal
  merged-reviewed-code criterion is not satisfied by uncommitted local changes.

Incomplete items:
- Stage, commit, push, PR, merge, Issue closure, Issue #105, external artifacts,
  final-master verification, Issue #38 review, and Issue #39 remain outside this
  authority.

Follow-up:
- Keep Issue #104 open and stop at the separate publication boundary. After
  explicit authorization, stage only these nine paths, commit, push, review and
  merge them, then repeat fresh-master validation before any Issue closure.
```
