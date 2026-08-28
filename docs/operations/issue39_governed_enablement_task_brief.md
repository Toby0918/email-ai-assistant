---
last_update: 2026-08-28
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 39 governed code enablement task brief

## 1. Task name

Issue 39 exact production-consumer allowlist and governed code enablement.

## 2. Task type

```text
security
```

## 3. Current status

```text
in_progress
```

## 4. Goal

On frozen base commit `98af48509a79bf6700576f11ec702c054da2c3af`
and tree `94d095c79221fa3277c13377626fbd8b38f9f3af`, record and
mechanically enforce the minimum Issue 39 production-consumer allowlist for the
already-reviewed one-command orchestrator. The only ordinary production entry
is `scripts/execute_project_container_cutover.py`, which imports the fixed
`backend.r2_issue39_orchestrator.cli.main`; the package-owned retained restart
runner may contain only the same exact import-and-call bytes.

The three historical `backend.r2_preflight_process`,
`backend.r2_evidence_process`, and `backend.r2_transaction_process` standalone
roots remain unconditionally `DORMANT_NO_ISSUE39_APPROVAL`. They are not a
second live command surface and are not unlocked by this change.

## 5. Non-goals

- Do not run the real command, incident disposition, closure confirmation,
  protected verifier, service lifecycle, ACL operation, Git/worktree repair,
  Runtime publication, database publication, or cutover.
- Do not create an environment, argument, file, manifest, acknowledgement,
  synthetic marker, Adapter, callback, or registry unlock.
- Do not touch provider, mailbox, vault, credential, private store, private
  data, GitHub ruleset, or cleanup state.
- Do not reopen or weaken the fixed Issue 39 command, action catalog, dynamic
  roster, durable ledger, confirmation, retained-state, or recovery contracts.
- Do not treat implementation, tests, PR, CI, merge, closure evidence, or the
  closed Issue 38 review as real-host execution authority.

## 6. Basis

- The operator's 2026-08-28 authorization to implement, test, publish, and
  merge the Issue 39 governed enablement without a real-host cutover.
- Closed Issue 38 review against `98af48509a79bf6700576f11ec702c054da2c3af`.
- `AGENTS.md`, `CONTEXT.md`, ADR 0010, ADR 0012, the current Project Status Log,
  and the Issue 39 tooling, architecture, linter, CI, mechanical, and security
  constraints.

## 7. Exact Add/Modify/Delete allowlist

### Add

```text
docs/operations/issue39_governed_enablement_task_brief.md
tests/test_r2_issue39_governed_enablement.py
```

### Modify

```text
AGENTS.md
docs/constraints/architecture_constraints.md
docs/constraints/ci_guardrails.md
docs/constraints/linter_constraints.md
docs/constraints/mechanical_rule_translation.md
docs/constraints/tooling_constraints.md
docs/conventions/logging.md
docs/decisions/0012-issue39-project-container-cutover-orchestration.md
docs/operations/project_status_log.md
docs/operations/project_structure.md
docs/security/project_container_cutover_contracts.md
scripts/generate_project_status.py
tests/test_generate_project_status.py
tests/test_mailbox_transport_constraints.py
tests/test_static_linter_constraints.py
```

### Delete

```text
none
```

Any additional path is a contract change and requires a new explicit allowlist
decision before it is modified.

Allowlist amendment 01 adds only
`tests/test_mailbox_transport_constraints.py` because that guard pins the AST
SHA-256 of the approved status generator. The user's standing authorization to
auto-approve necessary in-scope follow-on decisions covers this mechanical hash
update; it adds no capability and changes no transport rule.

Allowlist amendment 02 adds only `docs/conventions/logging.md` and
`tests/test_static_linter_constraints.py`. The Standards review identified the
repository's mandatory linter-rule synchronization rule; the user's standing
authorization to auto-approve necessary in-scope follow-on decisions covers
these documentation/test-only paths. They add no production capability.

## 8. Technical design

1. Add one static/behavioral guard at the production-consumer seam.
2. Recursively inspect production Python imports, including relative and
   from-package spellings; require that only the fixed script imports
   `backend.r2_issue39_orchestrator` from outside the package and that no
   production module imports the fixed script.
3. Pin the fixed script's complete source and bind the actual retained
   `__main__.py` archive argument to the exact import-and-call bytes owned by
   `production_anchor_package.py`.
4. Invoke all ten historical standalone verbs with poison objects and require
   zero reads, zero publication/mutation, and
   `DORMANT_NO_ISSUE39_APPROVAL`.
5. Update current normative documents to distinguish approved code
   reachability from still-missing real-host execution authority.
6. Preserve the existing one-command implementation byte-for-byte; no
   production effect code is changed by this enablement patch.

## 9. Data and API changes

- Database: none.
- HTTP API: none.
- AI output JSON: none.
- Prompt: none.
- Public cutover CLI: none; it remains exactly `run`.

## 10. Security and privacy checks

- [x] Providers remain disabled and no provider capability is added.
- [x] No mailbox, vault, credential, private store, or private data is read.
- [x] No email is sent, deleted, or archived.
- [x] No real host effect is authorized or executed.
- [x] Public output remains fixed and content-free.
- [x] Historical standalone roots remain dormant.

## 11. Acceptance criteria

1. The exact A/M/D diff equals this task brief's allowlist.
2. Only the fixed script can import the Issue 39 orchestrator from an ordinary
   production source; the retained runner bytes are exact and package-owned.
3. The three historical standalone roots remain dormant for all ten verbs and
   inspect none of the poison inputs.
4. Current normative documentation states that code enablement is approved but
   real-host execution still requires a separate fresh authorization.
5. Focused, affected, architecture, mechanical, documentation, full-suite,
   maintenance, and leakage checks pass.
6. Standards and Spec review report no unresolved findings before PR and merge;
   review fixes must be committed and re-reviewed first.
7. PR checks pass before merge; merge does not execute the real command.

## 12. Test plan

- First add the focused enablement guard and observe RED against the stale
  future-allowlist documentation.
- Update only the exact allowlist and rerun the focused guard to GREEN.
- Run all `tests/test_r2_issue39_*.py` and the historical dormant-root suites.
- Run architecture, static linter, mechanical, documentation, status, and
  provenance tests.
- Run `python -m unittest discover -s tests`, maintenance scan, and repository
  leakage scan with the pinned project Python 3.12.13 runtime.

## 13. Rollback plan

Before merge, use only forward corrective patches inside this exact allowlist.
After merge, a defect requires a new forward PR; do not reset published history
or delete retained closure, incident, evidence, journal, or host state.

## 14. Human confirmation questions

None for implementation, PR, CI, and merge. The user expressly authorized those
steps. A later fresh explicit authorization remains mandatory before any real
Issue 39 command is run.

## 15. Pre-execution checklist

- [x] Read the exact-master `AGENTS.md`, current Project Status Log, and
  applicable constraints.
- [x] Read and applied `ask-matt`, `codebase-design`, `tdd`, and `code-review`.
- [x] Confirmed the frozen base commit/tree and clean isolated worktree.
- [x] Confirmed Issue 38 is closed and Issue 39 is open.
- [x] Confirmed the task changes no real host state.

## 16. Execution record

- RED: the focused guard passed the import, retained-runner, and dormant-root
  checks, then failed only because the six normative documents did not yet
  contain the exact approved allowlist statement.
- GREEN: `tests.test_r2_issue39_governed_enablement` together with
  `tests.test_generate_project_status` passed 40 tests.
- Affected dormant-root, architecture, static, mechanical, documentation,
  status, mailbox, and multimodal suites passed 198 tests in total.
- The complete `test_r2_issue39_*.py` discovery passed 92 tests with one
  expected skip; `compileall` completed successfully.
- The complete repository suite passed 2,855 tests in 5,813.232 seconds with
  four expected skips.
- Maintenance scanning returned success with only pre-existing low-severity
  stale-document findings; repository leakage scanning returned `total=0`.
- The first Standards/Spec review exposed import-spelling and indirect-entry
  false negatives, an unbound retained-runner constant, mandatory linter-doc
  synchronization, stale document dates, and a review-gate wording mismatch.
  The guard was strengthened test-first, amendment 02 synchronized the required
  logging/static-linter paths, document dates were refreshed, and the affected
  focused/static/status/transport regression passed 86 tests. The post-review
  complete Issue 39 discovery passed 93 tests with one expected skip; the
  architecture/mechanical/static/status/transport set passed 141 tests.
- No real cutover command, closure confirm, protected verifier, service
  operation, ACL change, database swap, or other real-host mutation was run.
