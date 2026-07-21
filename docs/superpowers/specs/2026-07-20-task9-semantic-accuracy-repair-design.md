---
last_update: 2026-07-20
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: product_spec
---

# Task 9 Semantic Accuracy Repair Design

## Decision

Task 9 uses an evidence-reconciliation gate, not a parser-status gate. The result is
eligible for release only when the current message, bounded verified history, and
every model-visible parsed attachment are represented and reconciled. Extraction, semantic correctness, and human usefulness are three separate measurements.

## Evidence flow

```text
verified current page
  -> current message + chronological verified history
  -> one shared backend full-timeline build
  -> deterministic facts and unresolved-state analysis
  -> bounded provider source projection
  -> parsed attachment source coverage
  -> strict evidence and safety merge
  -> human-reviewed result
```

The current message is authoritative for the latest request but does not erase
historical decisions. Completed historical outcomes, changed values, and unresolved
attachment discrepancies remain visible to the analysis.

## Thread contract

- Frontend `thread_segments` contains history only, ordered oldest-to-newest.
- The backend appends the current message exactly once, even if a legacy collector
  accidentally included an exact current duplicate.
- Deterministic and model timelines consume the same complete bounded source set.
- Provider source JSON declares `message_role=current|history`; history also carries
  a zero-based chronological position.
- A verified adjacent-history window is retained for terse replies even without an
  identifier, topic, or parseable external address match.
- Limits remain explicit and fail soft with `context_limited=true`; truncation is
  never represented as a complete thread.
- Safe sibling history requires a complete legacy header and membership in the
  verified message region. The document body is never a generic extraction scope.

## Attachment contract

- `parsed` means that bounded readable content was produced.
- `parsed` does not mean full-file parsing, correct attachment identity, semantic
  completeness, or correct final analysis.
- Private attachment evidence preserves source ID, sanitized bounded text,
  truncation, and fixed parser limitations.
- Character-bounded attachment text drops an incomplete trailing clause at a
  conservative sentence boundary. Abbreviations, initialisms, decimals, and an
  end-position ASCII period in a truncated buffer are not accepted as boundaries;
  no-space CJK text retains bounded complete `。！？` sentences.
- Every attachment source actually sent to a provider requires exactly one
  source-bound augmentation. Missing, duplicate, or ungrounded coverage fails closed.
- Provider-visible limitations are untrusted-context metadata, not executable text.
- The deterministic layer adds semantic-review and bounded cross-source warnings.
  It never selects a winner when sources disagree.
- Backend safeguards are re-applied after model merge so a model cannot erase them.
- Locally extracted attachment facts remain byte-for-byte authoritative. Validated
  model additions are deduplicated and appended only while the five-item public
  bound has capacity.

## Human gold-standard method

Future real-mail improvement uses a versioned private-evaluation V2 rather than Git
fixtures or model self-training:

1. An administrator selects one authorized thread and its reviewed attachments by
   opaque bindings.
2. Local staging decrypts one raw object at a time, deidentifies it, performs a
   residual scan, releases raw material, then composes an ordered deidentified thread.
3. A business author records the expected current request, resolved historical
   decisions, required facts, conflicts, risks, actions, and reply constraints before
   seeing a model suggestion.
4. ChatGPT may analyze only the approved deidentified thread and attachment evidence
   as a labeling assistant. Its transcript and raw response are not the gold record.
5. The business author revises the structured reference; separate business and
   privacy reviewers approve the same revision. High-risk disagreements are manually
   adjudicated.
6. Candidate models cannot read the reference. Human judges see the deidentified
   evidence and candidate output without model identity. Reports contain aggregate
   counts and rates only.

This process makes accuracy auditable and measurable. It cannot guarantee that a
probabilistic model is correct on every future email.

## Compatibility

- Public analysis JSON and SQLite remain unchanged.
- Existing V1 private datasets remain readable.
- V2 staging/review implementation is a separate security task and must not silently
  reinterpret V1 artifacts.
- Remote providers, browser permissions, and mailbox access remain disabled or
  unchanged by default.
