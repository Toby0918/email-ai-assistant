---
last_update: 2026-07-21
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Current Email Grounding and Attachment Repair Task Brief

## 1. Task name

```text
repair labeled MOQ grounding and current-message attachment acquisition
```

## 2. Task type

```text
fix | security | prompt | api_contract
```

## 3. Current state

```text
approved
```

## 4. Goal

Correct two defects found during the separately authorized current-message smoke. First, a locally visible, explicitly labeled MOQ alternative must become an authoritative deterministic fact and must not be described as still unknown. Second, the extension must recognize the verified legacy Tencent attachment control, fetch it in memory under the existing limits, and offer an explicit user-selected local-file fallback when automatic acquisition is unavailable.

## 5. Non-goals

- No mailbox navigation, search, enumeration, polling, or background scan.
- No automatic email action, including send, reply, delete, move, or archive.
- No system Downloads automation and no new `downloads`, filesystem, cookie, or storage permission.
- No URL-query, cookie, token, local path, original binary, or Base64 persistence in HTTP responses, SQLite, logs, tests, docs, or Git.
- No relaxation of exact local authority for identifiers, dates, amounts, quantities, or tracking values.
- No provider call during implementation or automated verification.
- No use of the real values observed in the current message in repository fixtures; all tests use recreated synthetic values and `example.test` identities.

## 6. Background and evidence

The user-reported analysis treated a labeled MOQ alternative as unresolved even though the visible thread had already answered it. Read-only code tracing showed that local quantity extraction requires units, request topics omit MOQ, outcome detection does not treat a final labeled MOQ statement as an answer, and model grounding has no signature for slash-separated MOQ alternatives.

The user separately authorized one content-free attachment-control probe on the already opened message. The probe returned only structural booleans, counts, and endpoint classes. It found exactly one visible same-origin `/cgi-bin/download` anchor with a non-empty query and `target`, outside `#mailContentContainer.qmbox` but in the same verified parent region as `.readmailinfo`. The anchor had no `download` attribute. Current discovery and collector code both require that attribute, which precisely explains the `unavailable` attachment result.

A later separately authorized content-free diagnostic isolated the remaining
automatic-acquisition failure before fetch. The verified body root is nested
through one additional wrapper, the exact download endpoint is rendered below
the current viewport, and the anchor itself provides no supported type
evidence. The operator approved the narrow two-wrapper/off-viewport repair and
post-fetch response-header plus signature validation. This approval does not
authorize document-body scanning, arbitrary ancestor text inference, scrolling,
clicking, navigation, persistence, provider calls, or mailbox operations.

Related documents:

- `AGENTS.md`
- `docs/decisions/0007-multimodal-current-email-analysis.md`
- `docs/security/email_data_handling.md`
- `docs/api/backend_api_contract.md`
- `docs/operations/multimodal_current_email_analysis_task_brief.md`
- `docs/operations/task9_semantic_accuracy_repair_task_brief.md`

## 7. Scope

Expected changes:

- `backend/email_agent/quantity_facts.py`
- `backend/email_agent/email_facts.py`
- `backend/email_agent/thread_requests.py`
- `backend/email_agent/thread_outcomes.py`
- `backend/email_agent/model_grounding.py`
- `backend/email_agent/model_known_fact_consistency.py`
- `backend/email_agent/model_result_safety.py`
- `frontend/browser_extension/content/exmail_adapter.js`
- `frontend/browser_extension/content/current_message_collector.js`
- `frontend/browser_extension/shared/manual_attachment_files.js`
- `frontend/browser_extension/popup.html`
- `frontend/browser_extension/popup.js`
- `frontend/browser_extension/popup.css`
- focused tests and active contracts listed by the two implementation plans

## 8. Technical approach

1. Add one strict shared parser for explicitly labeled MOQ values. Bare slash pairs, dates, ratios, phone-like values, and pending/non-final statements stay rejected.
2. Reuse that parser in deterministic facts, timeline topics/outcomes, grounding signatures, and a narrow known-fact contradiction gate.
3. Keep the existing exact Tencent origin, HTTPS, path, query, visible-context, ownership, fetch, redirect, byte, count, and deadline gates. Accept only the existing direct-parent resource container or one legacy intermediate wrapper whose outer container remains a direct child of the verified document body. Never use `document.body` or an arbitrary ancestor as the resource scope.
4. Keep automatic bytes in browser memory and reuse the existing backend request-local temporary file plus API `finally` cleanup.
5. Add an optional, default-collapsed file picker. It reads selected files only on Analyze, merges them into the unchanged `attachment_files` payload, clears references on every exit, and never writes to browser storage or the system Downloads directory.
6. Treat only `attachment_insights[].status == "parsed"` as proof that attachment content was analyzed.
7. For verified attachment anchors only, allow rendered non-zero controls below
   the viewport without scrolling or clicking. Keep viewport intersection for
   inline body images.
8. When an exact legacy download anchor lacks supported type metadata, defer
   type resolution until its one bounded same-origin read. Require compatible
   response Content-Type or strict response Content-Disposition evidence plus
   an allowlisted signature. Never infer type from URL query or arbitrary
   ancestor text.

### Attachment acquisition release contract

- Automatic legacy control acquisition is current-message-only, begins only after Analyze, fetches at most once with credentials and redirect failure, and holds bytes in browser memory only.
- Manual picker selection does not read bytes. Selected supported files are read only inside Analyze, after the initial message fingerprint, and all references are cleared on every exit.
- Both paths share 5 files, 10 MiB per file, and 25 MiB total. They add no browser permission, storage, filesystem, download, URL, query, token, or path surface.
- Backend request-local files are removed from request `finally`. The 24-hour mtime cleanup is crash recovery only, not normal retention and not scheduled.
- Only `attachment_insights[].status == "parsed"` proves content parsing; metadata and counts do not.
- The real current-message attachment smoke remains separately gated and requires fresh explicit authorization after offline Tasks 1-4 are review-clean.

## 8a. Labeled MOQ grounding contract

- Finite accepted labels: `MOQ`, `minimum order qty`, `minimum order quantity`, `最低起订量`, and `最低订购量`.
- The parser accepts one-to-four alternatives only, with one closed canonical unit set; the local parser/local extraction rejects an unknown-unit.
- Recognition retains parser-owned source spans. The complete result is an indivisible alternative set: no consumer may split or omit one member.
- Negative cases: bare slash pairs, dates, ratios, phone-like values, contact/signature clauses, compact quotation rows, and pending/non-final claims are rejected.
- Local exact-fact authority: complete labeled MOQ alternatives are extracted and grounded locally; a provider cannot author or override these exact values.
- A final MOQ answer closes the quantity request only; sample, attachment, lead-time, quotation, and other requests remain independently resolved.
- Invalid, unitless, unknown-unit, non-final, incomplete, changed, or invented-unit provider MOQ claims fail closed. A known MOQ contradiction falls back only for the conflicting public field; unrelated grounded fields remain eligible.

### Release markers

- Accepted label: `MOQ`
- Accepted label: `minimum order qty`
- Accepted label: `minimum order quantity`
- Accepted label: `最低起订量`
- Accepted label: `最低订购量`
- Local unknown-unit rejection.
- Conflicting public field fallback.
- Unrelated grounded fields remain eligible.

## 9. Data and interface changes

### Database

```text
None.
```

### API

```text
No new public fields. The existing attachment_files and resource_limitations shapes are reused.
```

### AI output JSON

```text
None.
```

### Prompt

```text
No provider contract expansion. Documentation may clarify that locally extracted exact quantities remain authoritative.
```

## 10. Security and privacy checklist

- [x] The only real-page operation was the explicitly authorized content-free structural probe.
- [x] No real subject, body, address, filename, URL query, or attachment byte entered tool output or the repository.
- [x] Providers remain disabled by default.
- [x] The extension remains click-only and current-message-only.
- [x] Automatic fetch remains credentialed, same-origin, bounded, and redirect-failing.
- [x] The file picker requires explicit operator selection and does not prove mailbox origin; the UI states that limitation.
- [x] No new browser persistence or download permission is introduced.
- [x] Backend temporary files are deleted in request `finally`; the 24-hour cleanup is crash-recovery only, not scheduled retention.
- [x] Tests use synthetic values and identities only.

## 11. Prompt-injection protection

- Email text, attachment labels, selected filenames, and file contents remain untrusted data.
- No DOM text, attachment text, or model output can authorize commands, tools, mailbox actions, or commitments.
- Exact facts are constructed and validated locally; model-authored exact facts remain non-authoritative.
- The manual picker never accepts a path, URL, query, token, or restoration mapping as an API field.

## 12. Acceptance criteria

1. A synthetic final labeled MOQ alternative becomes one deterministic key fact and closes only the quantity request; an unrelated sample item can remain open.
2. Bare slash values, dates, ratios, phone-like values, pending MOQ, and mismatched model MOQ are rejected.
3. A synthetic legacy Tencent anchor matching the content-free probe structure is collected exactly once without a `download` attribute.
4. The same endpoint without `target`, a `viewfile` link without `download`, an in-body link, signature/profile link, external origin, empty query, redirect, stale context, or unsupported type remains rejected.
5. Automatic acquisition preserves 20 candidates, 5 files, 10 MiB per file, 25 MiB total, and 20 seconds.
6. The manual picker performs zero reads on load/change, reads only on Analyze, shares the aggregate limits, and is cleared on success, error, cancellation, or stale context.
7. Manifest permissions remain exactly `activeTab` and `sidePanel`; no browser storage or downloads API is used.
8. A vertical synthetic attachment test proves `status == "parsed"`; array length alone is not accepted.
9. Full tests, JS syntax, architecture/static/mechanical guards, leakage scan, project-status generation, maintenance scan, and `git diff --check` pass.
10. A synthetic two-wrapper, off-viewport, untyped legacy control is read once
    and accepted only when response headers and signature agree. Mismatches,
    HTML, hidden controls, zero-layout controls, deeper wrappers, authored-body
    links, and off-viewport inline images remain fail closed.

## 13. Test plan

- Validate the deterministic grounding, source-evidence binding, and exact-fact
  acceptance criteria in this brief and ADR 0007.
- Validate the current-message attachment acquisition and fail-closed visibility
  boundaries in this brief, the backend API contract, and the email-data policy.
- Implementation and verification evidence is preserved by commit `dc9f5e8`.
- Run all focused commands with the pinned Python 3.12.13 runtime and correct dependency paths.
- Run no real provider, mailbox, attachment download, or live browser test without a separate explicit authorization.

## 14. Rollback

Revert the MOQ parser integration to restore prior deterministic behavior. Revert the legacy positive signal to return to safe metadata-only/unavailable attachment handling. Remove the optional picker module and markup to restore automatic-only acquisition. No database migration or persistent file cleanup is required.

## 15. Human confirmation

The operator approved Option A plus Option C and the original content-free
probe. On 2026-07-18 the operator additionally approved implementation of the
bounded two-wrapper/off-viewport automatic-acquisition repair and post-fetch
header/signature type validation. This implementation approval does not itself
authorize another real attachment fetch, provider call, navigation, mailbox
scan, or send action.

## 16. Pre-execution checks

- [x] Read `AGENTS.md` and active project status.
- [x] Read tooling, architecture, linter, task-brief, and documentation rules.
- [x] Work only in `.worktrees/multimodal-plan-c`.
- [x] Preserve the root checkout and unrelated deployment-notes modification.
- [x] Keep existing review-package files unstaged.
