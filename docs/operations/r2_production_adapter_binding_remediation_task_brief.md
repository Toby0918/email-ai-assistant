---
last_update: 2026-08-04
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 Production Adapter Binding Remediation Task Brief

## 1. Task name

Implement Issue #104 production adapter binding remediation.

## 2. Task type

```text
refactor | security | test | docs
```

## 3. Current status

```text
in_progress
```

## 4. Objective

Replace the production callback binding with exactly three nominal stateful
Adapter slots for preflight, evidence publication, and transaction. Bind every
fixed command to the exact Adapter type identity and command domain, add the
deterministic `ApprovedCutoverBindingV2` candidate builder, and reconnect the
three production process bootstraps without making any operator path executable.

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
- Frozen baseline is remote
  `master@7a97afb53133b6a2bae31e8838fb234b800f8021`, tree
  `47b30c83af6693f8efedaae574c1a2b92b0305ac`.
- The dedicated worktree is
  `D:\Projects\email_ai_assistant_issue_104_r2_adapter_binding` on
  `codex/issue-104-r2-adapter-binding`.
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
Actual changed files:
- 47 paths are staged: 45 paths from the Issue #104 exact allowlist plus
  `tests/test_mailbox_transport_constraints.py` and
  `tests/test_r2_obsolete_surface_contract.py`, which the operator separately
  authorized on 2026-08-04.
- The protected operator runbook has no Git diff. Its worktree bytes were
  restored to the exact LF bytes already stored in `HEAD` so the frozen
  renderer contract could be validated without a content change.

Test results:
- Vertical adapter, composition, binding-candidate, process, and bootstrap
  slices were each observed RED before their corresponding GREEN.
- The focused and affected R2 matrix passed 90 tests; the architecture,
  mechanical, static, and documentation constraint matrix passed 118 tests.
- The four previously blocked repository tests passed after the separately
  authorized guard updates and byte-exact runbook checkout repair.
- The full repository suite passed on the required bundled Python 3.12.13:
  `Ran 2720 tests in 2662.999s` and `OK (skipped=3)`.
- `maintenance_scan.py --fail-on-high` passed with only pre-existing low
  stale-document findings. The repository leakage scan returned zero findings.
- `compileall` and `git diff --check` passed.

Incomplete items:
- Push, PR, merge, Issue closure, Issue #105, external artifacts, final-master
  verification, Issue #38 review, and Issue #39 remain outside this authority.

Follow-up:
- Report the staged local implementation and validation only. Await separate
  commit or publication authorization.
```
