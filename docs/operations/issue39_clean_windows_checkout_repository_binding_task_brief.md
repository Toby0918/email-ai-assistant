---
last_update: 2026-08-31
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 39 clean Windows checkout repository-byte binding task brief

## 1. Task name

Issue 39 controlled clean-checkout repository-byte binding repair.

## 2. Task type

```text
security
```

## 3. Current status

```text
in_progress
```

The authorized live command safely retained the reviewed incident archive and
six durable before-evidence preflight records, then returned `INCIDENT_STOP`
with `host_actions=0`. Read-only diagnosis reproduced
`R2_ISSUE39_REPOSITORY_BYTE_DRIFT` in `prepare_evidence` because 398 tracked
files in the clean legacy Windows checkout contain CRLF working-tree bytes
while their stage-zero index blobs contain LF bytes.

## 4. Goal

Keep binding the exact raw working-tree size and SHA-256 used by relocation,
while independently proving that either those raw bytes are the stage-zero Git
blob or one code-owned CRLF-to-LF clean projection is that blob. Reject every
other content change, non-clean repository, staged/index drift, custom Git
filter, working-tree encoding, or explicit text/EOL attribute.

## 5. Non-goals

- Do not rerun, resume, roll back, or otherwise continue the real cutover.
- Do not change or clean the retained incident archive, preflight ledger, or
  any real Project Container source.
- Do not execute Git clean filters, attribute commands, hooks, or caller code.
- Do not add a path, filter, encoding, normalization, force, repair, cleanup,
  overwrite, delete, or alternate repository option.
- Do not authorize a later master, closure, Issue 38 review, or Issue 39 run.

## 6. Basis

- The operator's explicit authorization for this exact repair and governed
  PR/CI/merge chain.
- Frozen base commit `d5063fd2d86821c2f927ae745a60682b79c7c9b8` and tree
  `18d469036e6c71a443ca3fa513c565a67a0f5cf6`.
- The retained content-free live failure evidence: three completed preflight
  observations, zero host effects, and the fixed repository byte-drift code.
- `AGENTS.md`, `CONTEXT.md`, ADR 0012, current Project Status Log, and the
  tooling, architecture, linter, CI, and mechanical constraints.

## 7. Exact Add/Modify/Delete allowlist

### Add

```text
backend/r2_issue39_orchestrator/production_repository_review.py
docs/operations/issue39_clean_windows_checkout_repository_binding_task_brief.md
```

### Modify

```text
backend/r2_issue39_orchestrator/production_repository.py
docs/constraints/architecture_constraints.md
docs/constraints/linter_constraints.md
docs/constraints/mechanical_rule_translation.md
docs/constraints/tooling_constraints.md
docs/decisions/0012-issue39-project-container-cutover-orchestration.md
docs/operations/issue39_project_container_cutover_runbook.md
docs/operations/project_status_log.md
docs/security/project_container_cutover_contracts.md
scripts/generate_project_status.py
tests/test_generate_project_status.py
tests/test_mailbox_transport_constraints.py
tests/test_cutover_managed_activation_architecture.py
tests/test_r2_issue39_production_native_windows.py
```

### Delete

```text
none
```

Any additional path is a contract change and requires a new exact allowlist
decision before modification.

## 8. Technical design

`review_repository_manifest(root)` remains the public seam. It first requires
filter-free clean-state evidence: HEAD tree equals the complete regular stage-
zero index, every index flag is ordinary, and the untracked set is empty. It
queries only the four fixed attributes `filter`, `working-tree-encoding`,
`text`, and `eol` through the already sanitized, hook-neutralized, stdin-closed
Git runner and requires every result to be `unspecified`; no filter is executed.

Each tracked file is still opened through the writer-denying bounded Windows
handle. Its exact raw byte size and SHA-256 remain the relocation evidence. The
index OID is accepted directly when it equals the raw blob OID. Otherwise the
only clean projection is code-owned replacement of CRLF pairs with LF. The
projection requires at least one CRLF, no remaining bare CR, no NUL, and an
exact resulting blob OID equal to the stage-zero index OID. Mixed LF/CRLF text
is allowed only when that same deterministic projection exactly reaches the
index blob. Every other mismatch fails closed.

The implementation accepts no arbitrary filter, attributes file, encoding,
normalizer, environment, or callback. Relocation continues to verify and move
the original raw bytes, not the projection.

## 9. Data and API changes

- Database, HTTP API, provider, prompt, frontend, mailbox, and vault: none.
- Public cutover command: unchanged; still exactly `run`.
- Repository manifest shape: unchanged; `git_oid` binds the index blob and
  `size_bytes` plus `sha256` bind the raw checkout bytes.

## 10. Security and privacy checks

- [x] No repository content is printed or persisted by diagnostics.
- [x] No Git filter, hook, shell, provider, mailbox, vault, or credential is used.
- [x] True content, stage, index, attribute, encoding, and raw-byte drift fail closed.
- [x] No live cutover continuation is authorized by this change.

## 11. Acceptance criteria

1. A real Windows synthetic repository with `core.autocrlf=true` and clean
   mixed LF/CRLF checkout bytes produces a manifest whose raw SHA-256 differs
   from but whose controlled projection equals the index blob.
2. True working-tree changes, staged changes, non-clean state, custom filter,
   working-tree encoding, and explicit text/EOL attributes fail closed.
3. Existing raw-byte-exact repositories and relocation/recovery behavior pass.
4. The exact A/M/D diff equals this brief.
5. Focused, Issue 39, architecture, mechanical, status, full-suite,
   maintenance, leakage, Standards, and Spec gates pass before PR/merge.
6. CI is green on the PR and merged master before a new closure is considered.

## 12. Test plan

Use the public `review_repository_manifest(root)` seam in the existing Windows
native suite. First add the clean `core.autocrlf=true` case and observe RED.
Implement only the controlled projection and observe GREEN. Add one rejection
case at a time for true content, staged state, filter, encoding, text, and EOL
attributes. Then run affected integration and complete repository gates.

## 13. Rollback plan

Before merge, use forward corrective commits only within the allowlist. After
merge, a defect requires another forward PR. Do not reset history or delete,
move, repair, or clean retained live evidence or host state.

## 14. Human confirmation questions

None for the authorized repair, PR, CI, and merge. A new master still requires
a new closure, protected verifier, human Issue 38 final review, and separate
SHA-bound Issue 39 cutover authorization.

## 15. Pre-execution checklist

- [x] Read exact-master `AGENTS.md`, status log, constraints, context, and ADR.
- [x] Applied Matt `diagnosing-bugs` and `tdd`; `code-review` is required before PR.
- [x] Confirmed `host_actions=0` and preserved the live evidence.
- [x] Created a clean isolated LF worktree at the exact frozen base.

## 16. Execution record

- The first `core.autocrlf=true` mixed-LF/CRLF public-interface test reproduced
  `R2_ISSUE39_REPOSITORY_BYTE_DRIFT` against the frozen implementation, then
  passed after the dual binding was implemented.
- Filter-free clean-state review now binds HEAD/index equality, ordinary index
  flags, an empty untracked set, stable fixed attributes, and raw relocation
  bytes without executing a Git clean filter.
- The actual legacy Repository Root passed the new read-only review with 481
  entries and content-free manifest fingerprint
  `7cca14d278af5f4c4d93ba4825f7fc8191d30105ec469e5b6effd1ea8bc749cb`.
- Six focused clean/drift/attribute/hidden-index tests pass. The complete Issue
  39 run executed 123 tests: 119 passed, two registered skips remained, and the
  same two legacy-service ambiguity errors reproduced independently on the
  unchanged exact `d5063fd2...` baseline.
- The complete repository run executed 2,920 tests. Five registered skips
  remained; the same two baseline legacy-service ambiguity errors remained;
  its sole change-related failure identified the new internal reader missing
  from the exact managed-activation consumer allowlist. That allowlist was
  corrected and its complete owning architecture/mechanical/focused set then
  passed 75/75.
- Maintenance reported no high or medium finding and only the existing 24 low
  stale-document findings. Standards/Spec review, PR, CI, and merge remain
  pending.
