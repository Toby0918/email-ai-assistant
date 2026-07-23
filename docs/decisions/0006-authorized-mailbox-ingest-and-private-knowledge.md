---
last_update: 2026-07-23
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

Partially superseded by ADR 0008 only for the exact clauses named there: future
manual incremental synchronization and an internal write-only deidentified
current-click evidence append. Mailbox isolation, read-only transport, raw-vault
prohibitions, authority review, and startup-only runtime knowledge remain active.

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
- A newly initialized vault uses the exact schema-v3 index. Each record ID and
  encrypted relative-path token is independently random and opaque. Before
  ciphertext publication, the index durably reserves those identifiers and the
  bounded retention metadata in a write intent; a retry after a crash between
   ciphertext publication and index activation must recover and reuse that same
   intent rather than minting another identity or orphaning the ciphertext. The
   cross-process mutation lock uses OS-managed ownership so a live holder fails
   closed and a terminated process releases the lock; its persistent one-byte
   lock file is not an ownership marker.
  Existing pre-v3 indexes fail closed and are never implicitly migrated.
- Active-record and write-intent metadata are authenticated with a separate
  HKDF-derived purpose key. Every lookup, activation, expiry update, verification,
  and purge plan verifies the complete metadata row first. Fresh initialization
  also pins the exact canonical SQLite schema and rejects removed constraints,
  triggers, views, or other unexpected schema objects.
- Task 2 accepts caller-supplied expiry but caps it at no later than the current
  time plus 24 calendar months. Ingest code derives the actual earlier expiry
  from validated `INTERNALDATE`; it cannot extend retention at ingest time.
- Fully observed exact message copies share one encrypted record and can only
  constrain that record's expiry to the earliest applicable source expiry.
  First-pass messages with unread attachment or unselected MIME leaves are not
  claimed as exact aggregate duplicates and are conservatively counted
  separately. Exact attachment
  bytes also share one encrypted blob, but a separately reviewed, still-valid
  governed binding may explicitly extend that blob only to the binding's
  bounded expiry and only after the binding succeeds; duplicate writes do not
  extend expiry by default.
- `verify` reports durable write intents as pending work. Expired intents,
  active records, and delete-pending records share the same bounded purge
  lifecycle instead of leaving unindexed ciphertext outside retention.
- The master key has a current-user DPAPI envelope plus a separately stored
  offline recovery envelope. DPAPI and BitLocker access is lazy and injected in
  tests so non-Windows CI can import modules without probing the host.
- Recovery rewrap uses a crash-recoverable staged activation and reconciliation
  protocol; no cross-volume atomicity is claimed. Whole-vault `revoke` requires
  explicit confirmation.

### Bootstrap only governed sales pairs

The initial 24-month bootstrap uses a strict private policy containing one
company domain and exact salesperson addresses. `scan` reads that policy during
local preflight, before mailbox credentials, and binds only a vault-keyed
fingerprint to a fresh metadata-only corpus index. Policy values, paths, mail
addresses, message identifiers, subjects, bodies, filenames, mailboxes, UIDs,
and source locators are prohibited from that index and from public output.

The corpus index uses its own HKDF-derived, purpose-separated key. Every stored
row and relationship edge is protected by a table-domain-separated HMAC over a
canonical typed encoding. All safety-relevant lookups authenticate the row or
edge before using it, and full `validate` authenticates the complete index;
missing, malformed, substituted, or tampered metadata fails closed.

A learning edge requires an external customer request and a strictly later
allowlisted salesperson reply linked by validated `In-Reply-To` or
`References`; Message-ID local-part case remains exact while its domain is
normalized, and a subject is never sufficient. Automated/list/bulk traffic,
notifications, pure forwards, non-sales internal messages, signature- or
disclaimer-only content, bounded Outlook or Chinese quoted-header history,
cross-folder copies, and exact duplicate quotations are excluded or
deduplicated. Raw authorized messages
remain encrypted even when unpaired, but downstream staging and reviewed
attachment acquisition must reject any source record that is not part of a
governed pair.

The v3 scan checkpoint binds fully observed outcomes to keyed tokens over the
validated raw BODYSTRUCTURE, selected-part metadata, and fetched header/body
bytes. It omits tokens when any MIME leaf remains unread, caps the token map at
20,000 entries, and uses an explicit 4 MiB encrypted control envelope. The
knowledge, evaluation, and reviewed-attachment paths share one strict v1/v2
scan-record envelope validator; v2 releases its learning projection only to the
paired knowledge path as support text. Bounded header-derived identity context
remains local to one-record deidentification and aggregate evidence and is not
released as support text or staged raw content.

Supported reviewed attachment bytes are stored in source-independent encrypted
blobs and linked only through opaque metadata. The encrypted attachment payload
contains a fixed record framing plus the exact acquired raw bytes only; parser
output is not persisted in that blob. Identical bytes reuse one blob. Parsing
and semantic-review outcomes are authenticated metadata states, separate from
acquisition and deduplication; `parsed` does not mean semantically correct, and
only a newly admitted blob contributes to the top-level attachment success
count.

Retention purge is corpus-aware. One cross-process vault mutation lock spans the
exact purge plan, authenticated corpus transaction, and planned ciphertext
deletion. Message upserts and attachment bindings use that same operation-level
lock across their vault and corpus mutations. Purge first deletes every affected
corpus row and relationship and only then deletes the exact planned vault
records and ciphertext. A corpus transaction failure leaves
the vault untouched; a later vault deletion failure may leave extra encrypted
ciphertext, but must never leave a corpus reference dangling to a removed vault
record.

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

### Separate staged evaluation, final dataset, and local judging

The raw-vault bridge ends at an encrypted `.pkevalstage`. The evaluator may
decrypt only that strict `EvaluationStageV1`, revalidate exactly 200 unique cases,
complete production strata, current business/privacy approvals and at least 40
explicit Pro-pair approvals, then create one final `.pkeval` in a separate external
directory. It uses the same operator-supplied 32-byte hidden key but a fresh UUIDv4
final namespace, final-specific magic/HKDF purpose and a fresh random nonce. The
final target uses atomic no-clobber publication. The publication helper's successful
return is the final commit point; code never rolls back or unlinks the target by
pathname, and only best-effort internal-stage cleanup may follow. It never overwrites
or deletes a competitor. The reviewed stage is never deleted automatically. Build
constructs no provider or judge and makes no network call.

Live usefulness judging remains default-off. `run` requires both the exact
confirmation and explicit `--interactive-judge`, with stdin and stdout attached to
a real local TTY and one fixed exact-y readiness acknowledgement before the hidden
key or dataset is opened. The adapter receives
only `UsefulnessJudgeView`, renders deidentified input plus production-gated public
output only after rejecting terminal control/format characters, and accepts one
exact `y` or `n`. Invalid input, EOF or terminal failure
stops before the next provider call. The evaluator creates no transcript, per-case
record, prompt/output export, cache or log; only the aggregate-only report persists.
It cannot prevent external terminal capture. The fixed 20 Flash + 180 Flash / 40
Pro sequence, zero retry and no automatic production model switch remain binding.

### Planned V2 human-gold extension

Task 9 adds a documentation-only V2 contract and no runtime capability. It does
not implement V2 and does not open a real V2 dataset. V1 compatibility is an
architectural requirement: current V1 datasets remain supported, and there is no
in-place migration or implicit reinterpretation.

The future `PrivateEvaluationCaseV2` binds ordered deidentified thread segments
oldest-to-newest, reviewed attachment bindings, and an encrypted
`StructuredHumanReferenceV2`. The reference must be evidence-bound, finalized
before candidate generation, and carry independent business and privacy_security approvals by
distinct actors. Strict candidate/reference separation keeps authoring and
generation roles apart. Candidate generation receives only the approved deidentified evidence and cannot access or decrypt the reference, approvals, rubric, or prior verdict.
A blinded human judge receives the approved deidentified
thread/attachment evidence, sealed reference criteria, and an unlabeled candidate,
while provider and model identity and routing metadata remain hidden. Evaluation
continues to use aggregate-only reporting.

The prohibited artifacts include raw ChatGPT transcripts; they are not durable
evaluation evidence. The rejected operations include automatic training,
automatic upload of cases or references as a training corpus, model self-grading,
and any automatic production model switch. Any future V2
implementation, dataset opening, provider run, or training workflow requires a
separate approved plan and authorization.

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
