---
last_update: 2026-07-22
status: active
owner: "@tobyWang"
review_cycle: quarterly
source_type: decision_record
---

# ADR 0008: Bounded corpus-to-runtime handoffs

## Status

Accepted for offline implementation on 2026-07-22. This decision ratifies two
narrow seams but does not authorize live mailbox access, initialize an evidence
inbox, or run candidate extraction.

## Context

The accepted architecture separates the administrator-only historical corpus
from click-only current-message analysis. The product now needs an explicit
contract for two future workflows without turning either context into a general
reader for the other: administrator-triggered incremental synchronization and a
write-only deidentified current-click evidence handoff.

## Exact clauses partially superseded

This ADR does not broadly replace ADR 0006 or ADR 0007. It changes only these
named clauses:

- **ADR 0006 / Separate the administrator workflow**: the absolute statement
  that the normal runtime data flow is unchanged is narrowed only enough to
  permit an internal write-only deidentified evidence append. The sole mailbox
  importer and all mailbox-enumeration prohibitions remain unchanged.
- **ADR 0006 / Require two-phase authorization**: the inventory gate now
  explicitly applies before every initial or incremental content-bearing run.
- **ADR 0006 / Schedule periodic import or evaluation**: the rejection of a
  scheduled or periodic job remains; a manual sync is one explicit operator run,
  not polling or automation.
- **ADR 0007 / Acquisition boundary**: the same clicked, validated, visible
  current-message scope may later be projected into a deidentified evidence
  contract after the current analysis result is available. Collection timing,
  resource ownership, stale-state checks, and attachment limits remain unchanged.
- **ADR 0007 / Privacy and media boundary**: only derived deidentified text may
  cross the internal append seam. Raw thread content, media, bytes, filenames,
  paths, URLs, cookies, tokens, temporary files, and provider material do not.
- **ADR 0007 / Consequences**: an internal append capability is permitted, but
  the public API and public SQLite remain unchanged.

ADR 0007 sections **Provider route through Budgets remain unchanged**, including
the provider-disabled defaults, call limits, validation, fallbacks, and the
60/55/35/10/12/8/5 timing contract.

## Decision

### Ratify a future manual incremental-sync seam

Administrator-triggered incremental synchronization remains a manual,
administrator-only extension of `scripts/manage_mailbox_vault.py`. Every future
content-bearing run must use one authorized account, the fixed `imap.exmail.qq.com:993` endpoint,
TLS certificate verification, the rolling
24-calendar-month scope, and an exact current inventory fingerprint confirmed
before content access. Transport remains read-only and limited to `LIST`,
read-only `EXAMINE`, `UID SEARCH`, and bounded `UID FETCH` with `BODY.PEEK`.

There is no browser, normal API, scheduler, cleanup, polling, or background trigger.
Mailbox mutation and arbitrary transport remain prohibited. This future seam is
**not implemented by this decision**; future issue #17 owns its command, state,
idempotency, reporting, and processing behavior. The existing command set stays
unchanged in issue #10.

### Ratify a write-only current-click evidence seam

The normal runtime may construct `CurrentClickEvidenceV1` only from the scope of
one explicit Analyze click. The contract contains only bounded, locally
deidentified text, sequential request-local source markers, an opaque UUIDv4
submission ID, a whole-second UTC creation time, and explicit parse/semantic
status. It rejects unknown fields, placeholders, residual private artifacts, raw
headers, message/thread IDs, source locators, attachment names, paths, URLs,
binary or Base64 data, keys, mappings, runtime cards, snapshot metadata,
authority metadata, prompts, and provider output.

Contract validation rejects raw message-header shapes, message/thread/private
metadata fields, labeled or prefixed secrets, auth/JWT material, Base64-like
payloads, serialized JSON/Python mapping shapes, hidden controls, and explicit
provider/model response fields before the generic residual scan. The predicate
returns only a boolean and never returns the match. The package has no provider
import; future issue #18 must preserve local-source provenance when it builds the
mapping and may not use provider output as evidence.

Normal runtime receives only one opaque callable:

```text
append(CurrentClickEvidenceV1) -> fixed content-free receipt
```

The capability is write-only. It has no read, get, list, search, query, delete,
path, key, repository, mailbox, raw-vault, candidate, authority, snapshot, or
restoration capability. Validation completes before append. A validation or
append failure returns only a fixed code and cannot change the current analysis
result.

The encrypted evidence inbox, candidate job, visible state, cancellation, and
post-result orchestration belong to future issue #18 and are not implemented by
this decision. When implemented, the inbox must use a separate external path,
key, magic, HKDF purpose, namespace, and AEAD associated data from the raw vault,
candidate store, authority repository, runtime snapshot, evaluation stores, and
public SQLite.

### Preserve one-way authority and activation

The current runtime still receives approved knowledge only as the immutable
startup-loaded tuple. It cannot read the authority repository, raw vault,
historical store, evidence inbox, keys, paths, mappings, or snapshot metadata.
There is no hot reload, polling, watch loop, evidence status endpoint, or
automatic publication. Appending evidence cannot approve a candidate, publish
knowledge, change a snapshot, or affect the analysis that produced it.

## Consequences

- Issues #17 and #18 have explicit dependency directions and cannot expand the
  browser or normal API into mailbox/store readers.
- The handoff contract can be tested with synthetic values and an injected
  callback without filesystem, credential, mailbox, vault, or provider access.
- Public analysis responses, public SQLite, provider routing, deterministic
  fallback, and restart-only knowledge activation remain compatible.
- Append failures are isolated from daily analysis and expose no store detail.

## Rollback

1. Do not configure an append callback; no evidence leaves request-local memory.
2. Keep all providers disabled and do not run the administrator CLI.
3. Revert the contract, guards, and this ADR. There is no data migration because
   this decision creates no inbox and changes no public schema.
