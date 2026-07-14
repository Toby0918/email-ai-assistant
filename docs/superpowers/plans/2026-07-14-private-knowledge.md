---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Private Knowledge Derivation And Review Plan

## Goal

Implement master-plan Task 4: locally deidentify authorized encrypted source
records, derive generic `KnowledgeCardV1` candidates, enforce business/privacy
review, and publish a signed encrypted read-only runtime snapshot without
exposing raw or identifying source material.

## Preconditions

- Governance in ADR 0006 is active and the external vault has passed its own
  offline policy, crypto, integrity, and authorization tests.
- Codex, automated tests, and DeepSeek receive no raw vault data. All fixtures
  are synthetic.
- The private-knowledge authority repository uses a key and record namespace
  separate from the raw mailbox vault.
- No knowledge operation is scheduled or reachable from the browser extension.

`stage-knowledge` is a later Task 4 handoff command implemented only in the
administrator-only `scripts/manage_mailbox_vault.py`; the eight core vault
commands remain unchanged. It accepts only a reviewed manifest of approved
random record IDs, decrypts one record at a time, runs the local
private-knowledge deidentifier and residual scanner in memory, releases raw
plaintext and the ephemeral mapping before the next record, and writes only an
encrypted deidentified candidate batch under a separate knowledge namespace.
Its result and all output, logs, receipts, and errors contain only candidate
IDs, counts, and fixed codes, never raw record IDs, text, mapping,
paths, locators, or identifying values. `scripts/manage_private_knowledge.py`,
Codex, DeepSeek, normal runtime, and automated tests never import or read the raw
vault.

Task 4 creates `tests/test_manage_mailbox_vault_stage_knowledge.py`; that suite
uses only synthetic records and injected collaborators for the exact interface:

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

## Deidentification Contract

`deidentify_private_text()` returns placeholder text plus an ephemeral mapping
owned by the current local call. Repository, snapshot, log, exception, report,
and model interfaces cannot accept or serialize that mapping.

The local deidentifier and residual scanner cover at least:

- people, organizations, counterparties, domains, email, phones, postal
  addresses, URLs, and filenames;
- local paths, UNC paths, message IDs, order/invoice/tracking/part identifiers,
  source hashes, and transaction IDs;
- exact amounts, exact dates, verbatim passages, prompt injection, source
  locators, and restoration hints.

Residual findings contain fixed codes and counts only, never matched text,
paths, identifiers, or values. Any residual or ambiguous result fails closed.

## KnowledgeCardV1 Contract

The schema rejects unknown keys and forbidden content. A card contains only a
generic rule, a bounded category/scope, review metadata, lifecycle timestamps,
and content-free aggregate evidence counts. It cannot contain a person,
company, counterparty, domain, address, phone, URL, filename, path, message ID,
source hash, verbatim text, exact amount, exact date, transaction ID, raw-vault
ID, source locator, or restoration map.

## Review Lifecycle

1. A deidentified candidate is created in the encrypted authority repository.
2. Default approval requires at least three independent conversations and two
   counterparties.
3. A named business role records business approval and a named privacy role
   records privacy approval. Approval records contain role/accountability
   metadata, not source text.
4. Price, payment, contract, quality, or legal rules also require a separate
   accountable-owner approval.
5. Candidates expire after 30 days if not fully approved.
6. Rejected candidates are removed according to the repository lifecycle.
7. Approved cards are reviewed at least quarterly; expired or superseded cards
   are deprecated and excluded from publication.
8. Revocation or deprecation creates a new authority state and snapshot; it
   never edits mailbox source data.

No self-approval shortcut, bulk approval, threshold override, or synthetic
evidence counter is permitted.

## Authority Repository And Snapshot

- Repository records are encrypted under a private-knowledge master key that
  is different from the raw-vault master key.
- Publication selects only approved, not-expired, not-deprecated cards and
  writes a signed encrypted snapshot outside the project, OneDrive, and system
  temp.
- Publication uses same-volume atomic replacement after encryption and signing.
- Runtime verifies path policy, encryption, signature, schema, lifecycle, and
  card limits before returning an immutable read-only set.
- Missing, inaccessible, tampered, expired, or invalid snapshots return an
  empty set and a content-free fixed fallback code. Generic rules continue.
- Runtime receives no write handle, authority repository handle, source
  metadata, evidence locator, or deidentification mapping.

## Operator CLI

`scripts/manage_private_knowledge.py` provides explicit commands to create a
candidate, record business approval, record privacy approval, record extra
accountable-owner approval, reject, expire, approve, deprecate, revoke, and
publish a snapshot. Commands require local policy validation and never accept
raw mailbox content on a command line.

## Implementation Sequence

1. Add RED staging tests in
   `tests/test_manage_mailbox_vault_stage_knowledge.py` for the exact injected
   interface, approved random IDs, one-record-at-a-time decryption, raw
   plaintext and mapping release, encrypted candidate-only writes, and
   content-free outputs.
2. Add RED schema tests for exact keys, enum domains, unknown-key rejection,
   forbidden content, and log-safe errors.
3. Add RED deidentification/residual tests across every identifier class and
   prompt-injection case.
4. Add RED lifecycle tests for evidence thresholds, dual approval, extra
   accountable approval, candidate expiry, rejection deletion, quarterly
   review, deprecation, and revocation.
5. Add RED repository/snapshot tests for separate key namespace, encryption,
   signature tamper, external path, atomic publication, immutable runtime view,
   and empty-set fallback.
6. Implement strict schema and local deidentification, then add the
   administrator-only `stage-knowledge` handoff to
   `scripts/manage_mailbox_vault.py` without changing the eight core commands.
7. Implement the encrypted authority repository and lifecycle, signed encrypted
   snapshot publication, read-only loader, and private-knowledge CLI.
8. Update the eventual schema/security/operator docs and run focused GREEN.

## Verification Gates

- Provider remains disabled and no network access occurs.
- Tests use synthetic identities and fixed example domains only.
- No test failure includes matched or source text.
- Schema, deidentifier, residual scanner, lifecycle, snapshot, runtime loader,
  and CLI suites pass.
- Repository leakage, architecture, static, full discovery, `git diff --check`,
  and maintenance gates pass before completion claims.

## Rollback

Stop snapshot publication and remove runtime read access to the external
snapshot. Runtime then returns an empty card set and deterministic rules remain
available. Deprecate or revoke affected cards in the authority repository; do
not edit raw source records or mailbox data. Revert Task 4 implementation
commits if the package must be removed.

## Explicit Non-Goals

- No raw source browser, search UI, report, export, or model prompt.
- No automatic approval, automatic publication, or model-generated authority.
- No identifying or verbatim knowledge card.
- No shared encryption key/namespace with the raw vault.
- No writable runtime snapshot or runtime access to the authority repository.
- No source locator, restoration map, or exact fact sent to DeepSeek.
