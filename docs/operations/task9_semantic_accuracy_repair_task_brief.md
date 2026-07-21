---
last_update: 2026-07-20
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Task 9 Semantic Accuracy Repair Task Brief

## Task

Repair Task 9 so that completion means the current request, bounded visible history,
and parsed attachments were reconciled into the result. A `parsed` attachment status
is acquisition evidence only and is never a semantic-accuracy acceptance signal.

## Type and state

```text
fix | security | prompt | test | operation_guide
approved
```

## Goal

Use one consistent evidence set for the deterministic timeline and remote model,
make current-versus-history roles explicit, carry attachment truncation and parser
limitations into the private prompt, and require every sent parsed attachment to be
accounted for. Preserve deterministic warnings when bounded sources disagree or are
incomplete.

The future real-mail evaluation method is also fixed here: locally deidentified full
threads plus reviewed attachment evidence, an independently authored human reference,
business and privacy approval, blinded candidate judging, and aggregate-only reports.
This is an evaluation and knowledge-improvement workflow, not automatic model training.

## Non-goals

- No mailbox navigation, enumeration, scan, send, delete, move, or archive.
- No live provider call, real attachment read, SQLite inspection, or browser operation.
- No public response or SQLite schema change; the only request addition is the
  content-free optional thread-limitation boolean documented below.
- No weakening of local authority for exact identifiers, dates, amounts, quantities,
  or tracking values.
- No real or derived email text in Git, tests, docs, logs, or public outputs.
- No automatic upload, fine-tuning, model self-grading, production model switch, or
  claim of guaranteed accuracy.

## Evidence and root causes

1. The frontend defines `thread_segments` as history-only, while the deterministic
   backend timeline currently omits the current message.
2. A safe Tencent legacy page can place complete-header history as bounded siblings;
   the resolver currently narrows to the current message when the common ancestor is
   `document.body`.
3. Topic, identifier, and address-only history relevance can discard the immediately
   preceding message required to understand a terse reply.
4. Attachment parsing is bounded before model projection, while the prompt omits the
   truncation and parser-limit state.
5. A successful parse does not prove that the attachment changed or constrained the
   analysis, and the old live smoke checked status and cleanup only.

## Technical contract

1. `thread_segments` remains history-only and oldest-to-newest. One backend helper
   appends the current message exactly once and supplies the same complete bounded
   source set to the deterministic timeline and model selection.
2. The Tencent resolver may expose only complete-header, layout-visible, bounded
   sibling history that belongs to the verified message region. It never authorizes
   arbitrary `document.body` text, mailbox chrome, or attachment controls as history.
3. The remote prompt identifies the current source and every chronological history
   source explicitly. When verified history exceeds limits, `context_limited` is true.
4. Parsed attachment model sources include fixed truncation and parser-limit metadata.
   The provider must account for every sent parsed attachment with a source-bound
   augmentation. Projection-created trailing fragments are removed at conservative
   complete-sentence boundaries; abbreviations and decimals are not sentence ends,
   while bounded CJK `。！？` sentences remain available. Missing coverage fails
   closed to the deterministic result.
5. Backend-generated semantic-review and cross-source warning items survive model
   merge. Deterministic attachment facts are deep-copied byte-for-byte; validated
   model additions are deduplicated and may only fill the remaining five-item bound.
   The deterministic layer never guesses which conflicting source is correct.
6. Synthetic fixtures mirror the structure and decision pattern only. They contain
   no real names, addresses, identifiers, prices, quantities, dates, filenames, or
   copied prose.

## Data and interface changes

- Database: none.
- Public HTTP JSON: one backward-compatible optional request boolean,
  `thread_context_limited`; only literal `true` is honored, no diagnostic text
  crosses the request boundary, and there is no response schema change.
- SQLite projection: none.
- Private prompt JSON: add explicit source role/order plus attachment truncation and
  parser-limitation metadata.
- Private evaluation: document a versioned V2 handoff for ordered thread records,
  reviewed attachment bindings, encrypted human reference, and blinded judging. V1
  remains compatible and no real dataset is opened in this task.

## Security checklist

- [x] Providers remain disabled by default.
- [x] All new automated evidence is synthetic and offline.
- [x] Current-message click-only and current-visible-thread boundaries remain intact.
- [x] Attachment bytes remain request-local and are removed in `finally`.
- [x] Email and attachment inputs remain untrusted data, never instructions.
- [x] Exact facts remain locally extracted and locally authoritative.
- [x] Private evaluation remains encrypted, deidentified, dual-reviewed, and
  aggregate-only.

## Acceptance

1. The current message changes the deterministic conversation status and appears
   exactly once in the model source set.
2. A recreated safe sibling-history fixture is extracted oldest-to-newest, while
   incomplete headers, unrelated body siblings, and stale replacements fail closed.
3. A terse current reply retains a bounded adjacent verified history window.
4. Prompt sources explicitly distinguish current versus history and disclose
   attachment truncation and parser limitations.
5. Every sent parsed attachment is represented by one valid augmentation; omission
   causes a fixed safety fallback.
6. Provider-disabled analysis of a parsed attachment without structured facts adds a
   semantic-review requirement rather than implying the attachment was understood.
7. Deterministic cross-source warnings and must-check items cannot be removed by a
   model merge.
8. Task 9 documentation no longer calls semantic gates complete merely because
   attachment status is `parsed`.
9. Focused tests, full unit tests, JavaScript syntax, architecture/static/mechanical
   checks, leakage scan, maintenance scan, status generation, and `git diff --check`
   pass offline.

## Rollback

Revert this repair as one feature-branch series. No database migration, mailbox
mutation, provider-side state, or persistent attachment cleanup is required.

## Human authorization boundary

The operator approved this offline repair and the future evaluation method. A new
real-email click test, mailbox import, private dataset run, or provider call still
requires its own explicit authorization.

## Execution record

- Offline implementation and independent review are complete. Current/history
  ordering, explicit source roles, attachment semantic coverage, complete-sentence
  text grounding, qualitative-only visual grounding, and deterministic merge
  safeguards are covered by synthetic tests.
- The V2 real-mail gold-standard contract is documentation-only; the existing V1
  runtime and CLI surfaces were not widened.
- No live mailbox, browser, provider, API, SQLite, real attachment, or private
  evaluation dataset was accessed or opened.
