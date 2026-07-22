---
last_update: 2026-07-22
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Bounded corpus-to-runtime handoffs task brief

## 1. Task name

```text
ratify bounded corpus-to-runtime handoffs
```

## 2. Task type

```text
security | api_contract | docs | test
```

## 3. Current status

```text
complete
```

## 4. Goal

Implement GitHub issue #10 by defining and mechanically enforcing the narrow
architecture that permits a future administrator-triggered incremental sync and
a normal-runtime write-only handoff of validated deidentified evidence from one
explicit current-message Analyze click.

## 5. Non-goals

- Do not implement the incremental synchronization behavior assigned to issue #17.
- Do not implement the candidate job, encrypted inbox storage, UI states, or cancellation assigned to issue #18.
- Do not add mailbox enumeration, a normal API mailbox route, a scheduler, polling, hot reload, or an authority-store reader.
- Do not access a live mailbox, real vault, authority store, provider, credential, or real message.
- Do not change the existing analysis response, public SQLite schema, provider routing, budgets, or fallback behavior.

## 6. Background and sources

This task implements GitHub issue #10 and the architecture/testing decisions in
parent PRD issue #9. Relevant sources:

- `AGENTS.md`
- `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`
- `docs/decisions/0007-multimodal-current-email-analysis.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/security/email_data_handling.md`
- `docs/security/private_knowledge_handling.md`
- `docs/operations/authorized_mailbox_ingest_task_brief.md`

## 7. Scope

Expected additions or changes:

- `backend/current_evidence/`
- `docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md`
- the active architecture, tooling, security, and project-structure documents
- `tests/test_current_evidence_handoff.py`
- `tests/test_architecture_constraints.py`
- `tests/test_mailbox_transport_constraints.py`
- this task brief and the generated project status log

## 8. Technical approach

1. Add a strict immutable `CurrentClickEvidenceV1` value contract for bounded,
   deidentified thread and attachment text. Reject unknown fields, raw source
   locators, unsafe identifiers, placeholders, invalid timestamps, duplicate
   opaque sources, oversized values, and unsupported attachment status. Preserve
   parsed and semantic-review status as separate explicit fields. Reject raw
   header/private metadata shapes, credentials, Base64-like payloads, serialized
   mappings, hidden controls, and explicit provider/model response fields.
2. Expose one submission function that validates before invoking an injected
   append-only callback. The package exposes no read, search, list, query, open,
   key, path, repository, mailbox, or authority capability and performs no I/O.
3. Add ADR 0008, explicitly superseding only the named clauses in ADR 0006 and
   ADR 0007 while preserving click timing, mailbox isolation, read-only
   transport, provider routing, budgets, and restart-only knowledge activation.
4. Add executable import/surface/transport guards so future incremental sync can
   exist only behind the administrator CLI and normal runtime can depend only on
   the contract-only evidence handoff package.

## 9. Data structure and interface changes

### Database

None.

### Public API

None. The handoff is an internal Python contract and injected append-only seam.

### AI output JSON

None.

### Prompt

None.

### Internal contract

`CurrentClickEvidenceV1` contains a UUIDv4 submission ID, a whole-second UTC
creation time, bounded ordered deidentified thread segments, and bounded
deidentified parsed attachment evidence. Submission returns only a fixed
content-free acceptance code after the append callback succeeds.

## 10. Security and privacy checks

- [x] No live mailbox or real data is read.
- [x] No email is sent, deleted, archived, moved, copied, or mutated.
- [x] No credential, key, token, path, source locator, raw record ID, or restoration mapping enters the contract.
- [x] The normal runtime receives no read/search/store-enumeration capability.
- [x] Incremental sync remains administrator-only, manual, fingerprint-gated, and read-only.
- [x] Tests use synthetic values and injected callbacks only.

## 11. Prompt-injection protection

The evidence text remains untrusted content. Construction rejects private or
control artifacts and does not execute links, commands, macros, tools, or
instructions. This task does not send the contract to a provider.

## 12. Acceptance criteria

1. ADR 0008 names the exact ADR 0006 and ADR 0007 clauses it supersedes.
2. The public handoff seam accepts only a strict validated deidentified contract and invokes only an append callback.
3. The handoff package has no historical, raw-vault, authority, mailbox, filesystem, key, reader, or provider capability.
4. Mechanical guards reject forbidden imports and incremental-sync exposure from browser, normal API, scheduler, cleanup, and background surfaces.
5. Existing read-only transport and provider-disabled fallback tests remain green.
6. All verification is synthetic and offline.

## 13. Test plan

- Run one RED -> GREEN vertical slice at the public submission seam for a valid synthetic contract.
- Add RED -> GREEN slices for unsafe text, malformed contracts, duplicate/oversized sources, and callback failure behavior.
- Add architecture and transport guard tests, including synthetic forbidden-import probes.
- Run the focused handoff, architecture, transport, API, config, and documentation suites regularly.
- Run the full unittest suite once after project-status generation, then maintenance and leakage scans.

## 14. Rollback

Revert this task's commit. Because there is no store, migration, public API,
mailbox operation, provider call, or runtime wiring, rollback requires no data or
service migration and leaves the current Analyze path unchanged.

## 15. Human confirmation needed

None. The ticket pre-agrees the public seams and explicitly authorizes only this
bounded architecture. Live sync, encrypted inbox storage, and candidate execution
remain separate tickets and authorizations.

## 16. Pre-execution checklist

- [x] Read `AGENTS.md`, the project status, core constraints, and documentation rules.
- [x] Read issues #9, #10, #17, and #18 to keep later features out of scope.
- [x] Confirmed the two TDD seams: administrator lifecycle guard and current-click submission contract.
- [x] Confirmed no live mailbox, vault, provider, or identifying fixture is needed.
- [x] Preserved the unrelated untracked `frontend/browser_extension.crx`.

## 17. Remote provider private-context checklist

- [x] Providers remain disabled by default; no provider routing or budget changes.
- [x] The handoff accepts only already deidentified, residual-safe text and no media bytes.
- [x] No identity mapping, path, key, bootstrap, vault, DPAPI, authority, or source locator crosses the seam.
- [x] Runtime knowledge remains immutable and startup-only with no reload, polling, hot update, or status endpoint.
- [x] Public API, SQLite, frontend renderer, diagnostics, prompts, and provider output schemas remain unchanged.
- [x] Verification is offline and uses no mailbox, vault, DPAPI, BitLocker, or provider.

## 18. Administrator stage-evaluation checklist

Not applicable. This task does not change stage evaluation.

## 19. Final dataset build and interactive judge checklist

Not applicable. This task does not change private evaluation datasets or judging.

## 20. Bounded corpus-to-runtime handoff checklist

- [x] Any future manual incremental sync remains administrator-triggered,
  read-only, fixed-endpoint, and gated by the exact current inventory fingerprint.
- [x] No sync path was added, and executable guards keep that future path out of
  the browser, normal API, cleanup, scheduler, poller, and background tasks.
- [x] `CurrentClickEvidenceV1` is restricted to one explicit Analyze click and
  validated current-visible sources; runtime construction remains future issue
  #18 scope and is not wired by this task.
- [x] The contract contains only bounded deidentified text and opaque indices;
  it rejects raw headers, identifiers, attachment bytes/names/URLs/paths,
  mappings, provider payloads, and private-knowledge metadata.
- [x] Normal runtime receives only a write-only append callable and no
  reader/search/path/key/repository/raw-vault/authority capability.
- [x] Validation and append failures use fixed content-free codes; no public
  analysis integration was added, so evidence submission cannot alter its result.
- [x] Evidence ingress cannot publish knowledge, mutate authority, rebuild a
  snapshot, or trigger reload, polling, or hot update.
- [x] Public HTTP, SQLite, frontend, provider-disabled fallback, and startup-only
  knowledge loading remain unchanged.
- [x] Tests use only synthetic data and access no mailbox, vault, provider,
  DPAPI, BitLocker, or ignored SQLite file.

## 21. Post-execution record

Implementation changes:

- Added the immutable, strictly validated `CurrentClickEvidenceV1` contract and
  one append-only submission function with fixed content-free outcomes.
- Added ADR 0008 plus architecture, transport, documentation, logging, status,
  and project-structure guards. No sync command, inbox, runtime wiring, public
  schema, provider route, or mailbox operation was added.
- Added behavioral, architecture, transport, documentation, and status-generator
  tests using synthetic values only.
- Closed final review gaps for mailbox/folder/customer identifiers,
  NFKC-normalized Unicode separators/labels, and short space-labeled credentials
  while preserving documented credential-policy prose. Unicode `Cf` format
  controls, `Cs` surrogates, and explicit default-ignorable non-`Cf` ranges now
  fail closed. Placeholder and residual-PII scans use the NFKC validation view.
- Expanded executable guards to use exact import bindings, call-target allowlists,
  a fixed complete binding-inventory fingerprint, and forbidden-capability
  references in every
  current-evidence module. Sync exposure now covers all administrator scripts and
  wrappers plus browser, API, cleanup, local-service, and scheduled workflow
  surfaces, including surface-root-relative path context, executable docstrings,
  bytes/f-strings, literal concatenations, compact lowercase compounds, and natural
  morphology. The binding fingerprint includes Store counts and non-name mutation
  targets; the status-prose exception pins one unrebound `output` Store and the
  exact consecutive canonical `Path` output flow, with no function alias/reference
  escape, plus unique unrebound `pathlib.Path` and `ROOT` bindings and no
  attribute/subscript capability mutation. The complete `parse_args` and `main`
  structures and sole `argparse` binding are pinned, and custom `write_text`
  definitions are rejected. A reviewed full-generator AST SHA-256 fingerprint
  makes any other code-shape change fail closed. The handoff body and complete administrator CLI command/parser surface
  are structurally/runtime pinned, including reflection and mutation targets. Sync
  scanning covers constant reassignment/deep chains, join/format/percent forms,
  multiline frontend concatenation, JS array/template/escape forms, and
  module-script extensions.

Final verification and independent review:

- Final focused handoff/architecture/transport/docs suite: 122 tests passed in
  the repository `.venv`.
- Full discovery: 1,537 tests passed, 1 expected skip.
- Maintenance report: no cleanup findings.
- Repository leakage scan: total 0.
- JavaScript syntax, manifest JSON, compileall, and `git diff --check`: passed.
- Standards review findings, including the missing bounded-handoff completion
  checklist, were fixed; the final standards re-review reported zero findings.
- Specification review found artifact rejection gaps, false positives, one
  pure-alphabetic auth-token bypass, and incomplete package/sync guard coverage.
  Focused RED -> GREEN cases fixed each issue; the final specification re-review
  reported zero findings.
- The authoritative `.venv` reports Python 3.12.13 and SQLite 3.50.4, contains
  the exact locked direct dependencies including `openai==2.45.0`, and does not
  inherit system packages.

Deferred follow-on scope:

- Issues #17 and #18 remain the only owners of actual incremental sync and the
  visible candidate/inbox implementation.
