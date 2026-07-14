---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# External Mailbox Vault And Read-Only Import Plan

## Goal

Implement the external encrypted vault and the separately authorized,
administrator-only, one-account, read-only Tencent Exmail import path described
by ADR 0006. This subordinate plan covers master-plan Tasks 2 and 3 only.

## Preconditions

- Company written authorization exists, but the repository stores only a
  non-sensitive authorization identifier.
- Automated work uses synthetic fakes and injected probes only. No mailbox,
  real data, external vault, BitLocker state, credential, or network endpoint is
  accessed by Codex or tests.
- The browser extension, local debug page, normal backend, cleanup agent, and
  scheduled workflows remain outside this architecture.
- Every implementation step follows RED, observed failure, minimal GREEN, and
  focused verification before commit.

## Fixed Authorization And Inventory Contract

The only network endpoint is `imap.exmail.qq.com:993` with TLS certificate
verification. One command run names exactly one authorized account and a
rolling 24-month scope. The 24-month cutoff is calculated as calendar months
from validated IMAP `INTERNALDATE`; missing or invalid dates fail closed. It is
not 730 days and ingest time cannot extend retention.

`inventory` retrieves no headers, bodies, filenames, or attachment sections.
It records content-free counts, aggregate size, opaque folder identifiers,
UIDVALIDITY, date window, and a deterministic inventory fingerprint. `scan`
requires `--confirm-inventory-fingerprint` to match the most recent inventory.
A mismatch stops before content retrieval.

The app password comes only from interactive `getpass` after local policy
checks. There is no password option, environment-variable source, `.env`
source, persisted value, log field, exception detail, or diagnostic value.

## Authorized Mailbox Transport Policy

The wrapper exposes only:

```text
list_folders
examine
uid_search
uid_fetch_size
uid_fetch_bodystructure
uid_fetch_peek
```

The command allowlist is `LIST`, read-only `EXAMINE`, `UID SEARCH`, and bounded
`UID FETCH` with `BODY.PEEK`. There is no arbitrary IMAP command passthrough.
Until Task 3 adds runtime validator tests, every target is a finite single-UID
decimal literal. Task 3 may add only the direct bare local, non-imported,
non-reassigned expression `validate_single_uid_fetch_target(uid)` in the same
change as its runtime tests; wildcard, range, sequence, dynamic, and qualified
targets remain forbidden.
The following are forbidden: `STORE`, `APPEND`, `COPY`, `MOVE`, `EXPUNGE`,
`CREATE`, `DELETE`, `RENAME`, `SUBSCRIBE`, `UNSUBSCRIBE`, `BODY[]` without
`PEEK`, `SMTP`, and every operation that can change flags or mailbox state.

The folder policy includes Inbox, Sent, Archive, and reviewed business custom
folders. Drafts, Trash, Junk/Spam, and configured high-sensitivity categories
are excluded. Any ambiguous folder, command, response, UIDVALIDITY transition,
or read-only state fails closed.

## External Volume And Key Contract

- The vault root is on a proven NTFS BitLocker To Go volume and outside the
  project, OneDrive, and system temp.
- Recovery material is on a different volume from the vault.
- Windows DPAPI and BitLocker functions are lazily loaded behind injected
  probes. Linux/non-Windows CI must be able to import modules and collect all
  synthetic tests without touching Windows APIs or host volume state.
- Each record uses AES-256-GCM, a fresh random nonce, and record ID as associated
  data. Tamper, nonce misuse, or record-ID substitution fails closed.
- The master key has a current-user DPAPI envelope and a separately protected
  offline recovery envelope.
- Recovery-key rewrap uses a crash-recoverable staged activation and
  reconciliation protocol. Prepare the new envelope, durably record staged
  state, verify it, activate it, and reconcile interrupted states. Do not claim
  cross-volume atomicity.
- `revoke` requires explicit typed confirmation and revokes usable key
  envelopes. It never connects to or mutates the source mailbox.

## Metadata-Only Index And Retention

The vault index may contain only random record IDs, encrypted relative paths,
HMAC deduplication values, timestamps, expiry timestamps, and integrity
metadata. It must not contain plaintext subjects, addresses, folders, bodies,
attachment names, message IDs, UIDs, or business identifiers.

Task 2 accepts a caller-supplied expiry only when it is no later than the
current time plus 24 calendar months. Task 3 derives each record's actual
expiry from validated IMAP `INTERNALDATE` and never extends it from ingest
time. `purge-expired` removes expired encrypted records and metadata but makes
no physical secure-erase claim for SSD/flash storage.

## Fetch Phases

First-pass scan fetches headers, selected `text/plain` or `text/html` MIME
sections, and attachment metadata using `BODY.PEEK`; it never fetches
attachment bodies. Plaintext exists only in memory before encrypted storage.

Second-pass `attachments` requires a separately reviewed manifest, accepts at
most 50 representative files, enforces 10 MiB per file and 25 MiB per
conversation, rejects active or unsupported content, and uses a restricted
vault-local temporary directory. Plaintext artifacts are deleted after
processing without claiming physical secure erase.

## CLI Contract

```text
init
inventory
scan
attachments
verify
purge-expired
revoke
rewrap-recovery
```

These remain the eight core vault commands. `stage-knowledge` is a later Task 4
handoff command implemented only in the administrator-only
`scripts/manage_mailbox_vault.py`; it does not widen Task 2 or Task 3 transport,
runtime, browser, or scheduling boundaries. It accepts only a reviewed manifest
of approved random record IDs, decrypts one record at a time, runs the local
private-knowledge deidentifier and residual scanner in memory, releases raw
plaintext and the ephemeral mapping before the next record, and writes only an
encrypted deidentified candidate batch under a separate knowledge namespace.
Its result and all output, logs, receipts, and errors contain only candidate
IDs, counts, and fixed codes, never raw record IDs, text, mapping,
paths, locators, or identifying values. `scripts/manage_private_knowledge.py`,
Codex, DeepSeek, normal runtime, and automated tests never import or read the raw
vault.

Task 4 creates `tests/test_manage_mailbox_vault_stage_knowledge.py` and uses the
exact injected interface below with synthetic readers and writers only:

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

Operational commands require `--vault`, `--authorization-id`, and one account
identifier. `scan` also requires `--confirm-inventory-fingerprint`.
`attachments` requires the reviewed manifest. `revoke` and
`rewrap-recovery` require explicit operator confirmation. No command is
scheduled or exposed to the browser/normal runtime.

## Implementation Sequence

### Vault primitives

1. Add exact dependency tests for `cryptography==49.0.0` in existing
   `tests/test_repo_utils.py` and `tests/test_static_linter_constraints.py`.
2. Add RED tests for volume evidence, forbidden locations, DPAPI injection,
   AES-GCM round trip/tamper/nonce/AAD, separate recovery volume, staged rewrap
   reconciliation, metadata allowlist, calendar-month expiry cap, purge,
   verify, and revoke.
3. Implement policy probes and key envelopes without importing or probing
   Windows facilities at module-import time.
4. Implement encrypted records and the metadata-only index, then run focused
   GREEN.

### Read-only importer

1. Add synthetic IMAP/bodystructure/inventory/scan/attachment/CLI RED tests.
2. Prove exact host, port, TLS verification, password acquisition order,
   calendar-month boundary, fingerprint gate, folder policy, command allowlist,
   `BODY.PEEK`, unchanged flags, resume cursor, deduplication, and
   UIDVALIDITY stop.
3. Implement the narrow wrapper, content-free inventory, first-pass scan, and
   approved attachment pass.
4. Implement all eight CLI commands and run focused GREEN.

## Verification Gates

- Provider is explicitly disabled.
- No test opens a socket or queries host DPAPI/BitLocker state.
- Exact dependency, crypto, policy, index, transport, bodystructure, inventory,
  scan, attachment, and CLI suites pass.
- Architecture/static transport guards pass.
- Full unit discovery, `git diff --check`, and maintenance scan pass before
  completion claims.

## Rollback

Do not run the CLI. If a runtime snapshot exists, remove its access separately;
it is not part of this vault. Use confirmed `revoke` only to invalidate vault
key envelopes. Use `rewrap-recovery` and staged reconciliation for recovery-key
migration. Revert implementation commits in reverse order. Never mutate source
mailbox data as rollback.

## Explicit Non-Goals

- No SMTP or mailbox write action.
- No arbitrary host/account/date/command mode.
- No scheduled scan, IDLE loop, background poller, browser integration, or
  normal-backend route.
- No legal archive, full backup, automatic second backup, or secure-erase
  claim.
- No raw content in Git, OneDrive, logs, public SQLite, docs, tests, status, or
  maintenance output.
- No DeepSeek or Codex access to the raw vault.

## Primary Sources Verified 2026-07-14

- Tencent Exmail configuration guide:
  https://main.qcloudimg.com/raw/document/product/pdf/613_46019_cn.pdf
- `cryptography` 49.0.0:
  https://pypi.org/project/cryptography/49.0.0/
- Microsoft `CryptProtectData`:
  https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
