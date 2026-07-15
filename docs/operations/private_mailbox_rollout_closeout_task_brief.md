---
last_update: 2026-07-15
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Private Mailbox Rollout Closeout Task Brief

## 1. Task Name

```text
close authorized mailbox, private knowledge, and DeepSeek offline rollout
```

## 2. Task Type

```text
docs | test | security | chore
```

## 3. Current Status

```text
approved | in_progress
```

This brief implements only Task 7 of the approved 2026-07-14 master plan.
Tasks 1 through 6 are treated as frozen inputs to closeout verification.

## 4. Goal

Complete the operational documentation, add content-free repository leakage
guards, regenerate the Agent handoff status, and run the complete offline
verification matrix. The result must be safe to review without exposing raw
mail, private-derived prose, identifiers, secrets, vault material, or private
evaluation cases.

## 5. Non-Goals

- No live mailbox, IMAP, DeepSeek, external vault, private evaluation dataset,
  DPAPI, BitLocker, recovery-key, or network access.
- No change to the public HTTP response, public SQLite projection, browser
  permissions, current-message click boundary, or production model selection.
- No automatic cleanup, deletion, remediation, mailbox action, provider call,
  snapshot provisioning, or second backup.
- No reading or scanning of project-external vaults or private `.pkeval` files.
- No claim of legal archiving, physical secure erase, zero retention, or
  cross-volume/path-race atomicity.

## 6. Background And Sources

This closeout follows:

- `AGENTS.md`
- `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`
- `docs/operations/authorized_mailbox_ingest_task_brief.md`
- `docs/operations/deepseek_analysis_contract_alignment_task_brief.md`
- `docs/operations/private_deepseek_evaluation_task_brief.md`
- `docs/superpowers/plans/2026-07-14-authorized-mailbox-ingest-knowledge-deepseek.md`
- the operations, documentation, CI, static, architecture, and mechanical
  constraints referenced by those documents.

## 7. Expected Scope

Expected changes are limited to:

- `scripts/repository_leakage_scan.py`
- `scripts/maintenance_scan.py`
- `scripts/generate_project_status.py`
- Task 7 tests under `tests/`
- `docs/operations/testing_checklist.md`
- `docs/operations/review_checklist.md`
- `docs/operations/deployment_notes.md`
- `docs/operations/project_structure.md`
- `docs/product/roadmap.md`
- regenerated `docs/operations/project_status_log.md`
- this task brief.

## 8. Technical Design

1. Add a pure, read-only repository leakage helper. Its default file list is
   Git tracked files plus explicitly scoped repository-local logs/test outputs
   and public SQLite fixtures. Tests inject their own temporary file list.
2. Match only fixed leakage classes with fixed allowlists for synthetic
   examples and official public URLs. Findings expose only fixed codes, counts,
   and coarse scope categories; never matched text, identifiers, secrets, or
   concrete paths.
3. Integrate the helper into the read-only maintenance scan without automatic
   deletion or rewriting.
4. Make the status generator report the completed offline controls and still
   distinguish them from separately authorized live operation.
5. Update operator checklists for vault, knowledge, evaluation, provider
   rollback, and incident stop workflows.

## 9. Data Or Interface Changes

### Database Changes

```text
None.
```

### API Changes

```text
None.
```

### AI Output JSON Changes

```text
None.
```

### Prompt Changes

```text
None.
```

The maintenance CLI gains content-free leakage findings only. It remains
read-only and preserves its existing exit-code contract.

## 10. Security And Privacy Checklist

- [x] No real mailbox or private dataset is accessed.
- [x] No email is sent, deleted, moved, archived, or marked read.
- [x] Provider configuration remains backend-only and disabled in verification.
- [x] Scanner output cannot contain the matched value or concrete file path.
- [x] Tests use only constructed synthetic canaries and temporary repositories.
- [x] External vaults and `.pkeval` datasets are outside scanner scope.
- [x] The scan is report-only and cannot remediate files automatically.

## 11. Prompt Injection Protection

No model prompt is changed. Repository text is treated as untrusted bytes for
pattern classification only; the scanner never executes instructions, opens
URLs, resolves external paths, or imports scanned files.

## 12. Acceptance Criteria

1. Leakage tests begin RED and finish GREEN for tracked files, repository-local
   operational artifacts, public SQLite fixtures, and generated status.
2. Findings serialize only fixed codes, counts, and coarse scope categories.
3. The status log states that the administrator CLI is default-off, browser
   behavior remains click-only, knowledge snapshot failure falls back to
   generic rules, DeepSeek uses the 15/13/10/5 privacy budget, private
   evaluation is judge-blocked by default, and no model switch is automatic.
4. Operator docs cover initialization, inventory, fingerprint-confirmed scan,
   at-most-50 approved attachments, verify, purge, revoke, recovery rewrap,
   knowledge review/publication/rollback, evaluation gates, provider rollback,
   and incident stops.
5. Full offline verification passes with `EMAIL_AGENT_LLM_PROVIDER=disabled`.

## 13. Test Plan

- Task 7 focused leakage, maintenance, status, and documentation contract tests.
- Existing 50-case synthetic DeepSeek replay.
- Full Python unittest discovery.
- JavaScript syntax checks for every changed JavaScript file, or record none.
- Architecture, static, mechanical, dependency, documentation, manifest, and
  leakage guards.
- `git diff --check` and maintenance scan with `--fail-on-high`.

## 14. Rollback

Revert the closeout commit. Keep `EMAIL_AGENT_LLM_PROVIDER=disabled`, do not run
the administrator CLI, and remove runtime access to the private knowledge
snapshot to force generic-rule fallback. Rollback never mutates mailbox data.

## 15. Human Confirmation

Any real mailbox import, external vault initialization, private dataset run,
human usefulness judge, DeepSeek call, or production model switch still needs
a separate local operator action and approval after this offline closeout.

## 16. Pre-Execution Check

- [x] Read `AGENTS.md`, the current project status, Task 1-6 contracts, ADR,
  closeout plan, and operations/constraint documentation.
- [x] Confirmed the exact Task 7 scope and non-goals.
- [x] Confirmed no live system, real data, secret, or external encrypted store
  will be accessed.
- [x] Confirmed public HTTP and SQLite schemas remain unchanged.

## 17. Remote Provider Private-Context Checklist

- [x] Provider remains disabled and conservative by default.
- [x] Existing backend-only deidentification/residual gate remains unchanged.
- [x] Existing immutable empty runtime-card default remains unchanged.
- [x] Existing 8-card/4,000-character knowledge limit remains unchanged.
- [x] Existing 13/10/8/5/2/15 second budgets remain unchanged.
- [x] Persistent disclosure continues to avoid local-only and zero-retention claims.
- [x] Verification is offline and uses synthetic fixtures only.

## 18. Post-Execution Record

### Actual changes

- Added `scripts/repository_leakage_scan.py` and integrated its content-free,
  fail-closed findings into `scripts/maintenance_scan.py`.
- Updated status generation and regenerated
  `docs/operations/project_status_log.md` as
  `authorized_private_analysis_offline_ready`.
- Added Task 7 leakage/closeout tests and synchronized testing, review,
  deployment, structure, cleanup, and roadmap documentation.
- No public HTTP, SQLite, renderer, prompt, provider route, or production-model
  configuration changed. No JavaScript file changed in Task 7.

### RED and GREEN evidence

- Initial focused RED: 28 tests, 34 subtest failures and 6 errors. Missing
  scanner/integration plus stale status/operations contracts caused every
  failure.
- Fail-closed follow-up RED: 9 tests, 1 failure and 1 error for an ignored
  repo-local `.pkeval` and native scope-discovery detail propagation.
- Final Task 7 focused GREEN: 33 tests, all passed.
- Architecture/static/mechanical/transport/dependency/docs/manifest/leakage
  guard group: 99 tests, all passed.
- Complete Python suite: 1,019 tests passed with one existing platform skip.
- Existing synthetic replay: 50 cases; schema and mandatory-risk retention
  `1.0`, unsupported critical facts `0`, commitment/action violations `0`, and
  the expected adversarial replay fallback rate `0.2`.
- Seven JavaScript syntax checks and manifest JSON parse passed even though
  Task 7 changed no JavaScript.
- Intended tracked scope leakage summary was `total=0`; maintenance
  `--fail-on-high` and `git diff --check` passed.

### Deferred live activities

Real mailbox/vault/evaluation/provider actions remain separately authorized
local-operator work. Private evaluation remains blocked by
`human_judge_unavailable` until an approved local judge is supplied, and no
production model is switched automatically.
