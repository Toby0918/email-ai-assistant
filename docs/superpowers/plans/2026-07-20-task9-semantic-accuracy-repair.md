---
last_update: 2026-07-20
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Task 9 Semantic Accuracy Repair Implementation Plan

> Execution mode: Subagent-Driven Development with strict RED, GREEN, independent
> review, and controller verification. All operations are synthetic and offline.

## Task 1: Reopen the semantic release gate

Files:

- `docs/superpowers/plans/2026-07-16-multimodal-current-email-analysis.md`
- `.superpowers/sdd/progress.md`
- active Task 9 status and testing documents
- documentation contract tests

Steps:

1. Add failing tests that reject any Task 9 closeout based only on `parsed` status.
2. Replace final-integration-only language with the explicit semantic repair gates.
3. Record extraction, semantic correctness, and human usefulness as distinct gates.

## Task 2: Build one complete bounded thread evidence set

Files:

- `frontend/browser_extension/content/exmail_visible_context.js`
- `frontend/browser_extension/content/current_message_collector.js`
- `backend/email_agent/analyzer.py`
- `backend/email_agent/model_context_selection.py`
- `backend/email_agent/prompt_context.py`
- focused browser, analyzer, context-selection, and prompt tests

Steps:

1. Add RED fixtures for verified sibling history, stale replacement, current-only
   requests, resolved current outcomes, exact-current deduplication, and terse replies.
2. Keep sibling discovery bounded to the verified message region and complete legacy
   headers.
3. Append the current message exactly once before deterministic timeline creation.
4. Retain bounded adjacent verified history and make source roles/order explicit.
5. Verify the same sources reach OpenAI and DeepSeek text routes.

## Task 3: Make attachment semantics observable and mandatory

Files:

- `backend/email_agent/attachment_text.py`
- `backend/email_agent/attachment_docx.py`
- `backend/email_agent/attachment_model_context.py`
- `backend/email_agent/prompt_context.py`
- `backend/email_agent/analysis_model_routes.py`
- `backend/email_agent/model_result_safety.py`
- focused attachment parser, prompt, route, and merge tests

Steps:

1. Add RED tests for parser truncation metadata, a late structured fact, and missing
   attachment augmentation.
2. Increase bounded parsing/model budgets only as needed by the synthetic evidence,
   while retaining byte, count, time, page, row, sheet, and paragraph limits.
3. Carry fixed truncation and parser limitations into provider source JSON.
4. Require exactly one valid augmentation for each sent parsed attachment.
5. Fail closed to deterministic analysis on missing semantic coverage.

## Task 4: Preserve deterministic reconciliation safeguards

Files:

- `backend/email_agent/rule_context.py`
- a focused cross-source reconciliation helper if required
- `backend/email_agent/rule_decision.py`
- `backend/email_agent/model_result_safety.py`
- focused rule and model-merge tests

Steps:

1. Add RED tests for parsed-without-facts semantic review and safely comparable
   cross-source differences.
2. Add fixed, non-sensitive must-check and missing-information items without guessing
   which source is correct.
3. Preserve those backend items after model merge.
4. Keep exact facts locally authoritative and retain the public schema.

## Task 5: Fix the future real-mail gold-standard contract

Files:

- `docs/operations/private_deepseek_evaluation.md`
- `docs/operations/authorized_mailbox_ingest_task_brief.md`
- `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`
- private-evaluation architecture and tooling constraints
- documentation contract tests

Steps:

1. Specify a versioned V2 ordered-thread and reviewed-attachment binding.
2. Specify an encrypted structured human reference with independent business and
   privacy approval.
3. Require candidate/reference separation, blinded human judging, and aggregate-only
   reporting.
4. Explicitly prohibit raw ChatGPT transcripts, automatic training/upload, model
   self-grading, and automatic production switching.
5. Do not implement or open a real V2 dataset in this Task 9 repair.

## Task 6: Review and verification

1. Request independent spec-compliance and code-quality reviews.
2. Resolve all Critical and Important findings and rerun focused tests.
3. Run the full pinned Python suite, all extension JavaScript syntax checks,
   architecture/static/mechanical tests, leakage scan, maintenance scan,
   deterministic status generation, and `git diff --check`.
4. Leave the branch unmerged. A new live representative-message test requires fresh
   explicit authorization and content-free diagnostics only.

## Completion rule

Task 9 is complete only when synthetic vertical tests prove that current/history and
attachment evidence materially constrain the final result, all safeguards survive
model merge, documentation no longer equates `parsed` with correctness, and the full
offline release gate passes. A future private real-mail evaluation remains separately
authorized and encrypted.

## Completion record

- The offline semantic repair is complete: trusted current mail, verified adjacent
  history, provider source roles, attachment coverage, and deterministic reconciliation
  are protected by synthetic vertical tests.
- Deterministic attachment facts survive model merge byte-for-byte, and truncated
  attachment evidence retains only conservative complete English/CJK sentences;
  abbreviation, initialism, decimal, and partial-tail counterexamples fail closed.
- Independent thread, Tencent DOM/API, attachment, deterministic-rule, and private
  human-reference reviews have no remaining Critical or Important findings.
- The future real-mail V2 method is documentation-only. It uses an encrypted,
  independently authored and dual-reviewed human reference with blinded judging; it
  does not implement automatic training, upload, self-grading, or model switching.
- No live browser, mailbox, provider, API, SQLite, attachment, navigation, scan, send,
  delete, move, or archive operation was performed by this repair.
