---
last_update: 2026-07-29
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 59 Project Container composition task brief

## 1. Task name

```text
Issue #59 assemble and lock the real-host Project Container compositions
```

## 2. Task type

```text
security
```

## 3. Current status

```text
final_validation
```

## 4. Goal

Implement only Issue #59 from exact remote
`master@4dd5183c7cb2731f519b0516516d9c0eb4490804`. Assemble the
read-only preflight, create-only evidence publication, and journal-driven
cutover transaction behind three physically separate, default-locked operator
roots. Prove their integration and complete receipt chain only with portable
contracts and caller-owned synthetic Windows sandboxes.

## 5. Non-goals

- Do not run a real preflight, HostBaseline collection, Migration Evidence
  Package review/create/verify, final audit, or recovery inspection.
- Do not stop, start, probe, discover, or modify a real service.
- Do not create, move, replace, repair, copy, or inspect a real repository,
  worktree, Runtime, database, CRX, Config, ACL, evidence package, journal,
  failed Container, rollback publication, provider, mailbox, vault, private
  store, credential, or private content.
- Do not accept arbitrary paths, source or target selections, worktree names,
  database/Runtime/artifact/Config/ACL/rollback objects, shell, PowerShell,
  Git command, executable, environment, provider, or dynamic adapter fields.
- Do not issue, mint, generate, sign, or otherwise manufacture real-host
  authorization.
- Do not modify or close Issues #38/#39, close parent Spec #50, merge the pull
  request, issue a real command, or claim R1 is executable.
- Do not expand cleanup, scheduler, browser, normal runtime, mailbox, provider,
  vault, private-knowledge, private-evaluation, HTTP, SQLite schema, Prompt, or
  AI output authority.

## 6. Background and references

- GitHub Issue #59, parent Spec #50, and closed dependencies #54 through #58.
- Issue #38 R1 approval record, which remains
  `NOT EXECUTABLE - BLOCKED_PENDING_REAL_PREFLIGHT_COMPOSITION`.
- Issue #39, which remains unstarted and blocked by Issue #38.
- `AGENTS.md`, `CONTEXT.md`, and the current project status log.
- `docs/decisions/0009-project-container-and-repository-boundaries.md`.
- `docs/security/project_container_cutover_contracts.md`.
- `docs/operations/project_container_migration_task_brief.md`.
- Issue #51 through #58 task briefs and their implemented contract,
  preflight, evidence, mutation, repository, managed-publication, and service
  lifecycle packages.
- Tooling, architecture, linter, mechanical, CI, documentation, testing,
  review, maintenance, and repository-leakage constraints.

The dirty root and every pre-existing worktree are preserved. Work occurs only
in `D:\Projects\email_ai_assistant_issue_59_final_composition` on
`codex/issue-59-final-composition`.

## 7. Scope

Expected additions:

- `backend/cutover_composition_contracts/` for strict content-free,
  profile/master/operator/authorization-sequence-bound composition receipts
  and the final chain.
- `backend/real_host_preflight_composition/` for the fixed read-only
  preflight, HostBaseline, evidence review/verify, final-audit readiness, and
  recovery-inspection root.
- `backend/migration_evidence_publication_composition/` for the fixed
  create-only evidence-publication root.
- `backend/cutover_transaction_composition/` for fixed execute, resume, and
  rollback over one journal owner and one closed adapter set.
- Focused portable, architecture, capability, leakage, race, crash,
  no-clobber, and Windows end-to-end sandbox tests.
- This task brief.

Expected synchronized changes:

- ADR, domain context, operations, security, tooling, architecture, linter,
  mechanical, testing, review, project-structure, maintenance, leakage, and
  generated project-status documentation.

No frontend, normal-runtime API, real operator CLI, service command, workflow,
scheduler, cleanup action, dependency, provider client, mailbox, vault, private
store, or arbitrary host adapter is in scope.

## 8. Technical approach

### 8.1 TDD public seams

Tests observe only the Issue-approved seams:

1. `RealHostPreflightComposition` with six exact read-only role adapters and
   fixed methods for current-topology preflight, HostBaseline, evidence
   review/verification, final-audit readiness, and recovery inspection.
2. `MigrationEvidencePublicationComposition` with one exact create-only role
   that requires the exact confirmed review fingerprint.
3. `CutoverTransactionComposition` with fixed execute, resume, and rollback
   methods, one exact journal owner, and a closed adapter bundle.
4. strict composition-stage receipts and one final
   `ProjectContainerReceiptChainV1`.
5. phase-specific, default-locked real constructors and entries.
6. mechanical package/import/consumer/capability and leakage guards.
7. one Windows-only end-to-end test-owned sandbox composition and portable
   tests that explicitly make no Windows/NTFS/ACL claim.

Each vertical slice starts with one failing test at one of these public seams,
implements the minimum behavior, and reruns the focused suite before the next
slice.

### 8.2 Physical root isolation

The three operator-root packages never import each other. They may import only
the pure composition-contract package, exact Issue #51 contract bridges, and
their own closed value/role modules. Capability-specific implementation
packages remain behind exact internal bridges or caller-bound fixed roles.

Mechanical AST guards pin:

- every package file and public export;
- every absolute and relative import;
- every cross-package bridge;
- the complete approved consumer allowlist;
- forbidden process, shell, PowerShell, dynamic import, environment, network,
  provider, mailbox, vault, private-data, cleanup, scheduler, browser, normal
  runtime, logging, path-selection, and arbitrary command capabilities.

### 8.3 Fixed role surfaces

The preflight root accepts exactly six read-only roles. The evidence root
accepts exactly one create-only publication role. The transaction root accepts
only the fixed journal owner and fixed ACL, pre-mutation, repository, managed
publication, activation, final-audit, inspection, resume, rollback, failed
Container, and legacy-health roles required by the approved state machine.

Role bundles are exact frozen nominal values with repr-hidden callables. They
cannot accept extra fields, mappings, subclasses, duck-typed values, arbitrary
selection arguments, or dynamic command values.

### 8.4 Authorization lock

Every real constructor and entry validates only the exact nominal Issue #51
authorization for its operation and phase:

- preflight/review/verify/readiness/inspection use
  `RealPreflightAuthorizationV1`;
- evidence create uses `EvidencePublicationAuthorizationV1`;
- execute/resume use `CutoverExecutionAuthorizationV1`;
- rollback/recovery use `RecoveryAuthorizationV1`.

Missing, malformed, expired, wrong-operation, wrong-phase, wrong-profile,
wrong-master, wrong-operator, mapping, receipt, subclass, duck-typed, and
`TestSandboxAuthorizationV1` values are rejected with fixed content-free
status. An otherwise valid real authorization still returns
`BLOCKED_NO_APPROVED_COMMAND`, with `blocked=1` and `executed=0`, until a
separately approved Issue #39 implementation exists.

Backend packages expose no executable test binder. Test-only assembly lives in
`tests/cutover_composition_binders.py`, requires the complete exact
`TestSandboxAuthorizationV1` sequence plus an internally created temporary
scope that accepts no caller-selected root, and cannot enter a real constructor
or entry. Every component `TemporaryDirectory` owner is registered to that
scope; every role and journal callback holds the scope lock from liveness
check through callback completion. Close first marks the scope irreversibly
inactive under that lock and only then cleans owned directories, so cleanup
failure or a concurrent callback cannot expose an active half-cleaned scope.
Closing or forging the scope therefore fails before any new original callback.

### 8.5 Complete receipt chain

The strict chain binds:

- one operation fingerprint;
- one exact immutable Profile fingerprint;
- one governing master commit;
- one operator fingerprint;
- one ordered authorization-sequence fingerprint;
- exact review and independently verified package fingerprints;
- exact ACL baseline and fresh single-use pre-mutation receipt;
- one journal-owner fingerprint, exact prior/current durable journal-head
  links, and the terminal receipt fingerprint;
- final-audit readiness and final-audit result;
- exact managed publication and provider-disabled activation receipts;
- failed-Container preservation, rollback restoration, legacy health, and
  final recovery state.

Every stage is a closed, canonical, content-free value. A stage can only append
after the required predecessor, exact binding, and exact prior journal head
match. Every partial chain must be an exact nonempty prefix of one approved
terminal sequence. The chain fingerprint commits the ordered stages and
terminal receipt, which recursively commits every predecessor. Receipt,
operation, Profile, master, operator, authorization sequence, validity,
journal head, or state drift fails closed. A receipt is never authorization.

### 8.6 Execute, resume, and rollback

`execute()` requires the complete accepted preflight/evidence chain, exact ACL
baseline, and a fresh pre-mutation gate before the first mutation. The journal
owner atomically claims that exact gate across composition instances, and its
injected clock rechecks authorization expiry before every role boundary.
Every fixed mutation is delegated to the exact role and advances only after a
validated receipt and prior/current journal-head link.

`resume()` starts with inspection and a fresh execution authorization. It may
continue only a separately classified, committed journal state and never
replays an unknown effect or guesses a postcondition.

`rollback()` starts with inspection and exact pre-bound recovery
authorization. It preserves new evidence and the failed Container before
restoring only committed journal stages, verifies original topology and ACL/
database/sidecar state, and starts legacy service only through the fixed
provider-disabled recovery role.

### 8.7 Windows end-to-end sandbox

Windows integration runs only under a test-owned temporary sandbox and composes
the actual approved seams for:

- two-pass current-topology preflight and fresh gate;
- HostBaseline plus evidence review, create-only publication, independent
  verification, and receipt agreement;
- fixed-role ACL baseline/publication/inheritance;
- exact 8 embedded plus 3 external repository/worktree forward transaction;
- create-only Runtime, LocalData, CRX, and Config publication;
- provider-disabled activation;
- failed-Container and new-evidence preservation;
- committed-journal reverse restoration and provider-disabled legacy health.

The harness sends the forward ACL-through-activation roles through
`CutoverTransactionComposition.execute()`. The fixed final audit rejects the
known failed activation; the test reconstructs only the exact committed
journal prefix and then enters a separately bound rollback action. The harness
binds the accepted #55 ACL policy receipt into the #56 transaction Profile,
uses the actual #56 forward receipt and durable journal head, and passes the
actual four-receipt #57 set directly into the #58 lifecycle/controller. The
new-service data-role evidence must equal that exact database receipt; no
substitute publication receipts are constructed. The harness
asserts no production path, credential, provider, mailbox, vault, private
store, or private content is reachable.

### 8.8 Race, crash, and no-clobber matrix

Focused and affected suites cover:

- reparse insertion, parent/source replacement, target appearance;
- service/database/worktree/ACL/receipt/journal/profile/master/operator drift;
- authorization expiry before every meaningful boundary;
- every forward and reverse intent/effect/observation/commit gap;
- package, journal record, directory, worktree, Runtime, database, CRX,
  Config, failed Container, and recovery-publication collision;
- no blind retry, no guessed recovery, no cleanup-by-delete, and no overwrite.

Issue #59 adds integration regression tests for the chain and composition
boundaries while retaining the complete component matrices from #53 through
#58 as affected evidence.

### 8.9 Output leakage

Closed schemas reject:

- paths, filenames, drive names, SID, SDDL, account names;
- Git refs, object IDs, branch/worktree/admin names, commands;
- shell/PowerShell/native command text and exception/native error text;
- credentials, tokens, mailbox/provider/vault/private content;
- database rows or queries;
- arbitrary strings, mappings, nested content, and unapproved dynamic fields.

`repr`, receipts, journal summaries, return values, stdout, stderr, and logs
contain only fixed enums, opaque fingerprints, and allowlisted bounded counts.

### 8.10 Platform claims

Portable tests prove closed values, authorization, ordering, state, import,
capability, and leakage contracts. They explicitly do not claim NTFS file ID,
Windows ACL, Windows reparse, native no-replace, service, Runtime-build, SQLite
lock, or durable Windows filesystem behavior. Only Windows tests under the
validated caller-owned sandbox may make those claims.

## 9. Data structure or interface changes

### Database changes

```text
None.
```

### API changes

```text
No public HTTP or frontend API change. New internal operator composition
packages and content-free contract values only.
```

### AI output JSON changes

```text
None.
```

### Prompt changes

```text
None.
```

## 10. Security and privacy checks

- [x] No real mailbox, provider, vault, private store, credential, or private
  content is read.
- [x] No automatic email send, delete, archive, or mailbox navigation is added.
- [x] No frontend key, endpoint, operator root, or host capability is added.
- [x] Normal runtime, browser, cleanup, scheduler, and workflows cannot import
  operator roots.
- [x] All test samples and receipts are synthetic and content-free.
- [x] All real entries remain non-executable before Issue #39.

## 11. Prompt Injection protection

This task does not change email, provider, Prompt, analysis, or reply-draft
paths. Operator roots accept no email body, attachment, instruction, free text,
or public request field.

## 12. Acceptance criteria

The GitHub Issue #59 acceptance criteria are authoritative. In addition:

1. the three root packages, pure contract package, import maps, exports,
   consumers, signatures, and fixed roles are mechanically pinned;
2. every real constructor/entry returns a fixed blocked/rejected result and
   never calls a role;
3. the final chain accepts only exact ordered same-binding receipts;
4. Windows sandbox proof and portable claims remain explicitly separated;
5. all component and integration race/crash/no-clobber matrices pass;
6. all required docs describe the same default-locked non-executable state;
7. #38 stays open/ready-for-human, #39 stays unstarted, and R1 stays NOT
   EXECUTABLE;
8. no real-host or private-data operation occurs.

## 13. Test plan

- Focused: all new Issue #59 contract, root, architecture, lock, chain,
  leakage, race/crash/no-clobber, and Windows sandbox modules.
- Affected: Issue #51 through #58 focused suites plus repository
  architecture/security/constraint/status tests.
- Full: `python -m unittest discover -s tests`.
- Compile: Python `compileall`; frontend JavaScript syntax and manifest JSON.
- Documentation, architecture, linter, mechanical, transport, maintenance,
  repository-leakage, and `git diff --check`.
- Separate Standards and Spec reviews against exact baseline
  `4dd5183c7cb2731f519b0516516d9c0eb4490804`; repair and re-review P1/P2,
  record P3 only.

## 14. Rollback plan

Before publication, abandon only the new isolated Issue #59 worktree/branch;
the dirty root and every existing worktree remain untouched. After publication,
revert only the explicit Issue #59 commit in a separately authorized change.
No test or task rollback deletes or modifies any real host material.

## 15. Human confirmation questions

```text
None. Issue #59 and parent Spec #50 already fix the public seams, capability
boundaries, authorization phases, test environment, non-executable state,
documentation scope, validation, review, and PR delivery requirements.
```

## 16. Pre-execution checklist

- [x] Live Issue #59 and parent Spec #50 were read.
- [x] Dependencies #54 through #58 are all closed/completed.
- [x] Remote master exactly matched the authorized baseline.
- [x] Issue #38 remains open/ready-for-human and blocked by #59.
- [x] Issue #39 remains open/unstarted and blocked by #38.
- [x] The single R1 record remains explicitly NOT EXECUTABLE.
- [x] Root status and all existing worktrees were captured and preserved.
- [x] A fresh sibling worktree and `codex/` branch were created.
- [x] `AGENTS.md`, `CONTEXT.md`, status, tooling, architecture, linter, task
  brief, tracker, security, ADR, and related Issue task constraints were read.
- [x] No new dependency or real-host/private-data authority is required.

## 17. Remote provider private-context checklist

Not applicable. Provider paths, private context, budgets, and runtime knowledge
are unchanged. Providers remain disabled in all tests.

## 18. Administrator stage-evaluation checklist

Not applicable. Raw-vault and private-evaluation handoffs are unchanged.

## 19. Final dataset build and interactive judge checklist

Not applicable. Private evaluation is unchanged.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable. Mailbox ingest and current-click evidence are unchanged.

## 21. Repository placement and operational layout checklist

- [x] No new placement mode or arbitrary path/role override is added.
- [x] All roots consume one exact immutable `CutoverProfileV1`.
- [x] Real authorization remains external, exact-type, phase-specific, and
  impossible to mint in the prerequisite.
- [x] Test authorization cannot enter a real constructor or entry.
- [x] Receipts remain content-free evidence and never authorization.
- [x] ContainerAudit remains unchanged and separately injected.
- [x] Evidence create remains separately confirmed, create-only, and
  independently verified.
- [x] All mutation/publication/lifecycle execution stays in caller-owned
  synthetic Windows sandboxes.
- [x] Linux tests make no Windows/NTFS/ACL assertion.
- [x] Cleanup, deletion, merge, #38/#39 mutation, and parent #50 closure remain
  unauthorized.

## 22. Post-execution record

Implementation completed in the isolated Issue #59 worktree:

- added the pure composition authorization/binding/receipt-chain contracts;
- added three physically separate, binding-bound operator roots;
- kept every real constructor and entry default-locked and test-authority
  rejecting;
- added exact import/export/consumer/signature/capability, receipt, leakage,
  platform-claim, coverage-ownership, and single-action tests;
- removed all executable test binders from backend packages; test-only
  assembly now requires an internally owned temporary scope;
- hardened partial-chain prefix validation, recursive terminal receipt
  commitment, prior/current journal-head linking, initial-head verification,
  per-boundary expiry checks, and cross-composition gate replay prevention;
- added one Windows-only E2E that composes the existing #53-#58 test-sandbox
  seams through transaction-root forward execution, failed activation,
  failed-Container preservation, reverse restoration, and legacy health with
  zero provider attempts;
- synchronized ADR, migration brief, operations, security, tooling,
  architecture, linter, mechanical rules, domain context, project structure,
  status generator, and generated project status.

The first Standards/Spec review found no P3 and identified four Standards P2
plus two Spec P1/four Spec P2 issues. All findings were repaired test-first;
the first Standards re-review was clean, while the first Spec re-review found
three remaining P2 items covering scope lifetime/ownership, terminal
freshness, and actual #55-#58 E2E data flow. Those three items were repaired
test-first. The next same-axis pass found one Standards P2 for atomic
fail-closed scope closure and one Spec P2 for the resume-result expiry
regression; both were repaired test-first. Final Standards and Spec re-reviews
now report no P1, P2, or P3 findings. Integrated full validation, exact
allowlist publication, remote CI, and final live Issue/Spec recheck remain to
be recorded before this brief becomes complete.

No real host, service, evidence package, repository/worktree, ACL, Runtime,
database, CRX/Config, provider, mailbox, vault, private store, credential, or
private-data operation was performed.
