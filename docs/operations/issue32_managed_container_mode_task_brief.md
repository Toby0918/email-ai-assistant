---
last_update: 2026-07-23
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 32 managed container mode task brief

## 1. Task name

```text
Issue #32 local-service Managed Container Mode
```

## 2. Task type

```text
feature
```

## 3. Current status

```text
implementation_verified_review_pending
```

## 4. Goal

Run the existing provider-disabled local-service lifecycle in Managed Container
Mode from remote `master@6d6551ffe0ace08a0bb57f52ff28a3d0dc4182f4`.
The launcher must validate the exact `email_ai_assistant/main` placement before
reading non-secret operational configuration or starting the service, then route
all ordinary writable state to the approved sibling zones while repository
source and tooling remain rooted at `main`.

## 5. Non-goals

- Do not perform the real Project Container or Repository Root migration.
- Do not move, copy, delete, clean, rename, or reconfigure the current
  repository, runtime, database, local directory, or any existing worktree.
- Do not create or activate a real Managed Container on this machine.
- Do not implement `ContainerAudit` or begin Issues #34 through #40.
- Do not access a real mailbox, provider, raw vault, recovery store, private
  store, private dataset, credential, key, ignored `.env`, or customer data.
- Do not enable OpenAI, DeepSeek, Ollama, Qwen, Gemma, private knowledge,
  mailbox ingest, or private evaluation.
- Do not change the public HTTP API, public SQLite schema, AI-result schema,
  prompts, browser permissions, current-message click boundary, attachment
  limits, or cleanup semantics.
- Do not broaden repository maintenance or leakage scanning to Project
  Container siblings.
- Do not restore the retired Codex cleanup automation or modify the scheduled
  GitHub cleanup workflow.
- Do not merge the resulting pull request or close parent Spec #29.

## 6. Background and references

- GitHub Issue #29: governed Project Container specification.
- GitHub Issue #32: approved Managed Container Mode implementation ticket.
- PR #44: merged at the exact remote baseline for this task.
- Issues #30, #31, and #33: completed prerequisites.
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/issue30_repository_placement_task_brief.md`
- `docs/operations/issue31_standalone_verification_task_brief.md`
- `docs/operations/issue33_protected_private_stores_task_brief.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/operations/testing_checklist.md`
- `docs/operations/deployment_notes.md`

## 7. Scope

Expected implementation and test paths:

- `backend/email_agent/config.py`
- `backend/email_agent/managed_runtime.py`
- `scripts/manage_local_service.py`
- `scripts/run_local_debug.py`
- `tests/test_config.py`
- `tests/test_manage_local_service.py`
- `tests/test_run_local_debug.py`
- `tests/test_managed_container_mode.py`
- focused architecture, maintenance, status, and leakage contract tests where
  required
- Managed Container Mode operations and setup documentation
- `docs/operations/project_status_log.md`

Repository scanners and source discovery are expected to remain unchanged
unless a focused test exposes a real `main`-root defect.

## 8. Technical approach

1. Add an explicit boolean `--managed-container` operator mode. It derives the
   Repository Root from the launcher source root and derives the Project
   Container as that root's parent. No CLI, environment, config, frontend, or
   public request may supply an arbitrary container, protected-root, runtime,
   data, temporary, log, artifact, worktree, or configuration path.
2. Call `RepositoryPlacement.managed` before any operational settings read,
   logging setup, cleanup, private bootstrap, or server start. Only the exact
   canonical `email_ai_assistant/main` relationship is accepted.
3. Resolve `OperationalLayout` from the validated placement. Require the seven
   approved ordinary zone roots to exist as stable, non-reparse directories.
   Managed startup may create only request-local descendants and normal service
   files inside those already provisioned zones; it does not create or migrate
   the Project Container layout.
4. Route the normal analysis database to
   `LocalData/email_agent.sqlite3`, request attachment temporary files to
   `RuntimeTemp/attachment_temp`, diagnostics and PID state to `Logs`, the
   Python executable to `Runtimes/venv/Scripts/python.exe`, and retain
   `Artifacts`, `Worktrees`, and `Config` as their approved resolved roots.
5. Read at most one bounded `Config/settings.env` only after placement and zone
   validation. The exact non-secret key allowlist is:
   `EMAIL_AGENT_LOG_LEVEL` and `EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS`.
   Unknown, duplicate, malformed, oversized, non-regular, or reparse-bearing
   configuration fails closed with a fixed content-free code. API keys,
   provider/model/endpoint settings, private paths, credentials, and secrets
   are never sourced from this file.
6. Build an immutable Managed `AppConfig` from resolved operational paths and
   allowlisted non-secret settings. All remote and local providers remain
   disabled, provider keys remain absent, private knowledge remains disabled,
   and the existing attachment limits remain fixed.
7. Pass the already-resolved database path and `AppConfig` through the existing
   launcher/server/API seams. Request handlers receive no placement or config
   reader and cannot rediscover the container from a public payload.
8. Keep `ServiceConfig.root`, child-process working directory, startup script,
   frontend assets, Git operations, project-status generation, maintenance
   scanning, and repository leakage scanning rooted at the Repository Root
   (`main`), never at the Project Container or another sibling zone.
9. Verify start, health, one fixed user-confirmed synthetic current-message
   analysis, SQLite persistence, and stop through the lifecycle seam using only
   a temporary synthetic Managed layout and injected process control.

## 9. Data structure or interface changes

### Database changes

No schema change. Managed normal analysis SQLite uses the resolved absolute
`LocalData/email_agent.sqlite3` path.

### API changes

No HTTP API change. The local lifecycle manager and debug launcher gain the
boolean `--managed-container` operator option.

### AI output JSON changes

None.

### Prompt changes

None.

## 10. Security and privacy checks

- [x] No real mailbox data is read.
- [x] No mail is sent, deleted, archived, moved, forwarded, or scanned.
- [x] No provider, vault, private store, credential, key, ignored `.env`, or
  private dataset is accessed.
- [x] Providers remain disabled and provider keys remain absent.
- [x] Managed configuration is bounded, non-secret, and exact-allowlisted.
- [x] Public requests cannot choose paths, placement, providers, or secrets.
- [x] Tests use only synthetic current-message content and temporary paths.
- [x] Logs and failures remain content-free and do not expose config values,
  paths, native exceptions, credentials, or customer data.
- [x] Existing attachment count, byte, retention, click-scope, and cleanup
  contracts remain unchanged.

## 11. Prompt injection protection

The synthetic email body remains untrusted current-message content and is
analyzed only with `user_confirmed=true`. It cannot configure the service,
select a provider, change a path, load Config, rediscover the container, or
execute commands. `Config/settings.env` is operator configuration, not email or
public-request input, and still accepts only the exact non-secret key allowlist.

## 12. Acceptance criteria

1. All Issue #32 acceptance criteria are satisfied.
2. Exact Managed placement fails closed before Config is read, logging is
   configured, cleanup runs, a process starts, or a server binds.
3. SQLite uses `LocalData`; request attachments use `RuntimeTemp`; logs and PID
   use `Logs`; runtime, artifact, worktree, and Config roots are the approved
   sibling zones.
4. Managed Config accepts only the two documented non-secret keys and never
   sources credentials, provider settings, provider keys, private paths, or
   arbitrary operational paths.
5. Providers stay disabled, loopback validation remains unchanged, and one
   synthetic analysis still requires explicit user confirmation and persists
   through the unchanged public API/schema.
6. Request handlers receive only the resolved `AppConfig` and database path;
   public payload placement/config fields cannot affect runtime routing.
7. Source assets, Git operations, project-status generation, maintenance scan,
   and repository leakage scan remain rooted at `main`.
8. A synthetic Managed layout passes start, health, one fixed analysis,
   persistence, and stop without touching a real Managed Container.
9. Focused tests, architecture/static/mechanical guards, full regression,
   compile checks, status generation, maintenance scan, repository leakage
   scan, and diff checks pass.
10. Standards review has no P1/P2 findings and Spec review has no findings.

## 13. Test plan

The pre-agreed TDD seams are:

- Managed runtime seam:
  `prepare_managed_runtime(repository_root=..., project_container=...)` using
  synthetic directories and observable fixed failures.
- Managed configuration seam:
  bounded `Config/settings.env` parsing and immutable provider-disabled
  `AppConfig` construction.
- Public lifecycle-manager seam:
  parser/config construction plus `start_service`, `health_service`,
  `analyze_synthetic_email`, and `stop_service` with injected process and stop
  adapters.
- Public launcher seam:
  `scripts.run_local_debug.main` with injected placement/config, logging, and
  server adapters.
- Existing HTTP contract seam:
  `/api/health` and `/api/analyze-current-email`, exercised in the synthetic
  Managed lifecycle test without a provider, mailbox, private store, or public
  network.
- Repository-root seam:
  source discovery, status generation, maintenance, and leakage scans remain
  bounded to `main`.

Use RED -> GREEN vertical slices:

1. Exact placement before Config read.
2. Zone and runtime executable routing.
3. Config allowlist and deterministic provider-disabled `AppConfig`.
4. Lifecycle-manager and launcher routing.
5. Synthetic start/health/analysis persistence/stop.
6. Architecture and no-public-rediscovery guards.

Focused suites run after each slice. Final verification uses the project Python
3.12.13 / SQLite 3.50.4 environment and includes full unittest discovery,
compileall, JavaScript syntax checks, manifest validation, project-status
generation, maintenance scan, repository leakage scan, and `git diff --check`.

Pre-change focused baseline:

- 94 tests passed across project layout, standalone verification, lifecycle,
  launcher, config, and server suites.

## 14. Rollback plan

Revert only this branch's Managed launcher, lifecycle, configuration, tests, and
documentation changes. No real Project Container, runtime, data, worktree,
mailbox, provider, vault, credential, ACL, or external-store state is created or
changed.

## 15. Questions requiring human confirmation

None. Issue #32 defines the mode, scope, safety boundaries, automatic acceptance
conditions, and authorized Git/PR operations. Any real migration, host-security
operation, destructive action, Config secret support, provider access, or Issue
#34 through #40 work requires new authorization.

## 16. Pre-execution checklist

- [x] Read `AGENTS.md`, `CONTEXT.md`, and the current project status log.
- [x] Read tooling, architecture, linter, task-brief, ADR, and migration rules.
- [x] Verified PR #44 merged as
  `6d6551ffe0ace08a0bb57f52ff28a3d0dc4182f4`.
- [x] Verified Issues #30, #31, and #33 are closed.
- [x] Verified Issue #32 is open, `ready-for-agent`, and has no open blocker.
- [x] Verified remote `master` is exactly
  `6d6551ffe0ace08a0bb57f52ff28a3d0dc4182f4`.
- [x] Created clean independent worktree
  `D:\Projects\email_ai_assistant_issue_32_managed_container_mode` and branch
  `codex/issue-32-managed-container-mode`.
- [x] Confirmed root `master@f071781` and every pre-existing worktree remain
  untouched.
- [x] Confirmed no real mailbox, provider, private store, vault, credential, or
  customer data is needed.

## 17. Remote provider private-context checklist

Provider routing, remote input, runtime knowledge, and budgets are unchanged.
Managed Container Mode forces both remote routes and every local model route
disabled, supplies no provider key, loads no private snapshot, and uses
synthetic/offline verification.

## 18. Administrator stage-evaluation checklist

Not applicable. Private evaluation staging remains disabled and is not imported
or invoked by this mode.

## 19. Final dataset build and interactive judge checklist

Not applicable. No private dataset, provider judge, TTY workflow, or aggregate
evaluation report is opened or created.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable. Mailbox sync and current-click evidence handoffs are unchanged.

## 21. Repository placement and operational layout checklist

- [x] No third final placement mode is added.
- [x] Managed mode derives and validates only the canonical
  `email_ai_assistant/main` relationship.
- [x] `OperationalLayout` derives only absolute ordinary paths.
- [x] Managed protected roots remain the single Project Container root.
- [x] Public HTTP, environment, frontend, Config, and CLI path overrides cannot
  supply or narrow protected roots.
- [x] Flat and Standalone behavior remain separate and unchanged.
- [x] Tests are synthetic/offline and perform no real migration or Managed
  Container creation.

## 22. Post-execution record

Actual changed files:

- Managed config/runtime: `backend/email_agent/config.py`,
  `backend/email_agent/managed_runtime.py`.
- Lifecycle/launch/status: `scripts/manage_local_service.py`,
  `scripts/run_local_debug.py`, `scripts/generate_project_status.py`,
  `docs/operations/project_status_log.md`.
- Tests/guards: `tests/test_managed_container_mode.py`,
  `tests/test_run_local_debug.py`, `tests/test_generate_project_status.py`,
  `tests/test_architecture_constraints.py`,
  `tests/test_mailbox_transport_constraints.py`.
- Boundary and operator documentation: `AGENTS.md`, `README.md`, ADR 0009,
  tooling/architecture/mechanical constraints, deployment/testing/project
  structure, and the migration/task briefs.

Test results:

- Focused Managed/config/launcher/lifecycle/server/layout suites: 112 passed,
  1 host-capability skip.
- Full unittest discovery after status generation: 1747 passed, 2 skips.
- Python compileall passed; JavaScript syntax passed for 10 files; extension
  manifest JSON parsed successfully.
- Maintenance report: no findings. Repository leakage summary: `total=0`.
- `git diff --check` passed.

Incomplete items:

- Standards/Spec dual-axis review, any required P1/P2 repair and re-review.
- Final staged-snapshot leakage/diff verification, commit/push, and PR creation.

Follow-up suggestions:

- Do not begin Issue #34 through Issue #40 without separate authorization.
