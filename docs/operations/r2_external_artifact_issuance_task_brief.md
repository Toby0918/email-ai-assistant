---
last_update: 2026-08-06
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 External Artifact Issuance Task Brief

## 1. Task name

Implement Issue #105 final-master-bound public artifact preparation and
installation.

## 2. Task type

```text
feature | security | test | docs
```

## 3. Current status

```text
in_progress
```

## 4. Objective

After Issue #104, add a deterministic public-only two-phase tool that binds one
fresh remote master to one reviewed production-binding candidate and fourteen
gate evidence fingerprints. Phase 1 emits canonical unsigned bodies and public
provenance. Phase 2 accepts only detached signatures, verifies all fourteen
against the pinned producer keys, and publishes exactly fifteen canonical JSON
files to the fixed Git common-directory location without overwrite.

## 5. Non-goals

- Do not read, represent, generate, copy, recover, or use a private key.
- Do not sign, self-sign, create test production signatures, or fabricate
  production evidence.
- Do not accept a caller-selected production-role or gate-evidence fingerprint.
- Do not modify the final verifier, final-master closure schemas, the three
  historical composition roots, workflows, or `AGENTS.md`.
- Do not run a real-host operation, production command, cutover, provider,
  mailbox, vault, private-data, cleanup, overwrite, or deletion operation.
- Do not approve or close Issue #38 and do not modify or start Issue #39.
- Do not run the fixed final verifier until the exact fifteen externally issued
  artifacts exist against the post-merge fresh master.
- Do not modify the dirty primary worktree at
  `D:\Projects\email_ai_assistant`.

## 6. Background and authority

- GitHub Issue #105 is the implementation authority and exact file allowlist.
- The governing decisions are `R2-GOV-EXT-01A`, `02A`, `03`, `03B`, `04A`,
  `04B1`, `04B2`, `05A`, `05B`, `06A`, and `06B`.
- `R2-GOV-EXT-03B` supplies the structural fourteen-gate derivation map. Its
  historical object IDs are not reusable; all values must bind the fresh
  post-Issue-#105 master.
- Issue #104 is closed. The independently verified implementation baseline is
  remote `master@294c526756020d72ca25fd530fd767f142ab7a0d`, tree
  `4f1246949afef69b57ad69f3053e34a585fe09f2`.
- The dedicated clean worktree is
  `D:\Projects\email_ai_assistant_issue_105_r2_external_artifacts` on
  `codex/issue-105-r2-external-artifacts`.
- A merge changes the final-master binding. Production artifacts must therefore
  be prepared only from the new remote master after this implementation merges.

## 7. Exact scope

Only paths listed in Issue #105's Add and Modify allowlists may change. The
following protected surfaces must remain byte-for-byte unchanged:

```text
backend/r2_final_master_closure/
scripts/verify_r2_final_master_closure.py
backend/real_host_preflight_composition/
backend/migration_evidence_publication_composition/
backend/cutover_transaction_composition/
.github/workflows/
AGENTS.md
```

Before staging, compare the diff against the live allowlist and reject every
other path. Stage explicit allowlisted paths only; never use `git add -A`.

## 8. Technical approach

1. Add one deep public-only review-input module. It accepts exact existing
   receipt types for direct gates and a closed `R2GateSourceReviewV1` record for
   the seven composite or human-review gates. It never accepts a final gate
   evidence fingerprint.
2. Preserve the approved derivation map: frozen-master observation; Spec source
   review; exact production-composition formula; Git-byte receipt; reconciled CI
   bundle; ordered Windows receipts; portable receipt; runbook receipt; crash
   and fresh-process source review; retention proof; documentation review;
   Standards review; exact leakage review; and classified maintenance review.
3. Rebuild the production binding only through
   `build_production_binding_candidate_v1` using one final-master binding and
   four unique public authority verification keys disjoint from all fourteen
   gate keys.
4. Emit one immutable unsigned package containing the canonical binding JSON,
   fourteen fixed ordered unsigned bodies, supporting public provenance, file
   SHA-256 values, and one domain-separated issuance-manifest fingerprint.
5. Require a separate exact human-approved issuance-manifest fingerprint before
   phase 2. Accept fourteen gate-ordered detached 64-byte signatures only.
6. Reparse the unsigned package, rederive all fourteen evidence fingerprints,
   verify every signed payload with the pinned Ed25519 public key, and retain the
   original canonical signed body bytes expected by the protected verifier.
7. Resolve the installation location internally from the fixed repository's Git
   common directory. Write one fixed manifest-bound staging directory and use a
   platform no-replace directory publication primitive as the single commit
   point. On Windows, open every exact child by volume file ID with an RWH
   oplock without following a reparse point, and issue that oplock immediately
   after the requiring-oplock open. Preopen the exact directory path, deny
   delete sharing, and immediately issue its Read oplock before binding its
   `FileIdInfo` volume/file ID to the path identity. Keep every pending oplock
   buffer and handle alive, then apply a protected read/execute-only DACL
   through all sixteen already-guarded handles. Validate the locked child file
   IDs, `FileStandardInfo` single-link state, sole default streams, and bytes;
   reject every child or directory ADS and every added hard link;
   and enumerate exact name-plus-file-ID entries through the same directory
   handle without reopening child paths after its oplock. Require
   all sixteen guards to remain quiet before the calling thread synchronously
   renames through the same preauthorized directory handle; keep them held
   through exact target validation, and retain the protected DACL afterward.
   Cancel and synchronously reap pending oplock I/O before releasing its
   `OVERLAPPED`, output storage, event, or file handle.
   Existing final or staging state fails closed and is never removed.
8. Keep the fixed CLI to two phase verbs. It accepts bounded canonical public
   JSON from stdin, emits canonical public output or a fixed failure status, and
   accepts no repository, destination, key-file, environment-key, command, or
   arbitrary filename option.

The pre-approved TDD public seams are, in order:

1. deterministic review-input-to-unsigned-package preparation;
2. detached-signature validation and fixed no-clobber installation.

Tests cross these interfaces and do not expose lower-level fingerprint or path
selectors.

## 9. Data structure and interface changes

### Database changes

None.

### HTTP API changes

None.

### AI output JSON changes

None.

### Prompt changes

None.

### R2 internal interfaces

- Add immutable reviewed-public-input, source-review, unsigned-package,
  detached-signature, and validated-install result values.
- Add deterministic public preparation and fixed installation functions.
- Add one fixed two-verb public CLI adapter.
- Do not change existing production binding or final closure schemas.

## 10. Security and privacy checks

- [x] No mailbox, provider, vault, credential, private store, or private data is
  read.
- [x] Only public keys, public receipts, canonical public bodies, and detached
  signatures cross the new interfaces.
- [x] No private-key type, key generator, signer, `.sign()`, `.generate()`,
  VeraCrypt, `M:`, clipboard, environment-key, or arbitrary key-file capability
  is present.
- [x] The tool has no real-host cutover or production-command capability.
- [x] Public errors, repr, stdout, stderr, and logs remain content-free.
- [x] Tests use synthetic public values and test-owned temporary repositories.
- [x] Issue #38 remains human-only and Issue #39 remains unchanged.
- [x] Windows installation treats the operator/object-security policy as trusted;
  the DACL is not claimed to defeat owner/admin ACL changes, privileged mutation,
  or a deliberately pre-positioned foreign write-capable handle. Those are
  external tamper and fixed-verifier incident-stop conditions.

## 11. Prompt injection protection

Not applicable. The task consumes no email, prompt, provider input, or free-form
executable instruction.

## 12. Acceptance criteria

1. Every gate evidence fingerprint is derived by the approved map and same
   fresh final-master binding; no caller can provide that fingerprint.
2. Production binding construction accepts only exact final master plus four
   unique, gate-key-disjoint public authority keys.
3. The unsigned package contains one canonical binding and fourteen canonical
   fixed-order bodies with zero signatures and complete public provenance.
4. Human review is represented by an exact approved issuance-manifest
   fingerprint and cannot be omitted or substituted.
5. Exactly fourteen detached signatures are gate ordered, length checked, and
   verified against the pinned gate keys and exact body bytes.
6. Installation publishes exactly the fifteen verifier filenames in one
   no-replace commit and never overwrites or removes an existing path.
7. Missing, duplicate, stale, mixed-master, wrong role/domain/key/signature,
   self-certified, noncanonical, reordered, caller-selected, or incomplete
   input fails closed before publication.
8. Production modules contain no private-key, signing, secret, credential,
   private-volume, clipboard, arbitrary key-file, or environment-key surface.
9. The approved focused, affected, architecture, mechanical, documentation,
   maintenance, leakage, compile, diff, and full repository matrix passes.
10. Before external signatures exist, Issue #105 moves only to
    `ready-for-human`. It remains open until the fixed verifier returns
    `AWAITING_SINGLE_HUMAN_FINAL_REVIEW` and the immutable R2-D38-01 through
    R2-D38-14 package is ready.

## 13. Test plan

Use vertical RED to GREEN slices through the two approved interfaces:

1. Review-input and derivation slice: exact type/binding/order, direct and
   wrapper formulas, deterministic binding, and rejection of arbitrary values.
2. Unsigned-package slice: canonical bodies, fixed filenames, manifest hashes,
   zero signatures, complete round-trip validation, and tamper rejection.
3. Signature/install slice: all fourteen valid signatures, wrong/missing/
   duplicate/reordered signatures, canonical signed JSON, fixed common-dir,
   no-clobber, all-or-nothing, retained failed staging state, protected DACL,
   both late-mutation windows, and failure-path event-handle cleanup.
4. CLI slice: exact verbs, bounded canonical stdin, fixed statuses, no path/key
   options, and no production private capability.

After focused GREEN, run the exact `R2-GOV-EXT-06A` matrix, status generation,
maintenance and leakage scans, compileall, `git diff --check`, and the full
repository suite with the pinned Python 3.12.13 virtual environment. Run final
Standards and Spec reviews against the fixed baseline and repair all actionable
findings before publication.

## 14. Rollback approach

Do not rewrite history or use destructive Git commands. Repair only through
allowlisted forward patches in the dedicated worktree. Failed installation
state is retained and reported; repository code does not clean, delete, replace,
or retry it. Any later code rollback is a separate authorized corrective commit.

## 15. Human confirmation boundaries

The Issue and approved governance already fix the implementation seams, so no
additional implementation clarification is required. Separate human action is
still mandatory for production-binding/manifest review, offline signing, any
external public input, final verifier execution, Issue #38 review, and all Issue
#39 activity.

## 16. Pre-execution checks

- [x] Read `AGENTS.md`, `CONTEXT.md`, project status, and live Issue #105.
- [x] Read the required tooling, architecture, linter, task-brief, documentation,
  testing, deep-module, and code-review instructions.
- [x] Revalidated Issue #104 closure and Issue #105's native blocker state.
- [x] Revalidated remote master, exact baseline tree, branch, clean dedicated
  worktree, and dirty primary worktree isolation.
- [x] Recovered the approved structural derivation map and validation matrix.
- [x] Confirmed the exact allowlist, protected surfaces, non-goals, and human
  boundaries.

## 17. Remote provider private-context checklist

Not applicable. Provider routing and private context are unchanged; all
verification is offline and public-only.

## 18. Administrator stage-evaluation checklist

Not applicable.

## 19. Final dataset build and interactive judge checklist

Not applicable.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable.

## 21. Repository placement and operational layout checklist

- [x] Only the dedicated linked worktree is mutable for implementation.
- [x] Installation has one internally fixed Git common-directory target and no
  caller-supplied Repository Root, Project Container, or destination path.
- [x] Existing real composition constructors remain locked before Issue #39.
- [x] Tests are synthetic/offline and perform no real migration, cutover, host,
  provider, mailbox, vault, private-store, or credential operation.

## 22. Post-execution record

```text
Changed files:
- Added backend/r2_external_artifacts_v1/__init__.py
- Added backend/r2_external_artifacts_v1/review_inputs.py
- Added backend/r2_external_artifacts_v1/derivation.py
- Added backend/r2_external_artifacts_v1/unsigned_package.py
- Added backend/r2_external_artifacts_v1/installer.py
- Added docs/operations/r2_external_artifact_issuance_runbook.md
- Added docs/operations/r2_external_artifact_issuance_task_brief.md
- Added scripts/prepare_r2_external_artifacts.py
- Added tests/test_prepare_r2_external_artifacts.py
- Added tests/test_r2_external_artifacts_v1.py
- Added tests/test_r2_external_artifacts_v1_architecture.py
- Modified docs/constraints/architecture_constraints.md
- Modified docs/constraints/linter_constraints.md
- Modified docs/constraints/mechanical_rule_translation.md
- Modified docs/conventions/logging.md
- Modified docs/operations/project_status_log.md
- Modified docs/operations/project_structure.md
- Modified docs/operations/testing_checklist.md
- Modified docs/security/project_container_cutover_contracts.md
- Modified scripts/generate_project_status.py
- Modified tests/test_architecture_constraints.py
- Modified tests/test_generate_project_status.py
- Modified tests/test_mailbox_transport_constraints.py
- Modified tests/test_mechanical_rule_constraints.py
- Modified tests/test_multimodal_documentation_contracts.py
- Modified tests/test_r2_operator_runbook_v2_architecture.py
- Modified tests/test_r2_retention_ledger_v2_architecture.py
- Modified tests/test_static_linter_constraints.py

Test results:
- Pinned Python 3.12.13 full discovery: 2776 tests, OK, 3 skipped.
- Issue #105 package, architecture, and CLI: 43 tests, OK.
- Affected R2 matrix: 15 + 31 + 43 + 48 tests, all OK.
- Final maintenance/status/leakage/constraint guard group: 139 tests, OK.
- Windows race repetitions: 160/160, OK.
- Windows handle stress after 10-test warmup: 100 tests, 200 -> 200,
  delta 0.
- Generated status is exact; compileall and git diff checks exit 0.
- Maintenance --fail-on-high exits 0 with 19 pre-existing low stale-doc
  findings and no high finding; repository leakage scan reports total 0.
- Independent Standards and Spec review reports no remaining P0-P2 code
  finding. The full discovery preceded only this post-execution record update;
  final hosted checks must validate the published commit.

Incomplete items:
- External public inputs, human review, offline signatures, installation,
  final verifier, immutable R2-D38 review package, and Issue closure remain
  pending until their exact phase gates are satisfied.
```
