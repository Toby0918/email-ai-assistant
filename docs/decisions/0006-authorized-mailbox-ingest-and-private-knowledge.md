---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: quarterly
source_type: decision_record
---

# ADR 0006: Authorized mailbox ingest and private knowledge

## Status

Accepted for offline implementation on 2026-07-14. Live mailbox access,
external-vault initialization with real material, private DeepSeek evaluation,
and production provider enablement remain separately operator-run activities.

## Context

The browser product intentionally analyzes only the currently visible message
after an explicit click. The company now requires a bounded historical
analytical snapshot from one authorized Tencent Exmail account so it can derive
reviewed, non-identifying business rules. Treating that requirement as a normal
extension capability would break the product's privacy model and make mailbox
enumeration reachable from daily runtime code.

The snapshot contains sensitive source material and is not suitable for Git,
OneDrive, the existing public SQLite database, ordinary logs, or model input.
The derived knowledge also needs a review and revocation lifecycle before it can
influence current-message analysis.

## Decision

### Separate the administrator workflow

- Only the operator-run `scripts/manage_mailbox_vault.py` administrator-only
  CLI may import `backend.mailbox_ingest`.
- The exception is limited to one authorized account, the fixed
  `imap.exmail.qq.com:993` endpoint, TLS certificate verification, and a rolling
  24-month window.
- There is no scheduled job, background poller, extension command, local-debug
  command, normal-backend route, or cleanup-agent hook.
- The browser extension and normal runtime remain click-only and cannot scan a
  mailbox. Their permissions, public API, public SQLite projection, and human
  review contract remain unchanged.

### Require two-phase authorization

The operator first supplies a non-sensitive authorization ID and runs a
content-free inventory. Inventory returns aggregate counts and size, opaque
folder identifiers, UIDVALIDITY, date scope, and an inventory fingerprint. A
scan starts only when the operator confirms that exact fingerprint. A changed
fingerprint, authorization scope, account, endpoint, UIDVALIDITY, or date gate
fails closed.

The 24-month boundary means calendar months calculated from validated IMAP
`INTERNALDATE`. Missing or invalid dates fail closed; the implementation must
not substitute 730 days or extend retention from ingest time.

### Use a fixed read-only transport

The isolated wrapper permits only `LIST`, read-only `EXAMINE`, `UID SEARCH`,
and bounded `UID FETCH` with `BODY.PEEK`. It provides no arbitrary IMAP command
passthrough. `STORE`, `APPEND`, `COPY`, `MOVE`, `EXPUNGE`, `CREATE`, `DELETE`,
`RENAME`, `SUBSCRIBE`, `UNSUBSCRIBE`, `BODY[]` without `PEEK`, SMTP, flag
mutation, and mailbox mutation are prohibited mechanically and at runtime.

### Store an encrypted analytical snapshot externally

- The vault must be on a proven NTFS BitLocker To Go volume outside the
  repository, OneDrive, and system temp. It is an analytical snapshot, not a
  legal archive or complete backup.
- Each record is protected with AES-256-GCM, a fresh nonce, and authenticated
  record identity. The metadata-only index contains random record IDs,
  encrypted relative paths, keyed deduplication values, timestamps, bounded
  expiry, and integrity fields only.
- Task 2 accepts caller-supplied expiry but caps it at no later than the current
  time plus 24 calendar months. Ingest code derives the actual earlier expiry
  from validated `INTERNALDATE`; it cannot extend retention at ingest time.
- The master key has a current-user DPAPI envelope plus a separately stored
  offline recovery envelope. DPAPI and BitLocker access is lazy and injected in
  tests so non-Windows CI can import modules without probing the host.
- Recovery rewrap uses a crash-recoverable staged activation and reconciliation
  protocol; no cross-volume atomicity is claimed. Whole-vault `revoke` requires
  explicit confirmation.

### Derive reviewed non-identifying knowledge

Raw records are deidentified locally. Knowledge cards contain generic rules and
no people, organizations, domains, contact details, URLs, paths, filenames,
message IDs, hashes, verbatim text, exact amounts, exact dates, transaction IDs,
or source locators. Default approval needs at least three independent
conversations, two counterparties, business approval, and privacy approval.
Price, payment, contract, quality, or legal rules need an additional
accountable-owner approval. Candidates expire after 30 days; approved cards are
reviewed quarterly.

The private authority repository and signed runtime snapshot have a key and
namespace separate from the raw vault. A missing, invalid, expired, or tampered
snapshot returns no private cards and leaves deterministic rules available.

### Gate DeepSeek with local deidentification and bounded evaluation

DeepSeek can receive only the locally deidentified current visible thread,
deidentified supported attachment text, and at most eight approved cards
totalling at most 4,000 characters. It receives no raw vault data, binary, URL,
path, source locator, vault identifier, or restoration mapping. Codex and
DeepSeek never read the raw vault.

The local identity context covers current headers and every sender/recipient in
the bounded timeline sources selected for the prompt. Outbound truncation may
stop only at a complete token boundary and drops a field when no safe boundary
exists. Before either production analysis parser runs, provider output passes a
raw scan plus a bounded, duplicate-key-rejecting JSON privacy decode that scans
decoded keys and string leaves. Any invalid JSON or private artifact fails
closed to the complete rule result.

The provider stays disabled by default. Offline tests use injected clients.
Private live evaluation stops after its first 20 cases on any schema, safety,
grounding, serialization, or p95 latency gate failure. There is one call per
case and no retry. Flash remains default; Pro requires an approved paired
comparison and must improve quality without safety or latency regression.

## Alternatives Considered

### Extend the browser extension to enumerate the mailbox

Rejected. It would widen permissions and couple a high-risk administrative
operation to daily user runtime.

### Store raw imports in the existing SQLite database or OneDrive

Rejected. Those locations do not provide the required isolation, encryption
envelope, index minimization, recovery separation, and revocation boundary.

### Send historical raw messages to a model to derive knowledge

Rejected. It would disclose identifying source content, make review and
grounding weaker, and violate the local deidentification gate.

### Schedule periodic import or evaluation

Rejected. Manual execution and explicit fingerprint confirmation are required
for every content-bearing run.

## Consequences

- The normal product boundary remains simple and testable.
- Historical processing requires deliberate operator work, an external
  encrypted volume, and separate recovery handling.
- Knowledge publication is slower because it requires aggregation, privacy and
  business review, and sometimes accountable-owner review.
- Missing Windows volume evidence, invalid dates, changed inventory state,
  unavailable keys, expired approval, snapshot tamper, unsafe model output, or
  insufficient time budget all fail closed.
- Revocation can make encrypted records unavailable, but this project does not
  claim physical secure erase from SSD/flash media.

## Rollback

1. Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and do not run the administrator
   CLI.
2. Remove runtime access to the external private-knowledge snapshot; analysis
   returns to generic rules.
3. Use explicit `revoke` only for intended key-envelope revocation and
   `rewrap-recovery` for staged recovery-key migration.
4. Revert the isolated implementation commits in reverse order. Rollback never
   changes source mailbox data.

## Primary Sources Verified 2026-07-14

- Tencent Exmail configuration guide, page 24:
  https://main.qcloudimg.com/raw/document/product/pdf/613_46019_cn.pdf
- `cryptography` 49.0.0 package and supported environments:
  https://pypi.org/project/cryptography/49.0.0/
- Microsoft `CryptProtectData` current-user and machine behavior:
  https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- DeepSeek model list:
  https://api-docs.deepseek.com/api/list-models

These sources establish endpoint/platform/model facts only. They do not replace
the project's stricter authorization, privacy, retention, and fail-closed
controls.
