---
last_update: 2026-07-23
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Authorized Mailbox Ingest Task Brief

## 1. Task Name

```text
build a separately authorized private mailbox-ingest and knowledge workflow
```

## 2. Task Type

```text
security | feature | docs
```

## 3. Current Status

```text
approved_governance_boundary
```

The user approved the written plan on 2026-07-14 and stated that company
written authorization exists. This approval permits offline implementation and
synthetic verification. It does not itself permit Codex, automated tests, the
browser extension, the normal backend, or a scheduled job to connect to a
mailbox or call DeepSeek.

## 4. Goal

Add a separately authorized, operator-run workflow that can import a rolling
24-month analytical snapshot from one authorized account through a fixed
read-only Tencent Exmail IMAP route, protect the snapshot in an external
encrypted vault, derive reviewed non-identifying company knowledge, and use
only locally deidentified current-message context plus approved knowledge cards
for a bounded DeepSeek evaluation.

The normal product remains an assistant for the currently visible message. The
browser extension remains click-only and cannot scan a mailbox.

## 5. Non-Goals

- No browser extension, local debug page, normal backend, cleanup agent,
  scheduled job, or background worker may enumerate or import a mailbox.
- No live mailbox connection, real mailbox data, vault, recovery material, or
  DeepSeek call is part of automated implementation or testing.
- No SMTP, send, reply, forward, flag mutation, move, copy, append, delete,
  expunge, folder mutation, or subscription mutation is permitted.
- The workflow is not a legal archive, backup product, e-discovery system,
  batch mailbox report, or automatic training pipeline.
- Imported content does not enter the existing public SQLite database, Git,
  docs, logs, fixtures, status reports, or maintenance reports.
- Raw or identifying imported content is never supplied to Codex or DeepSeek.
- No public analysis API, public response field, extension render field, or
  mandatory human-review behavior changes under this authorization.

## 6. Authorization And Inventory Gates

Every operator-run inventory or scan must fail closed unless all gates pass:

1. The operator supplies a non-sensitive authorization identifier; no signed
   authorization document or personal data is copied into the repository.
2. The command names exactly one authorized account and the fixed endpoint
   `imap.exmail.qq.com:993` with TLS certificate verification.
3. The date scope is a rolling 24-month window. There is no unrestricted date
   range, second account, discovery mode, or arbitrary host option.
4. `inventory` runs before content retrieval and returns only aggregate counts,
   aggregate size, opaque folder identifiers, UIDVALIDITY, the date window, and
   a deterministic content-free inventory fingerprint.
5. `scan` requires the operator to repeat that exact fingerprint through
   `--confirm-inventory-fingerprint`. A changed fingerprint or UIDVALIDITY
   stops the run before further content retrieval.
6. The mailbox app password is requested only with interactive `getpass` after
   local policy checks. There is no password flag, environment variable,
   `.env` source, persisted value, log value, or diagnostic representation.
7. Attachment collection requires a separately reviewed local manifest and is
   capped at 50 representative files, 10 MiB per file, and 25 MiB per
   conversation.
8. A bootstrap `scan` also requires an absolute, bounded private sales-policy
   file on approved storage. It names one exact company domain and an exact
   salesperson-address allowlist. The values are never emitted or persisted;
   only a vault-keyed policy fingerprint is bound to the corpus index.

The governed corpus contains only an external customer request paired through
strict `Message-ID` references with a later reply from an allowlisted
salesperson. Message-ID local-part case remains exact and only its domain is
normalized; subject-only matching is prohibited. Automated/list/bulk mail,
notifications, pure forwards, non-sales internal mail, signatures,
disclaimers, bounded Outlook or Chinese quoted-header history, cross-folder
message copies, and exact duplicate quotations do not inflate learning evidence.
Raw authorized records remain only
in the encrypted vault; a separate external metadata-only corpus index stores
opaque record IDs, keyed lookup values, enums, integer timestamps, and aggregate
state. It stores no addresses, domains, subject, body, filename, Message-ID,
mailbox, UID, path, or locator.

The corpus index receives a purpose-separated key derived independently from
the vault master key with HKDF. Every metadata row and relationship edge has a
table-domain-separated HMAC over a canonical typed encoding. Safety-relevant
reads authenticate the selected row or edge before use, and `validate`
authenticates the complete index. Missing, malformed, substituted, or tampered
metadata fails closed.

Reviewed attachments may be acquired only for a source in a governed pair.
The attachment lifecycle distinguishes supported versus unsupported metadata,
byte acquisition, parse success, exact blob reuse, and semantic-unreviewed
state. An encrypted attachment record contains fixed attachment framing and the
exact acquired raw bytes only; its parsed projection is not written into that
blob. Parse and semantic-review outcomes remain authenticated metadata, and
parsing alone is never reported as semantic correctness.

The administrator-only CLI is `scripts/manage_mailbox_vault.py`. Its approved
commands are `init`, `inventory`, `scan`, `attachments`, `verify`,
`purge-expired`, `revoke`, and `rewrap-recovery`. There is no scheduled job,
automatic trigger, browser command, or normal-runtime hook.

ADR 0008 authorizes future issue #17 to add administrator-triggered incremental
synchronization within this same isolation boundary. Issue #10 does not add a
`sync` command. Each future sync must be a new manual run, use only the fixed
`imap.exmail.qq.com:993` endpoint and existing read-only operations, and stop
before content access unless the operator repeats the exact current inventory
fingerprint. It has no browser, normal API, scheduler, cleanup, polling, or
background trigger. The existing eight core commands and `NETWORK_COMMANDS`
remain unchanged until #17 supplies its own tests and implementation.

Operators invoke it only as `python -B -m scripts.manage_mailbox_vault <command>`;
direct file execution is not an approved runbook form. Inventory review is a
mandatory stop before scan. Live mailbox scan, private evaluation, and production
provider activation use separate operator confirmations; no credentials are
supplied to Codex, and there is no automatic mailbox scan from a browser, normal
runtime, or automation path.

These remain the eight core vault commands. `stage-knowledge` is a later Task 4
handoff command implemented only in that administrator-only CLI. It accepts
only a reviewed manifest of approved random record IDs, decrypts one record at
a time, runs the local private-knowledge deidentifier and residual scanner in
memory, releases raw plaintext and the ephemeral mapping before the next
record, and writes only an encrypted deidentified candidate batch under a
separate knowledge namespace. Its result and all output, logs, receipts, and
errors contain only candidate IDs, counts, and fixed codes,
never raw record IDs, text, mapping, paths, locators, or identifying values.
`scripts/manage_private_knowledge.py`, Codex, DeepSeek, normal runtime, and
automated tests never import or read the raw vault.

Task 4 creates `tests/test_manage_mailbox_vault_stage_knowledge.py` and tests the
exact synthetic injected interface:

```python
stage_knowledge(
    selection,
    *,
    read_one_record,
    deidentify,
    scan_residuals,
    write_encrypted_candidate_batch,
) -> StageKnowledgeResult
```

The separately reviewed `stage-evaluation` handoff is also local-only in
`scripts/manage_mailbox_vault.py` and is not one of the eight core commands or a
`NETWORK_COMMANDS` member. Its strict `StageEvaluationSelectionV1` binds exactly
200 unique raw record IDs to unique UUIDv4 case IDs, the authorized vault,
authorization `scope_fingerprint`, reviewed `inventory_fingerprint`, rolling
window, current-revision business/privacy approvals by distinct
actors, optional Pro-pair approval, production stratum, and expected category,
mandatory risks, and required actions. The manifest contains no subject, body,
address, filename, source locator, or other message content and expires no later
than 24 hours after the latest required review.

The command decrypts one record at a time, applies structured local
deidentification and residual scanning in memory, builds one validated evaluation
case, and releases raw plaintext plus restoration mapping before the next record.
Its evaluation-only source validates the record inventory fingerprint before
plaintext release, performs no evidence accumulation, and retains no counterparty
domain, message/thread ID, or other raw-derived identifier between records.
It uses a hidden interactive base64 32-byte staging/evaluation key and no mailbox
app password, key flag, environment, `.env`, or key file. Only a bounded,
atomically replaced, project-external `.pkevalstage` is written with AES-256-GCM,
a random nonce, and distinct magic, purpose, and namespace from final `.pkeval`,
raw vault, and private knowledge. Post-replacement path validation excludes only
the exact target while sibling and descendant private stores still fail closed.
Success is exactly
`evaluation_stage_complete` with 200 accepted and zero rejected; all failures,
repr, logs, and output contain only fixed codes/counts and never case/record IDs,
paths, text, matches, exception detail, or a partial stage file. Parser and local
validation failure is exactly `argument_invalid`. The evaluator
never imports or reads the raw vault.

### Future real-mail V2 evaluation boundary

Task 9 records a documentation-only V2 contract; it does not implement V2 and it
does not open a real V2 dataset. V1 compatibility remains binding: the existing V1
staging/dataset flow stays valid, and a future V2 flow may neither mutate V1 nor
silently promote a V1 case.

A future `PrivateEvaluationCaseV2` must preserve ordered deidentified thread
segments oldest-to-newest and reviewed attachment bindings, rather than flattening
history or treating `parsed` as semantic proof. Its encrypted
`StructuredHumanReferenceV2` is completed before candidate generation, uses opaque
evidence bindings, and requires independent business and privacy_security approvals
by distinct actors. Strict candidate/reference separation prevents a candidate,
provider, or reference author from rewriting both sides of the comparison.
Candidate generation receives only the approved deidentified evidence and cannot access or decrypt the reference, approvals, rubric, or prior verdict.
The blinded human judge sees the complete approved deidentified evidence and an
unlabeled candidate, but not provider and model identity or routing metadata.
Only aggregate-only reporting may persist.

The prohibited artifacts include raw ChatGPT transcripts. The prohibited
operations include automatic training, automatic upload of cases or references
as a training corpus, model self-grading, and any automatic production model switch.
A manually obtained second opinion can inform a newly authored and
independently approved structured reference, but the transcript itself cannot enter
the vault handoff, dataset, repository, report, or training material. V2
implementation, live dataset creation, provider calls, and any training use require
new separate written authorization.

## 7. Expected Scope

The approved implementation plan may later add these isolated packages and
operator CLIs:

```text
backend/mailbox_ingest/
backend/private_knowledge/
backend/private_evaluation/
scripts/manage_mailbox_vault.py
scripts/manage_private_knowledge.py
scripts/evaluate_private_deepseek.py
```

Only `scripts/manage_mailbox_vault.py` may import `backend.mailbox_ingest`.
`frontend/`, `backend.email_agent`, the loopback server, cleanup automation,
and scheduled workflows may not import or invoke it.

## 8. Transport Policy

The IMAP wrapper has no arbitrary command passthrough. It exposes only folder
listing, read-only `EXAMINE`, `UID SEARCH`, and bounded `UID FETCH` operations
using `BODY.PEEK`. It must never issue `BODY[]` without `PEEK`.
Until Task 3 adds runtime validator tests, every target is a finite single-UID
decimal literal. Task 3 may add only the direct bare local, non-imported,
non-reassigned expression `validate_single_uid_fetch_target(uid)` in the same
change as its runtime tests; wildcard, range, sequence, dynamic, and qualified
targets remain forbidden.

Mechanically forbidden operations are `STORE`, `APPEND`, `COPY`, `MOVE`,
`EXPUNGE`, `CREATE`, `DELETE`, `RENAME`, `SUBSCRIBE`, `UNSUBSCRIBE`, SMTP, and
any command that can change flags or mailbox state. A connection that cannot
prove the required read-only state fails closed.

## 9. External Vault And Key Boundary

- The raw vault is outside the project, OneDrive, and system temporary
  directories on a proven NTFS BitLocker To Go volume.
- "Outside the project" means outside the complete Project Container protected
  root, including `main`, every approved sibling zone, the container itself, and
  all descendants. Vault, current/new recovery, and the strict sales-policy file
  derive this root internally from freshly revalidated placement; no CLI,
  environment, config, HTTP, browser, or normal-runtime input can narrow it.
- Every raw record is independently protected with AES-256-GCM and a random
  nonce. The random record ID is authenticated as associated data.
- Fresh initialization creates only the exact schema-v3 index. Record IDs and
  encrypted relative-path tokens are independently random and opaque. The
  index durably reserves those identifiers and bounded metadata in a write
  intent before ciphertext publication, then activates the same row after the
  ciphertext commit. A close/reopen retry after a crash reuses the original
  intent, identifiers, creation time, and expiry. An existing pre-v3 schema
  fails closed; this workflow performs no implicit migration.
- Active-record and write-intent rows authenticate all identity, path, dedup,
  size, version, creation, and expiry metadata with a distinct HKDF-derived key.
  Reads, activation, expiry mutation, verification, and purge planning verify
  that MAC first. Exact schema validation rejects changed constraints, triggers,
  views, and other unexpected objects.
- The master key has a current-user DPAPI envelope and a separate offline
  recovery-key envelope. Recovery material cannot share the vault volume.
- Windows DPAPI and BitLocker probes are loaded lazily behind injected probes,
  so non-Windows CI can import modules and collect synthetic tests safely.
- Recovery-key rewrap uses a crash-recoverable staged
  activation/reconciliation protocol. Current and new recovery locations are
  both validated before vault/DPAPI/private-key access and both volume-evidence
  bindings are revalidated before rewrap. It must not claim cross-volume
  atomicity.
- The index contains only random record IDs, encrypted relative paths, HMAC
  deduplication values, timestamps, expiry timestamps, and integrity metadata.
- `verify` reports durable but unactivated write intents as pending. Expired
  intents participate in the same bounded purge plan as active expired and
  delete-pending records.
- Deduplicated copies of the same message can only tighten the shared record's
  expiry to the earliest source-derived value. Duplicate attachment bytes do
  not extend retention by default; only a separately reviewed, still-valid
  governed attachment binding may explicitly extend the shared blob to that
  binding's bounded expiry.
- One cross-process mutation lock spans each vault-plus-corpus message upsert,
  attachment binding, and exact purge plan/transaction/delete sequence.
  Corpus-aware purge first removes all affected message, pair, source,
  reference, quotation, attachment-binding, and attachment-blob metadata in
  one authenticated corpus transaction, then deletes exactly the planned
  vault records. If the corpus transaction fails, vault deletion does not
  start. If later ciphertext deletion fails, extra encrypted material may
  remain, but no corpus-to-vault dangling reference is permitted.
- Plaintext may exist only in memory or a restricted vault-local temporary
  directory and is deleted after use. No secure-erase claim is made for
  SSD/flash media.
- `revoke` requires explicit operator confirmation and removes usable key
  envelopes; it does not mutate the source mailbox or claim recoverability
  without the offline recovery key.

## 10. Private Knowledge Lifecycle

- Knowledge cards contain generic rules only and reject people, organizations,
  domains, addresses, phones, URLs, filenames, message IDs, source hashes,
  verbatim text, exact amounts, exact dates, transaction IDs, and source
  locators.
- Default approval requires evidence from at least three independent
  conversations and two counterparties, business approval, and privacy
  approval.
- Price, payment, contract, quality, and legal rules also require an
  accountable-owner approval.
- Candidates expire after 30 days. Approved cards are reviewed at least
  quarterly and may be deprecated or revoked.
- The authority repository and signed runtime snapshot use a key and namespace
  separate from the raw vault. Runtime access is verified and read-only; a
  missing, expired, invalid, or tampered snapshot yields an empty card set.
- Authority, candidate, runtime snapshot, `.pkevalstage`, and `.pkeval`
  project-external checks reject the same complete Project Container root while
  retaining their existing private-store separation and fixed-error contracts.

## 11. DeepSeek And Evaluation Gates

DeepSeek receives only locally deidentified current visible thread content,
deidentified supported attachment text, and at most eight approved cards with
at most 4,000 rendered characters. It receives no binary, URL, path, raw-vault
identifier, source locator, or restoration map.

The safe defaults remain:

```text
EMAIL_AGENT_LLM_PROVIDER=disabled
EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative
EMAIL_AGENT_DEEPSEEK_MODEL=deepseek-v4-flash
```

Automated tests use injected fake clients and never use the network. A private
evaluation first runs 20 gate cases. Any schema, safety, grounding, or
aggregate-only serialization violation, or gate p95 latency above 12 seconds,
stops all remaining calls. No retry is permitted. The remaining 180 Flash
cases and 40 separately approved Flash/Pro paired cases run only after the gate
passes. Reports contain fixed metric names, counts, rates, latency aggregates,
model names, and fixed error codes only.

## 12. Data And Interface Changes

### Public API

```text
None.
```

### Public SQLite

```text
None.
```

### Browser Extension

```text
None. It remains current-message, user-click-only.
```

### AI Output JSON

```text
No public schema change. Invalid or unsafe private output falls back to rules.
```

## 13. Acceptance Criteria

1. Governance names one administrator CLI, one account, one fixed endpoint,
   one rolling 24-month window, and no scheduled or runtime integration.
2. The browser extension permissions and click-only current-message behavior
   remain unchanged.
3. Architecture tests reject importer references from `frontend/`,
   `backend.email_agent`, and every script except the one approved CLI.
4. Transport constraints list the allowed read-only operations and mechanically
   forbid write IMAP, SMTP, and non-PEEK body fetches.
5. Authorization and content-free inventory fingerprint confirmation precede
   content retrieval.
6. External-vault, key separation, knowledge review, evaluation stop rules,
   rollback, and explicit non-goals are documented.
7. No test or implementation step accesses a mailbox, real data, a vault, or a
   remote API.

## 14. Test Plan

- Run governance tests RED before changing active docs or generator behavior.
- Run focused generator, architecture, static-linter, and mailbox transport
  suites with `EMAIL_AGENT_LLM_PROVIDER=disabled`.
- Run complete unit discovery, `git diff --check`, and the maintenance scan
  before each task-level completion claim.
- Use only synthetic values and injected probes/clients.
- Regenerate `docs/operations/project_status_log.md` once in final Task 7 after
  all implementation tasks. Task 1 verifies `build_project_status()` only to
  avoid an intermediate authoritative snapshot.

## 15. Rollback

1. Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and do not run the administrator
   CLI.
2. Remove or disable access to the project-external runtime knowledge snapshot;
   normal analysis then uses generic rules.
3. Use the explicitly confirmed `revoke` path only when key-envelope revocation
   is intended. Never modify mailbox data during rollback.
4. Use `rewrap-recovery` and its staged reconciliation path for recovery-key
   migration; do not rely on cross-volume atomic replacement.
5. Revert implementation commits in reverse order if the isolated capability
   must be removed. Existing extension behavior remains available.

## 16. Human Confirmation Needed

- Live inventory and scan require the operator's non-sensitive authorization
  identifier, one account identifier, interactive app password, and exact
  inventory fingerprint confirmation.
- Attachment retrieval requires a separate reviewed manifest.
- Any DeepSeek evaluation or production use requires a separate operator-run
  authorization after all offline gates pass.
- Recovery rewrap and vault revocation require explicit operator confirmation.

## 17. Execution Record

Task 1 establishes governance only. No mailbox, real data, external vault,
credential, or remote provider was accessed. Project-status file regeneration
is deliberately deferred to Task 7; Task 1 validates generator output through
focused tests.
