---
last_update: 2026-07-22
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Issue 11 Governed Sales Corpus Task Brief

## 1. Task name

```text
bootstrap one governed 24-month sales corpus
```

## 2. Task type

```text
security | feature | data_schema | docs
```

## 3. Current status

```text
completed
```

The implementation authority is GitHub Issue #11 and its parent PRD #9. The
ticket is ready for an autonomous agent. This task authorizes offline code and
synthetic verification only; it does not authorize a live mailbox, real vault,
host-security probe, provider call, or real private sales-policy file.

## 4. Goal

Complete the existing administrator lifecycle so one authorized account can be
inventoried and, only after exact fingerprint confirmation, imported as a
governed rolling 24-calendar-month sales corpus. Only actual external-customer
requests paired with later replies from privately allowlisted salespeople become
learning evidence. Duplicate messages, quotations, and attachments must not
inflate evidence or aggregate reports.

## 5. Non-goals

- Do not add a command; the eight core commands and three network commands stay
  unchanged.
- Do not implement incremental sync (#17) or current-click candidate work (#18).
- Do not change the browser, normal backend, public HTTP API, public SQLite, AI
  output JSON, provider routing, or startup knowledge loading.
- Do not add polling, scheduling, arbitrary mailbox access, SMTP, mailbox
  mutation, model calls, or live credentials.
- Do not infer salesperson aliases, fuzzy-match quotations, or treat parsing as
  semantic correctness.
- Do not migrate an older vault implicitly. A missing Issue #11 corpus index
  fails closed and requires a newly initialized vault/fresh inventory.

## 6. Background and authority

Relevant sources:

- GitHub Issue #11, `Bootstrap one governed 24-month sales corpus`
- GitHub Issue #9, parent product requirements
- `AGENTS.md`
- `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`
- `docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md`
- `docs/operations/authorized_mailbox_ingest_task_brief.md`
- `docs/security/email_data_handling.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`

The public test seam is the administrator lifecycle entrypoint. Tests drive
`scripts.manage_mailbox_vault.run_cli` or the corresponding service operation
with synthetic mailbox, clock, keys, stores, and output sinks. Pure policy and
index contracts are secondary public seams. Private helper implementation is not
the test target.

## 7. Expected scope

Expected additions or changes:

```text
backend/mailbox_ingest/sales_policy_file.py
backend/mailbox_ingest/sales_message_policy.py
backend/mailbox_ingest/sales_message_primitives.py
backend/mailbox_ingest/sales_corpus_index.py
backend/mailbox_ingest/_sales_corpus_*.py
backend/mailbox_ingest/governed_scan.py
backend/mailbox_ingest/governed_scan_state.py
backend/mailbox_ingest/scan_record.py
backend/mailbox_ingest/inventory.py
backend/mailbox_ingest/inventory_codec.py
backend/mailbox_ingest/attachment_scan.py
backend/mailbox_ingest/attachment_operation.py
backend/mailbox_ingest/service_models.py
backend/mailbox_ingest/service.py
backend/mailbox_ingest/service_operations.py
backend/mailbox_ingest/vault_access.py
backend/mailbox_ingest/vault.py
backend/mailbox_ingest/vault_index.py
backend/mailbox_ingest/vault_record_writer.py
backend/mailbox_ingest/_vault_lifecycle.py
scripts/manage_mailbox_vault.py
tests/test_mailbox_sales_policy_file.py
tests/test_mailbox_sales_corpus*.py
tests/test_mailbox_governed_scan.py
tests/test_mailbox_inventory.py
tests/test_mailbox_scan.py
tests/test_mailbox_attachments.py
tests/test_mailbox_vault*.py
tests/test_manage_mailbox_vault.py
tests/test_mailbox_transport_constraints.py
tests/test_architecture_constraints.py
docs/ and generated project status files named by the final diff
```

New Python modules remain at or below 300 lines and functions remain at or below
50 lines. No dependency is added.

## 8. Technical design

1. Preserve the content-free inventory and exact confirmation gate. The CLI
   inventory result exposes the already-safe `InventoryV1` projection: fixed
   endpoint token, authorized window, per-folder opaque ID/count/size/
   UIDVALIDITY, totals, and fingerprint. Private folder role is retained only in
   the encrypted inventory control codec and fingerprint.
2. Require `scan --sales-policy <absolute-path>` without adding a command. The
   bounded strict JSON file contains only `schema_version`, one company domain,
   and an exact salesperson-address allowlist. Values use a redacted value
   object, never enter output/log/repr/status/source fixtures, and are bound to
   the corpus index only by a vault-keyed HMAC. Automated tests use synthetic
   `.test` values and an injected loader.
3. Initialize a separate external-vault `corpus-index.sqlite3`. It contains only
   random vault record IDs, vault-keyed HMAC values, enums, bounded counts, and
   UTC integer timestamps. Every security-relevant row and edge is authenticated
   including corpus metadata, and verified by both reads and `validate()`. It
   stores no raw address, domain,
   subject, body, filename, Message-ID, folder, UID, locator, or plaintext. Its
   HMAC key uses a distinct HKDF purpose and is wiped on close.
4. Parse bounded headers and decoded current-message text locally. Direction is
   based on the private policy plus private folder role. A customer request has
   an external sender and company recipient; a salesperson reply has an exact
   allowlisted sender, external recipient, a later trusted inventory
   `INTERNALDATE`, and an exact validated `In-Reply-To` or `References` link to
   an included request. Message-ID local-part case is exact and only its domain
   is normalized. Subject-only pairing is prohibited.
5. Reject ambiguous headers and exclude automated/list/bulk/notification
   traffic, pure forwards with no new content, non-sales internal
   mail, signature/disclaimer-only content, and duplicate quotation evidence.
   Signatures, bounded Outlook or Chinese quoted-header history, and disclaimers
   are removed from the learning projection, while authorized raw bytes remain
   only in encrypted vault records.
6. Use vault-keyed content deduplication with random opaque record and path
   identifiers. A durable authenticated write intent reserves those identifiers
   before ciphertext creation; a retry after a ciphertext/index interruption
   resumes the same intent rather than creating an orphan. Fresh vault schema
   v3 is required and older schemas fail closed without implicit migration.
   Every active-record and intent metadata row has a distinct-purpose MAC, and
   exact schema validation rejects weakened constraints or unexpected objects.
   Raw records are written through `MailboxVault`; only authenticated paired
   edges become downstream learning evidence. Earlier duplicate message copies
   can only shorten raw-record expiry. One cross-process mutation lock spans
   each vault-plus-corpus upsert, attachment binding, and purge sequence.
7. Preserve the reviewed attachment-manifest gate and existing byte limits.
   Unsupported candidates are counted without byte retrieval. A fetched
   supported attachment is stored in a source-independent encrypted blob that
   contains only fixed framing and exact raw bytes, then linked to opaque
   source/candidate IDs in the private corpus index. Parsed projections are not
   persisted in the blob. Exact byte
   duplicates reuse one blob and an explicitly authorized later binding may
   extend its expiry. Outcomes separately report fetched, parsed, new-blob,
   duplicate-blob, and semantic-unreviewed counts.
8. Successful output contains only fixed codes and allowlisted integer aggregate
   counts. Failure contains only fixed codes. No raw value, locator, path,
   filename, MIME-derived text, exception detail, or partial record ID is public.

## 9. Data and interface changes

### External vault

```text
Add a fresh, metadata-only corpus-index.sqlite3 with its own schema and HMAC key.
Add source-independent encrypted attachment blob records and opaque bindings.
Keep raw message bytes in the existing AES-256-GCM record store.
```

### Administrator CLI

```text
inventory: same command, richer safe aggregate projection.
scan: same command, additionally requires --sales-policy absolute path.
attachments: same command, richer aggregate outcome counts.
No command-set or transport change.
```

### Public API, public SQLite, browser, AI JSON, prompts

```text
No change.
```

## 10. Security and privacy checklist

- [x] No real mailbox or real business data is used during implementation.
- [x] No send, delete, archive, flag, move, copy, or other mailbox mutation is added.
- [x] Provider and fallback defaults remain disabled; no provider is called.
- [x] Private allowlist/domain values do not enter tracked source, fixtures,
  logs, repr, status, or public output.
- [x] Mail, attachments, and filenames remain untrusted input.
- [x] Raw bytes persist only through the external encrypted-vault contract.
- [x] Public output is fixed-code and aggregate-only.
- [x] Tests use synthetic values and injected host/network boundaries.

## 11. Prompt-injection protection

No prompt or provider route is added. Header, body, and attachment content is
data only. It cannot choose commands, policy, storage paths, transport methods,
or output fields.

## 12. Acceptance criteria

1. Inventory exposes the exact safe window and per-folder aggregates and requires
   the exact fingerprint before any mailbox content fetch.
2. The fixed endpoint, one authorized account, rolling 24 calendar months, TLS,
   read-only IMAP allowlist, and `BODY.PEEK` limits remain executable guards.
3. A synthetic request and later allowlisted reply pair across folder order;
   spoofed, unlinked, earlier, or non-allowlisted replies do not pair.
4. Automated mail, notifications, bulk marketing, pure forwards, signatures,
   disclaimers, quoted history, and duplicate quotations do not become evidence.
5. Cross-folder duplicate messages and exact duplicate attachment bytes do not
   create additional evidence or aggregate success counts.
6. Raw content is written only through encrypted vault contracts; index and
   public output remain content-free.
7. Attachment output separates supported/unsupported, acquisition, parsing,
   deduplication, and semantic-unreviewed state.
8. Focused tests, JavaScript syntax checks, full unit discovery, maintenance
   scan, project-status regeneration, leakage scan, and final code review pass.

## 13. TDD plan

- RED/GREEN 1: safe inventory CLI projection.
- RED/GREEN 2: strict redacted private policy loader.
- RED/GREEN 3: metadata-only corpus index and exact pairing/dedup contract.
- RED/GREEN 4: pure message direction, exclusion, cleaning, and canonicalization.
- RED/GREEN 5: scan lifecycle integration, checkpoint/retry, pair and report counts.
- RED/GREEN 6: attachment blob dedup and parsed-versus-semantic reporting.
- RED/GREEN 7: CLI fixed shapes and architecture/transport/privacy guards.

## 14. Rollback

1. Do not run the administrator CLI; leave all providers disabled.
2. Revert this task's single commit. No public schema or runtime migration is
   required.
3. An Issue #11 vault is not silently downgraded. If rollback is necessary,
   preserve it offline and create a separately authorized fresh vault only after
   a later reviewed plan.
4. Rollback never mutates the source mailbox.

## 15. Human confirmation

No further design choice is required for offline implementation because the
ticket and parent PRD fix the behavioral seam. Live execution still requires the
operator's existing separate authorization, app password, exact fingerprint,
private policy file, reviewed attachment manifest, and external-vault controls.

## 16. Bounded handoff checklist

- [x] No incremental sync command is added; #17 remains future work.
- [x] No current-click evidence inbox or orchestration is added; #18 remains
  future work.
- [x] Normal runtime receives no mailbox, corpus-index, raw-vault, reader,
  search, path, key, repository, or authority capability.
- [x] Public HTTP, public SQLite, frontend, provider-disabled fallback, and
  startup-only knowledge loading remain unchanged.

## 17. Execution record

```text
Actual files: AGENTS.md; governed sales-policy/message/corpus/vault modules under
  backend/mailbox_ingest/; scripts/manage_mailbox_vault.py and
  scripts/generate_project_status.py; ADR/operations/status documentation; and
  the synthetic mailbox, corpus, attachment, vault, CLI, architecture, leakage,
  transport, status, and documentation-contract tests shown by the task commit.
Focused tests: 147 core tests passed; 147 architecture/mechanical/static/
  transport/leakage/status/documentation tests passed.
Full verification: pinned .venv Python 3.12.13 ran 1,629 tests successfully
  (1 existing skip); maintenance reported no findings; 7 JavaScript syntax
  checks, compileall, and git diff --check passed.
Literal required command: system Python discovered 1,360 tests and stopped with
  36 import errors because that interpreter lacks locked openai/bs4 dependencies;
  no dependency was installed into it. The authoritative pinned .venv passed.
Review: final independent Standards and Specification re-reviews reported no
  findings after all initial findings were reproduced and fixed.
Commit: feat: bootstrap governed sales corpus (current branch; not pushed).
```
