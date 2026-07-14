---
last_update: 2026-07-14
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

The administrator-only CLI is `scripts/manage_mailbox_vault.py`. Its approved
commands are `init`, `inventory`, `scan`, `attachments`, `verify`,
`purge-expired`, `revoke`, and `rewrap-recovery`. There is no scheduled job,
automatic trigger, browser command, or normal-runtime hook.

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

Mechanically forbidden operations are `STORE`, `APPEND`, `COPY`, `MOVE`,
`EXPUNGE`, `CREATE`, `DELETE`, `RENAME`, `SUBSCRIBE`, `UNSUBSCRIBE`, SMTP, and
any command that can change flags or mailbox state. A connection that cannot
prove the required read-only state fails closed.

## 9. External Vault And Key Boundary

- The raw vault is outside the project, OneDrive, and system temporary
  directories on a proven NTFS BitLocker To Go volume.
- Every raw record is independently protected with AES-256-GCM and a random
  nonce. The random record ID is authenticated as associated data.
- The master key has a current-user DPAPI envelope and a separate offline
  recovery-key envelope. Recovery material cannot share the vault volume.
- Windows DPAPI and BitLocker probes are loaded lazily behind injected probes,
  so non-Windows CI can import modules and collect synthetic tests safely.
- Recovery-key rewrap uses a crash-recoverable staged
  activation/reconciliation protocol. It must not claim cross-volume atomicity.
- The index contains only random record IDs, encrypted relative paths, HMAC
  deduplication values, timestamps, expiry timestamps, and integrity metadata.
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
