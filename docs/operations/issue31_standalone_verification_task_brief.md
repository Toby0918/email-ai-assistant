---
last_update: 2026-07-23
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 31 standalone verification mode task brief

## 1. Task name

```text
Issue #31 local-service Standalone Verification Mode
```

## 2. Task type

```text
feature
```

## 3. Current status

```text
accepted
```

## 4. Goal

Run the existing local-service lifecycle in explicit Standalone Verification
Mode from the reviewed remote `master@b3ed70b5bc63d22c80666922858d1f5022136582`
baseline. The mode uses a separately supplied temporary state root, synthetic
current-message input, and provider-disabled configuration for start, status,
health, analysis, restart, and stop verification.

## 5. Non-goals

- Do not implement Managed Container Mode.
- Do not perform the Project Container or Repository Root migration.
- Do not create, move, delete, clean, or reconfigure any existing worktree.
- Do not start Issue #32 through Issue #40.
- Do not enable or access OpenAI, DeepSeek, Ollama, Qwen, Gemma, mailbox ingest,
  private evaluation, raw vault, Operator Private, ignored credentials, or
  external private stores.
- Do not change the public HTTP API, public SQLite schema, AI result schema,
  prompts, browser permissions, current-message click boundary, attachment
  limits, or cleanup semantics.
- Do not restore the retired Codex cleanup automation or change the scheduled
  GitHub cleanup workflow.
- Do not close parent Spec #29 or merge the resulting pull request.

## 6. Background and references

- GitHub Issue #29: governed Project Container specification.
- GitHub Issue #30: completed RepositoryPlacement compatibility seam.
- GitHub Issue #31: approved Standalone Verification Mode implementation ticket.
- PR #42: merged at the exact remote baseline for this task.
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/issue30_repository_placement_task_brief.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/operations/testing_checklist.md`
- `docs/operations/deployment_notes.md`

## 7. Scope

Expected implementation and test paths:

- `backend/email_agent/config.py`
- `backend/email_agent/standalone_verification.py`
- `scripts/manage_local_service.py`
- `scripts/run_local_debug.py`
- `tests/test_config.py`
- `tests/test_manage_local_service.py`
- `tests/test_run_local_debug.py`
- `tests/test_standalone_verification.py`
- focused architecture and documentation contract tests where required
- Standalone Verification Mode operations and setup documentation
- `docs/operations/project_status_log.md`

## 8. Technical approach

1. Add an explicit `--standalone-state-root` option to the existing lifecycle
   manager and local-debug launcher. Add lifecycle-manager `health` and fixed
   synthetic `analysis` commands. The state value must identify an existing,
   separate, absolute temporary directory accepted by
   `RepositoryPlacement.standalone`.
2. Resolve `OperationalLayout` from that validated placement. Create and
   revalidate ordinary operational directories, reject reparse writable
   targets, and derive SQLite, attachment temporary files, logs, and PID state
   under the state root only.
3. Build a deterministic Standalone Verification `AppConfig` without loading
   `.env` or provider/private configuration from the process environment.
   Remote and local providers remain disabled, provider keys are absent, private
   knowledge is disabled, and existing attachment limits are retained.
4. Preserve the flat-layout transition behavior when the new option is absent.
   Do not add Managed Container routing.
5. Pass the explicit state root through the process-launch command, keep the
   repository as the working directory, and keep the current Python executable
   and startup script observable through injected process adapters.
6. Keep existing lifecycle cleanup ordering and status/loopback behavior. The
   standalone cleanup receives the same deterministic temporary attachment
   configuration used by the launched service.
7. Verify the complete operational lifecycle with a fresh temporary state root
   and one synthetic user-confirmed current-message analysis.

## 9. Data structure or interface changes

### Database changes

No schema change. Standalone SQLite is an explicit absolute path under the
temporary state root.

### API changes

No HTTP API change. The local CLI gains the optional
`--standalone-state-root <absolute-temporary-directory>` argument.

### AI output JSON changes

None.

### Prompt changes

None.

## 10. Security and privacy checks

- [x] No real mailbox data is read.
- [x] No mail is sent, deleted, archived, moved, or scanned.
- [x] Ignored `.env` and signing credentials remain unread.
- [x] Providers, mailbox ingest, private evaluation, raw vault, and Operator
  Private remain disabled and inaccessible.
- [x] Standalone state is separate from the Repository Root and uses explicit
  absolute temporary paths.
- [x] Tests use only synthetic requests and temporary state.
- [x] Logs and failures remain content-free and do not expose private paths or
  native exception details.
- [x] Existing attachment count, byte, retention, click-scope, and cleanup
  contracts remain unchanged.

## 11. Prompt injection protection

The synthetic email body remains untrusted current-message content and is
analyzed only with `user_confirmed=true`. It cannot configure the service,
select a provider, change a path, load credentials, or execute commands.

## 12. Acceptance criteria

1. All Issue #31 acceptance criteria are satisfied.
2. `start`, `status`, `health`, `analysis`, `restart`, and `stop` use the
   existing lifecycle-manager interface with the same explicit state root.
3. `/api/health` returns HTTP 200 and one synthetic user-confirmed analysis
   returns a valid provider-disabled rule result.
4. SQLite, attachment temporary files, diagnostics log, and PID state are all
   located under the explicit temporary state root and no runtime output enters
   the Repository Root.
5. Standalone startup does not load `.env`, private knowledge, ignored
   credentials, mailbox ingest, private evaluation, or raw-vault capabilities.
6. OpenAI, DeepSeek, Ollama, Qwen, and Gemma remain disabled even if hostile
   provider environment values are present.
7. Loopback validation, current-message click scope, persistence, attachment
   limits, and cleanup ordering remain unchanged.
8. Process arguments, executable, startup script, working directory, and
   operational paths are observable through injected adapters.
9. Focused tests, architecture/static/mechanical guards, full regression,
   compile checks, maintenance scan, repository leakage scan, and diff checks
   pass.
10. Standards review has no P1/P2 findings and Spec review has no findings.

## 13. Test plan

The pre-agreed TDD seams are:

- Public lifecycle-manager seam: parser/config construction plus
  `start_service`, `status_service`, `restart_service`, and `stop_service`, using
  injected process, health, stop, and sleep adapters.
- Public launcher seam: `scripts.run_local_debug.main` with parsed arguments and
  injected config, logging, bootstrap, and server adapters.
- Existing HTTP contract seam: `/api/health` and
  `/api/analyze-current-email`, exercised by one final loopback operational smoke
  after automated tests. Automated tests do not bind a socket or probe host
  security.

Each capability is implemented as a RED to GREEN vertical slice. Focused suites
run after each slice, followed by configuration, server, lifecycle,
architecture, static-linter, and mechanical suites. Final verification uses the
project Python 3.12.13 environment and includes full unittest discovery,
compileall, JavaScript syntax checks, manifest validation, project-status
generation, maintenance scan, repository leakage scan, and staged scope checks.

## 14. Rollback plan

Revert only this branch's launcher, lifecycle, configuration, tests, and
documentation changes. The mode creates no Managed Container data and performs
no migration, so rollback requires no directory, mailbox, provider, vault,
credential, ACL, or external-store recovery.

## 15. Questions requiring human confirmation

None. Issue #31 defines the lifecycle seam, exact scope, automatic acceptance
conditions, and authorized Git/PR operations. Any Managed Container behavior,
real migration, external/private access, destructive action, or Issue #32
through Issue #40 work requires separate authorization.

## 16. Pre-execution checklist

- [x] Read `AGENTS.md`, `CONTEXT.md`, and the current project status log.
- [x] Read tooling, architecture, linter, testing, deployment, documentation,
  and task-brief rules.
- [x] Verified PR #42 merged and Issue #30 completed.
- [x] Verified Issue #31 is open, `ready-for-agent`, and blocked only by the now
  closed Issue #30.
- [x] Verified remote `master` is exactly
  `b3ed70b5bc63d22c80666922858d1f5022136582`.
- [x] Created a new isolated worktree and
  `codex/issue-31-standalone-verification` branch from that exact commit.
- [x] Confirmed the original dirty root worktree and every pre-existing
  worktree remain untouched.
- [x] Confirmed no real mailbox, provider, private store, vault, credential, or
  customer data is needed.

## 17. Remote provider private-context checklist

Provider routing, remote input, runtime knowledge, and budgets are unchanged.
Standalone Verification Mode forces both remote routes and every local model
route disabled, supplies no provider key, loads no private snapshot, and uses
synthetic/offline automated verification.

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
- [x] Standalone requires an explicit separate temporary state root.
- [x] `OperationalLayout` derives only absolute ordinary paths.
- [x] Flat layout remains a transition adapter when standalone is not selected.
- [x] No real migration or Managed Container creation is performed.
- [x] Tests are synthetic and use temporary directories.

## 22. Post-execution record

Actual changed files:

- `README.md`
- `backend/email_agent/config.py`
- `backend/email_agent/standalone_verification.py`
- `docs/operations/deployment_notes.md`
- `docs/operations/issue31_standalone_verification_task_brief.md`
- `docs/operations/project_status_log.md`
- `docs/operations/testing_checklist.md`
- `scripts/manage_local_service.py`
- `scripts/run_local_debug.py`
- `tests/test_config.py`
- `tests/test_manage_local_service.py`
- `tests/test_run_local_debug.py`
- `tests/test_standalone_verification.py`

Test results:

- TDD RED failures were observed before each standalone path/config,
  lifecycle-manager command, and reparse-guard implementation.
- Focused configuration, lifecycle, launcher, server/API, placement,
  architecture, static-linter, and mechanical regressions passed.
- Final full regression at `1a438e4`: 1700 tests passed, 1 skipped.
- Complete lifecycle-manager smoke passed start, status, health, fixed synthetic
  analysis, restart, health, and stop with hostile provider/private environment
  values ignored. The result used `rule_fallback`, persisted exactly one SQLite
  row, removed PID state on stop, and created no repository `outputs/`.
- Python compileall, 10 JavaScript syntax checks, manifest JSON validation, 69
  focused guard tests, maintenance scan, repository leakage scan, and
  `git diff --check` passed.
- Initial Standards/Spec review findings were addressed: project status and this
  record were updated; health/analysis became lifecycle commands; derived
  operational directories and writable targets now fail closed on reparse
  evidence.
- Final Spec review reported no findings. The second Standards review
  found that flat mode could invoke the synthetic analysis POST; a RED test now
  proves flat mode is rejected before the injected HTTP requester. Standards
  re-review confirmed that behavior and identified only the now-corrected stale
  test count/status record plus the recorded non-blocking P3.

Incomplete items:

- No Issue #31 implementation or review item remains. Authorized GitHub
  publication remains.
- Normal non-blocking P3: the initial review noted duplicated standalone path
  derivation across manager and launcher. The fix centralized that derivation
  in `backend.email_agent.standalone_verification`.
- Normal non-blocking P3: the second Standards review noted that
  `scripts/manage_local_service.py` now owns both process lifecycle and the
  small synthetic verification HTTP client and exceeds the 300-line
  recommendation. Extraction is deferred because it is advisory, behavior is
  covered through injected boundaries, and a broader refactor is not required
  for Issue #31.

Follow-up suggestions:

- Do not begin Issue #32 through Issue #40 without separate authorization.
