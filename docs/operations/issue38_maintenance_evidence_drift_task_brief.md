---
last_update: 2026-08-13
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue #38 maintenance evidence drift task brief

## Task

- Type: fix
- State: implemented
- Governing baseline: `master@9f736f2e4e367c6e9f4c90e9073a8d37fc572240`
- Confirmed test seams: the public `scripts/maintenance_scan.py` behavior and
  `tests/test_manage_mailbox_vault_stage_knowledge.py`.

## Goal

Review the current setup checklist and remove the newly materialized,
unclassified `stale_doc` finding that makes Solo Maintainer Closure manifest
construction return `R2_SOLO_MAINTAINER_CLOSURE_EVIDENCE_REJECTED` on
2026-08-13, then remove the unrelated date-sensitive test blocker discovered
by full discovery without changing private-knowledge production behavior.

## Non-goals

- Do not weaken or expand the Solo Maintainer Closure maintenance allowlist.
- Do not run `prepare`, `confirm`, the protected verifier, preflight, cutover,
  evidence publication, execution, resume, rollback, or cleanup.
- Do not access a provider, mailbox, vault, private data, credentials, or a
  real host.
- Do not modify the dirty Repository Root, the clean closure worktree, the
  retained CRLF worktree, the ruleset, Issue #38, or Issue #39.
- Do not push, open a pull request, merge, or change remote GitHub state.

## Evidence and diagnosis

- The real read-only closure evidence path reproduced
  `R2_SOLO_MAINTAINER_CLOSURE_EVIDENCE_REJECTED` at manifest construction.
- All other 25 local sources passed.
- `maintenance_scan_output` alone failed because the actual classifications
  contained 20 entries while the frozen registry contained 19.
- The only extra entry was
  `low/stale_doc/docs/operations/setup_checklist.md`, derived from
  `status: draft`, `last_update: 2026-07-11`, and the strict
  `STALE_DRAFT_DAYS = 30` rule.

## Scope

Expected changed files:

- `docs/operations/issue38_maintenance_evidence_drift_task_brief.md`
- `tests/test_maintenance_scan.py`
- `tests/test_manage_mailbox_vault_stage_knowledge.py`
- `docs/operations/setup_checklist.md`
- `docs/operations/project_status_log.md` (generated after implementation)

## Design

1. Add one regression test at the maintenance scan seam proving the reviewed
   setup checklist is not classified as a stale draft.
2. Review every setup-checklist instruction against current repository policy.
3. If the checklist is current and operational, mark it `active` and update
   `last_update`; otherwise stop instead of suppressing the finding.
4. Prove the repaired local maintenance classification set matches the frozen
   closure registry. The exact fixed repository/GitHub manifest gate can only
   be rerun after a separately authorized publication to `master`.
5. Make the stage-knowledge test use the same fixed UTC clock when reading the
   candidate batch that it used when creating it.

## Interface and data changes

- Database: none.
- API: none.
- AI JSON: none.
- Prompt: none.
- Provider or privacy boundary: none.
- Solo Maintainer Closure contract or allowlist: none.

## Security and privacy

- Uses repository metadata and synthetic/offline tests only.
- Does not read or transmit real email, attachments, private knowledge,
  credentials, provider payloads, or vault data.
- Does not grant Issue #38 approval, Issue #39 authority, or execution
  authority.

### Safety checklist

- [x] Does not read real mailbox data.
- [x] Does not send, delete, or archive email.
- [x] Does not store or expose an OpenAI API key in the frontend.
- [x] Treats any email content as untrusted input; no email content is read.
- [x] Does not change AI output parsing or validation.
- [x] Does not log real email, customer data, API keys, or tokens.
- [x] Uses only synthetic or content-free test evidence.

### Issue #110 Solo Maintainer Closure checklist

- [x] `backend.r2_solo_maintainer_closure` retains its exact ten-file package
  and parameterless `prepare()` plus `confirm(...)` public seam.
- [x] Closure still binds exactly five hosted checks and one exact GitHub
  guardrail snapshot and fails closed on drift.
- [x] Guardrail observation remains fixed authenticated GET-only GitHub CLI
  access without caller URL, credential, method, fallback, or cache input.
- [x] Python does not read or emit the GitHub token, and ambient token/host/
  repository/config/proxy overrides remain excluded.
- [x] `pull_request.parameters.required_reviewers` normalization remains
  limited to absent or exact empty-list input.
- [x] The fourteen gates, eight ordered gap proofs, and all zero authority,
  execution, provider, private-data, mutation, and cleanup counts remain
  unchanged.
- [x] Real-console two-input confirmation and the half-open 300-second wall
  plus monotonic freshness contract remain unchanged.
- [x] Create-only/no-replace publication, collision rejection, and retained
  incident stage behavior remain unchanged.
- [x] The no-argument verifier remains independent and rejects legacy V1
  external/signature artifacts.
- [x] `ApprovedCutoverBindingV3` remains the sole binding with one operator and
  zero independent reviewer or external signer authority.
- [x] Execution Confirmation bindings, append-before-attempt claim, and
  attempt consumption remain unchanged.
- [x] Historical journal reconstruction remains non-authorizing.
- [x] Production process roots remain dormant before Issue #39 authority.
- [x] Closure and Execution Confirmation still grant neither Issue #38
  approval nor Issue #39/execution authority; validation remains offline and
  accesses no real host, provider, mailbox, vault, private data, signer, or
  cleanup surface.

## Acceptance criteria

1. The new regression test fails on the frozen baseline and passes after the
   reviewed documentation change.
2. `scripts/maintenance_scan.py` no longer reports
   `docs/operations/setup_checklist.md` as `stale_doc`.
3. The actual maintenance classification set again exactly matches the frozen
   19-entry closure registry without modifying that registry.
4. After this repair is separately published to `master`, the protected
   read-only repository/GitHub/manifest diagnostic can be rerun against the
   exact new remote SHA. This local repair does not claim that later gate.
5. Focused tests, full unit discovery, generated status validation,
   maintenance scan, leakage scan, and `git diff --check` pass.
6. Existing worktrees, dirty-root status, retained damaged refs, GitHub Issues,
   ruleset, closure target, and stages remain unchanged.
7. The stage-knowledge regression passes both alone and in full discovery
   without changing private-knowledge production code.

## Test plan

- `python -m unittest tests.test_maintenance_scan`
- `python -m unittest tests.test_r2_solo_maintainer_closure`
- `python -m unittest tests.test_manage_mailbox_vault_stage_knowledge`
- `python -m unittest discover -s tests`
- `python scripts/generate_project_status.py --output docs/operations/project_status_log.md`
- `python scripts/maintenance_scan.py`
- `python scripts/repository_leakage_scan.py`
- Local maintenance classification comparison against the frozen closure
  registry; the fixed repository/GitHub manifest diagnostic remains a
  post-publication gate.
- `git diff --check`

## Rollback

Before publication, rollback is deletion/reversion of only the five allowlisted
worktree changes. No remote or protected state is in scope.

## Manual decisions

- Maintenance and stage-knowledge test seams: approved by the maintainer on
  2026-08-13.
- Publication, push, PR, merge, closure confirmation, verifier, Issue #38
  comment/closure, and every Issue #39 action remain separately gated.

## Pre-execution checklist

- [x] Read `AGENTS.md`, `CONTEXT.md`, the closure runbook, ADR 0010/0011, and
  the applicable constraint and documentation rules.
- [x] Confirmed exact goal, non-goals, file allowlist, and public test seam.
- [x] Confirmed no mailbox, provider, vault, private-data, real-host, or cleanup
  access.
- [x] Confirmed a new LF linked worktree and unchanged protected worktrees.

## Completion record

- Actual changed files are exactly the five files listed in Scope.
- The regression test failed on the frozen baseline, then passed after the
  checklist review. The complete maintenance module passed 7 tests; the
  maintenance plus Solo Maintainer Closure suites passed 31 tests.
- Maintenance scan returned the exact frozen 19-entry classification set;
  local closure-registry derivation succeeded with observation fingerprint
  `bd971d5584301914d8131b79a4d101230f0ed050f34a2c0fd6458689680bd05c`.
  Repository leakage scan and `git diff --check` passed.
- Initial full discovery ran 2,750 tests in 2,790.022 seconds with 3 skips and
  one unrelated error. The baseline test
  `test_default_adapter_enforces_deadline_scope_and_writes_encrypted_batch`
  writes a batch using fixed `2026-07-14` time and reads it with the real
  2026-08-13 clock, so the 30-day batch is now rejected as
  `candidate_batch_expired`; the same test failed alone. The maintainer then
  expanded the confirmed seam to that test. Its writer and reader now share
  the same fixed UTC clock, and the single regression plus all 11 tests in its
  module pass without production-code changes.
- Fresh full discovery then ran 2,750 tests in 2,904.036 seconds and passed
  with 3 skips.
- Remaining work: separately authorize publication and the post-publication
  protected manifest gate. All closure gates remain separately authorized.
