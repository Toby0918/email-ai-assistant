---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Authorized Mailbox Ingest, Private Knowledge, And DeepSeek Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to execute this plan task by task.
> Every production change follows RED -> GREEN -> focused verification ->
> commit, followed by specification and code-quality review.

**Goal:** Add a separately authorized, administrator-only, one-account,
read-only IMAP import workflow that stores an encrypted analytical snapshot on
an external BitLocker volume, derives reviewed non-identifying company
knowledge, and supplies only locally deidentified current-message context and
approved knowledge cards to DeepSeek.

**Architecture:** The existing browser extension and loopback analysis API keep
their click-only current-message boundary. A new offline CLI-only import package
owns the fixed Tencent Exmail IMAP route and external vault. A separate private
knowledge package owns deidentification, review state, encryption, signing, and
runtime snapshot publication. The email analyzer consumes only the verified
read-only snapshot and deidentified request-local context; every missing,
invalid, late, or unsafe private component falls back to the existing rules.

**Tech Stack:** Python 3.12.13, standard-library `imaplib`, `ssl`, `sqlite3`,
`email`, `getpass`, `ctypes`, and `hmac`; `cryptography==49.0.0` for AES-256-GCM
and Ed25519; pinned `openai==2.45.0`; existing attachment parsers; JavaScript
browser extension; `unittest`.

## Approval And Safety Constraints

- The user approved this implementation plan on 2026-07-14 and states that a
  company written authorization exists. Real execution still requires a
  non-sensitive authorization identifier and an explicit inventory
  fingerprint confirmation.
- No implementation or automated test may connect to a mailbox or call
  DeepSeek. Tests use synthetic fakes only. Live import and private evaluation
  are operator-run activities after offline gates pass.
- The extension, local debug page, normal backend service, background cleanup,
  and scheduled jobs must never enumerate a mailbox. Only the new administrator
  CLI may do so.
- The importer is fixed to one account, `imap.exmail.qq.com:993`, TLS certificate
  verification, a rolling 24-month window, and a command allowlist equivalent
  to `LIST`, read-only `EXAMINE`, `UID SEARCH`, and `UID FETCH BODY.PEEK`.
- The 24-month window means calendar months from validated IMAP `INTERNALDATE`;
  missing or invalid dates fail closed. It is not 730 days and ingest time
  cannot extend retention. The Task 2 vault accepts caller-supplied expiry only
  when capped at no later than the current time plus 24 calendar months.
- Mechanically forbid IMAP `STORE`, `APPEND`, `COPY`, `MOVE`, `EXPUNGE`, folder
  creation/deletion/rename/subscription mutation, SMTP, and any command that can
  modify flags. Never use `BODY[]` without `PEEK`.
- The mailbox app password is acquired only with interactive `getpass`; it has
  no command-line flag, environment-variable source, `.env` source, log field,
  persisted value, or diagnostic representation.
- The raw vault is an analytical snapshot, not a legal archive. It must be on
  an NTFS BitLocker To Go volume outside the project, OneDrive, and system temp.
  Failure to prove the volume policy fails closed.
- Every raw record is AES-256-GCM encrypted with an independent random nonce.
  The master key has a current-user DPAPI envelope and a separate offline
  recovery-key envelope. Recovery material may not share a volume with the
  vault. V1 creates no automatic second backup.
- The vault index stores only random record IDs, encrypted relative paths,
  HMAC deduplication values, timestamps, expiry timestamps, and integrity
  metadata. It must not store plaintext subjects, addresses, folders, bodies,
  attachment names, or identifiers.
- First-pass import fetches headers, text/plain or text/html body sections, and
  attachment metadata only. It never fetches attachment body sections.
  Second-pass attachment collection is separately approved and capped at 50
  representative files, 10 MiB per file and 25 MiB per conversation.
- Raw plaintext may exist only in memory or in a restricted temporary directory
  on the unlocked vault volume and is deleted after processing. Documentation
  must not claim physical secure erase on SSD/flash media.
- Codex and DeepSeek never read the raw vault. Git, logs, public SQLite, tests,
  status reports, and maintenance reports contain no real or real-derived text.
- Knowledge cards contain generic rules only. They cannot contain people,
  companies, domains, addresses, phone numbers, URLs, filenames, message IDs,
  source hashes, verbatim text, exact amounts, exact dates, or transaction IDs.
- A default-approved knowledge card requires at least three independent
  conversations and two counterparties, business and privacy approval, and
  extra accountable-owner approval for price, payment, contract, quality, or
  legal rules. Candidates expire after 30 days; approved cards are reviewed
  quarterly.
- DeepSeek receives only the locally deidentified current visible thread,
  deidentified supported attachment text, and at most eight approved cards
  totaling at most 4,000 characters. It receives no binary, URL, path, vault
  identifier, source locator, or restoration map.
- DeepSeek output containing a placeholder, reidentification attempt,
  unsupported critical fact, unsafe commitment, invalid JSON, or invalid
  schema falls back safely. Exact local facts are supplied only by existing
  deterministic rule results.
- Safe defaults remain `EMAIL_AGENT_LLM_PROVIDER=disabled`,
  `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative`, and
  `deepseek-v4-flash`. One call, zero retries, JSON-only, thinking disabled,
  and `max_tokens=2400` remain mandatory.
- Interaction budgets are browser 15 seconds, backend 13 seconds, provider
  maximum 10 seconds, and provider minimum remaining budget 5 seconds.
- Public HTTP analysis response fields, public SQLite projection, extension
  render fields, and mandatory human-review behavior remain unchanged.

---

### Task 1: Establish the separately authorized governance boundary

**Files:**
- Create: `docs/operations/authorized_mailbox_ingest_task_brief.md`
- Create: `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`
- Create: `docs/superpowers/plans/2026-07-14-mailbox-vault.md`
- Create: `docs/superpowers/plans/2026-07-14-private-knowledge.md`
- Create: `docs/superpowers/plans/2026-07-14-private-deepseek-evaluation.md`
- Modify: `AGENTS.md`
- Modify: `docs/product/feature_scope.md`
- Modify: `docs/product/roadmap.md`
- Modify: `docs/security/email_data_handling.md`
- Modify: `docs/security/privacy_rules.md`
- Modify: `docs/constraints/tooling_constraints.md`
- Modify: `docs/constraints/architecture_constraints.md`
- Modify: `docs/constraints/linter_constraints.md`
- Modify: `scripts/generate_project_status.py`
- Modify: `tests/test_generate_project_status.py`
- Modify: `tests/test_architecture_constraints.py`
- Modify: `tests/test_static_linter_constraints.py`
- Create: `tests/test_mailbox_transport_constraints.py`

**Interfaces:**
- Add the project status `authorized_private_ingest_build` while preserving the
  normal runtime statement that the browser extension cannot scan a mailbox.
- Document that only `scripts/manage_mailbox_vault.py` may import
  `backend.mailbox_ingest`; extension and `backend.email_agent` may not.
- Document an explicit IMAP/SMTP forbidden-token policy for the isolated
  package and CLI.

- [ ] **Step 1: Write governance-contract tests first.** Add failing assertions
  that require the new stage, narrow admin exception, unchanged extension
  permissions, no importer reference from extension/runtime modules, and the
  read-only IMAP/SMTP mechanical rule.
- [ ] **Step 2: Run the focused tests and record RED.**
  `python -B -m unittest tests.test_generate_project_status tests.test_architecture_constraints tests.test_static_linter_constraints tests.test_mailbox_transport_constraints -v`
- [ ] **Step 3: Add the approved task brief, ADR, and three subordinate plans.**
  Include front matter, authorization/fingerprint gates, external vault and key
  boundaries, knowledge review lifecycle, evaluation stop rules, rollback, and
  explicit non-goals.
- [ ] **Step 4: Update project governance without weakening daily-runtime
  protections.** Make the exception precise: administrator CLI only, one
  authorized account, 24 months, no schedule, no browser/runtime integration.
- [ ] **Step 5: Update the status generator and focused tests to GREEN.**
- [ ] **Step 6: Commit.**
  `git commit -m "docs: authorize isolated mailbox ingest workflow"`

---

### Task 2: Implement external-vault policy, key wrapping, and encrypted records

**Files:**
- Modify: `requirements.txt`
- Create: `backend/mailbox_ingest/__init__.py`
- Create: `backend/mailbox_ingest/errors.py`
- Create: `backend/mailbox_ingest/models.py`
- Create: `backend/mailbox_ingest/drive_policy.py`
- Create: `backend/mailbox_ingest/dpapi.py`
- Create: `backend/mailbox_ingest/key_envelopes.py`
- Create: `backend/mailbox_ingest/vault_crypto.py`
- Create: `backend/mailbox_ingest/vault_index.py`
- Create: `backend/mailbox_ingest/vault.py`
- Create: `tests/test_mailbox_vault_crypto.py`
- Create: `tests/test_mailbox_vault_policy.py`
- Create: `tests/test_mailbox_vault_index.py`
- Create: `tests/test_mailbox_key_envelopes.py`
- Create: `tests/test_mailbox_vault.py`
- Modify: `tests/test_repo_utils.py`
- Modify: `tests/test_static_linter_constraints.py`

**Interfaces:**
- `validate_vault_location(vault_root, project_root, recovery_key_path) -> VolumeEvidence`
- `DpapiProtector.protect(bytes) -> bytes`; `unprotect(bytes) -> bytes`
- `initialize_key_envelopes(vault_root, recovery_key_path, dpapi) -> None`
- `open_master_key(vault_root, dpapi) -> bytearray`
- `rewrap_recovery_key(vault_root, old_recovery_path, new_recovery_path) -> None`
- `VaultCrypto.encrypt(record_id, plaintext) -> bytes`
- `VaultCrypto.decrypt(record_id, ciphertext) -> bytes`
- `VaultIndex` CRUD uses only the approved metadata columns.
- `MailboxVault.put_record`, `get_record`, `delete_record`, `verify`,
  `purge_expired`, and `revoke`.

- [ ] **Step 1: Add dependency and crypto/policy/index tests before code.** Cover
  exact `cryptography==49.0.0`, AES-GCM round trip, unique nonce, associated-data
  binding to record ID, tamper rejection, DPAPI wrapper behavior, recovery
  envelope migration, different-volume enforcement, NTFS/BitLocker evidence,
  prohibited project/OneDrive/temp locations, index allowlist, caller-supplied
  expiry capped at no later than now plus 24 calendar months, record deletion,
  revoke, and log-safe exceptions.
- [ ] **Step 2: Run focused tests and record RED.**
- [ ] **Step 3: Implement Windows volume evidence and fail-closed path policy.**
  Use fixed-argument subprocess calls only; no shell, no user-controlled command
  text. Tests inject a probe and never query the host BitLocker state.
- [ ] **Step 4: Implement DPAPI current-user envelope and separate recovery
  envelope.** Keep master keys mutable in memory where possible and wipe local
  bytearrays in `finally` blocks; document Python/OS memory limits honestly.
  Lazy-load DPAPI and BitLocker access behind injected probes so non-Windows CI
  can import modules and collect synthetic tests without probing the host.
- [ ] **Step 4a: Implement crash-recoverable recovery-key rewrap.** Use staged
  prepare, durable activation, verification, and reconciliation states; never
  claim cross-volume atomic replacement.
- [ ] **Step 5: Implement encrypted records and metadata-only SQLite index.**
  Use atomic same-volume replacement and randomized record paths. Do not expose
  plaintext values in repr, exceptions, diagnostics, or integrity output.
- [ ] **Step 6: Run focused tests to GREEN and commit.**
  `git commit -m "feat: add encrypted external mailbox vault"`

---

### Task 3: Implement the fixed read-only IMAP inventory and scan CLI

**Files:**
- Create: `backend/mailbox_ingest/authorization.py`
- Create: `backend/mailbox_ingest/folder_policy.py`
- Create: `backend/mailbox_ingest/bodystructure.py`
- Create: `backend/mailbox_ingest/imap_readonly.py`
- Create: `backend/mailbox_ingest/inventory.py`
- Create: `backend/mailbox_ingest/scan.py`
- Create: `backend/mailbox_ingest/attachment_scan.py`
- Create: `backend/mailbox_ingest/service.py`
- Create: `scripts/manage_mailbox_vault.py`
- Create: `tests/test_mailbox_authorization.py`
- Create: `tests/test_mailbox_bodystructure.py`
- Create: `tests/test_mailbox_imap_readonly.py`
- Create: `tests/test_mailbox_inventory.py`
- Create: `tests/test_mailbox_scan.py`
- Create: `tests/test_mailbox_attachments.py`
- Create: `tests/test_manage_mailbox_vault.py`

**Interfaces:**
- CLI commands: `init`, `inventory`, `scan`, `attachments`, `verify`,
  `purge-expired`, `revoke`, `rewrap-recovery`.
- All operational commands require `--vault`, `--authorization-id`, and one
  account identifier. `scan` additionally requires
  `--confirm-inventory-fingerprint`. `attachments` requires a local reviewed
  approval manifest and never accepts more than 50 selections.
- No password option exists. Network commands call `getpass.getpass()` only
  after all local policy checks pass.
- `ReadOnlyImapSession` exposes only `list_folders`, `examine`, `uid_search`,
  `uid_fetch_size`, `uid_fetch_bodystructure`, and `uid_fetch_peek`.
- Until Task 3 adds runtime validator tests, every `UID FETCH` target is a
  finite single-UID decimal literal. Task 3 may add only the direct bare local,
  non-imported, non-reassigned expression
  `validate_single_uid_fetch_target(uid)` in the same change as its runtime tests;
  wildcard, range, sequence, dynamic, and qualified targets remain forbidden.

- [ ] **Step 1: Write synthetic IMAP and CLI tests before code.** Assert fixed
  host/port/TLS context, no password flag/env access, two-phase fingerprint,
  rolling 24 calendar months from validated IMAP `INTERNALDATE`, fail-closed
  invalid/missing dates, no 730-day or ingest-time extension, folder
  inclusion/exclusion, inventory contains no content, exact command allowlist,
  `BODY.PEEK`, flags unchanged, resume cursor, duplicate HMAC handling, and
  stop-on-UIDVALIDITY-change.
- [ ] **Step 2: Add bodystructure tests.** Prove first-pass code selects only
  header/text MIME sections and attachment metadata. Include multipart/alternative,
  nested multipart, encoded filenames, malformed structures, and
  `message/rfc822` fail-closed behavior.
- [ ] **Step 3: Run focused tests and record RED.**
- [ ] **Step 4: Implement authorization, folder policy, and IMAP wrapper.** The
  wrapper must not expose raw client methods or arbitrary commands. Folder
  policy includes Inbox, Sent, Archive, and business custom folders while
  excluding Drafts, Trash, Junk/Spam and configured high-sensitivity folder
  categories.
- [ ] **Step 5: Implement inventory and fingerprint confirmation.** Inventory
  records content-free counts, aggregate size, folder opaque IDs,
  UIDVALIDITY, date window, and a deterministic fingerprint. It does not fetch
  headers, bodies, or attachment sections.
- [ ] **Step 6: Implement first-pass scanning.** Fetch only header and selected
  text body sections with PEEK. Parse in memory, classify high-sensitivity
  messages locally, encrypt eligible records, keep resume state, and confirm
  flags before/after when supported by the fake.
- [ ] **Step 7: Implement representative attachment pass.** Fetch only approved
  supported sections with PEEK, enforce 50/10 MiB/25 MiB caps before and during
  transfer, reject active/unsupported content, parse in a restricted vault-local
  temp directory, encrypt accepted binary/text records, and delete plaintext
  temp artifacts.
- [ ] **Step 8: Implement CLI dispatch, focused GREEN, and commit.**
  `git commit -m "feat: add authorized read-only mailbox importer"`

---

### Task 4: Implement deidentification, KnowledgeCardV1, review, and snapshot

**Files:**
- Modify: `scripts/manage_mailbox_vault.py`
- Modify: `tests/test_architecture_constraints.py`
- Create: `backend/private_knowledge/__init__.py`
- Create: `backend/private_knowledge/schema.py`
- Create: `backend/private_knowledge/deidentifier.py`
- Create: `backend/private_knowledge/residual_scanner.py`
- Create: `backend/private_knowledge/repository.py`
- Create: `backend/private_knowledge/review.py`
- Create: `backend/private_knowledge/snapshot.py`
- Create: `backend/private_knowledge/runtime_loader.py`
- Create: `scripts/manage_private_knowledge.py`
- Create: `docs/data/knowledge_card_v1.md`
- Create: `docs/security/private_knowledge_handling.md`
- Create: `tests/test_private_deidentifier.py`
- Create: `tests/test_knowledge_card_schema.py`
- Create: `tests/test_private_knowledge_review.py`
- Create: `tests/test_private_knowledge_snapshot.py`
- Create: `tests/test_manage_private_knowledge.py`
- Create: `tests/test_manage_mailbox_vault_stage_knowledge.py`

**Interfaces:**
- `KnowledgeCardV1.from_mapping(value) -> KnowledgeCardV1` strictly rejects
  unknown keys and forbidden content.
- `deidentify_private_text(text, context) -> DeidentifiedText` returns only
  placeholder text plus a local ephemeral mapping that is never serialized.
- `scan_residuals(deidentified) -> tuple[ResidualFinding, ...]` uses fixed error
  codes and never includes matched source text.
- Review commands create candidate, record business approval, record privacy
  approval, record extra accountable-owner approval, reject, expire, approve,
  deprecate, and publish snapshot.
- Runtime loader verifies signature, decrypts outside-project snapshot, filters
  approved/not-expired cards, and otherwise returns an empty immutable set.
- The exact raw-vault handoff interface is:

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

`stage-knowledge` is a later Task 4 handoff command implemented only in the
administrator-only `scripts/manage_mailbox_vault.py`; it does not change the
eight core vault commands. It accepts only a reviewed manifest of approved
random record IDs, decrypts one record at a time, runs the local
private-knowledge deidentifier and residual scanner in memory, releases raw
plaintext and the ephemeral mapping before the next record, and writes only an
encrypted deidentified candidate batch under a separate knowledge namespace.
Its result and all output, logs, receipts, and errors contain only candidate
IDs, counts, and fixed codes, never raw record IDs, text, mapping,
paths, locators, or identifying values. `scripts/manage_private_knowledge.py`,
Codex, DeepSeek, normal runtime, and automated tests never import or read the raw
vault. `tests/test_manage_mailbox_vault_stage_knowledge.py` uses only synthetic
records and injected `read_one_record` and
`write_encrypted_candidate_batch` collaborators.

- [ ] **Step 1: Write schema/deidentifier/review/snapshot tests first.** Cover
  names, companies, domains, addresses, email, phone, URL, filenames, local/UNC
  paths, order/invoice/tracking/part IDs, amounts, dates, prompt injection,
  verbatim/source locator/source hash rejection, exact-key schema, enum mapping,
  3-conversation/2-counterparty threshold, dual approval, extra approval,
  candidate expiry, rejection deletion, quarterly review, separate key
  namespace, signature tamper, read-only runtime view, and no-snapshot fallback.
- [ ] **Step 1a: Write the staging boundary test.** In
  `tests/test_manage_mailbox_vault_stage_knowledge.py`, prove approved random
  record IDs only, one-at-a-time decryption, in-memory deidentification and
  residual scanning, raw-plaintext and ephemeral-mapping release before the
  next record, encrypted candidate-only writes, content-free results, and
  synthetic injected I/O.
- [ ] **Step 2: Run focused tests and record RED.**
- [ ] **Step 3: Implement strict schema and local deidentification.** Residual
  findings contain only stable codes and counts. Mapping lifetime is confined to
  the caller and cannot be persisted by repository interfaces.
- [ ] **Step 4: Implement encrypted authority repository and lifecycle.** It
  must use a separate master key and record namespace from the raw vault.
- [ ] **Step 5: Implement signed encrypted runtime snapshot.** Publish outside
  project/OneDrive/temp with atomic replacement. Runtime opens read-only and
  accepts no write handle or source metadata.
- [ ] **Step 6: Implement CLI, documentation, GREEN, and commit.**
  `git commit -m "feat: add reviewed private company knowledge"`

---

### Task 5: Align the DeepSeek contract and add the production deidentification gate

**Files:**
- Create: `backend/email_agent/deepseek_analysis_contract.py`
- Modify: `backend/email_agent/deepseek_analysis_schema.py`
- Modify: `backend/email_agent/prompt_context.py`
- Create: `backend/email_agent/private_context_gate.py`
- Create: `backend/email_agent/private_knowledge_context.py`
- Modify: `backend/email_agent/analyzer.py`
- Modify: `backend/email_agent/analysis_budget.py`
- Modify: `backend/email_agent/config.py`
- Modify: `frontend/browser_extension/shared/api_client.js`
- Modify: `frontend/browser_extension/popup.html`
- Modify: `frontend/local_debug_page/index.html`
- Modify: `docs/prompts/analyzer_prompt.md`
- Modify: `docs/data/analysis_result_schema.md`
- Modify: `docs/security/email_data_handling.md`
- Modify: `docs/operations/deepseek_analysis_contract_alignment_task_brief.md`
- Create: `docs/superpowers/plans/2026-07-14-deepseek-analysis-contract-alignment.md`
- Modify: `tests/test_prompt_context.py`
- Modify: `tests/test_deepseek_analysis_schema.py`
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_analysis_budget.py`
- Modify: `tests/test_browser_extension_static.py`
- Modify: `tests/test_browser_extension_behavior.py`
- Modify: `tests/test_deepseek_documentation_contracts.py`
- Create: `tests/test_private_context_gate.py`
- Create: `tests/test_private_knowledge_context.py`

**Interfaces:**
- Implement the approved design in
  `docs/superpowers/specs/2026-07-14-deepseek-analysis-contract-alignment-design.md`
  so prompt and validator consume one contract definition.
- `build_private_model_context(request, rule_result, cards, budget) -> context | fallback_code`
  performs local deidentification and residual scanning before any client call.
- Card selection returns at most eight approved cards and at most 4,000 rendered
  characters.
- Provider text containing deidentification placeholders is rejected; no
  restoration mapping reaches the provider, parser, public response, SQLite,
  log, or exception.

- [ ] **Step 1: Add contract-parity tests from the approved design and record
  RED.** Include all required fields/types/enums/cardinality/evidence rules,
  deterministic rendering, compliant complete example, no fabricated sources,
  and prompt length ceiling.
- [ ] **Step 2: Add private-context and budget RED tests.** Prove residual
  detection prevents the injected client from being called, knowledge limits
  are enforced, placeholders in provider output fail closed, local rule facts
  survive safe merge, and public interfaces do not change. Require browser 15,
  backend 13, provider max 10, provider min 5.
- [ ] **Step 3: Implement the shared DeepSeek contract without loosening the
  validator.** Keep the existing private envelope and diagnostics behavior.
- [ ] **Step 4: Implement the deidentification/card gate before the single
  provider call.** No live call. The gate returns fixed content-free fallback
  codes only.
- [ ] **Step 5: Update time budgets and persistent disclosure.** Disclosure must
  state that a configured remote provider receives locally deidentified current
  visible content and must not claim local-only or zero-retention.
- [ ] **Step 6: Run focused tests and the existing 50-case offline evaluator.**
- [ ] **Step 7: Commit.**
  `git commit -m "feat: gate DeepSeek with private deidentification"`

---

### Task 6: Implement aggregate-only private DeepSeek evaluation

**Files:**
- Create: `backend/private_evaluation/__init__.py`
- Create: `backend/private_evaluation/schema.py`
- Create: `backend/private_evaluation/repository.py`
- Create: `backend/private_evaluation/metrics.py`
- Create: `backend/private_evaluation/runner.py`
- Create: `scripts/evaluate_private_deepseek.py`
- Create: `docs/operations/private_deepseek_evaluation.md`
- Create: `tests/test_private_evaluation_schema.py`
- Create: `tests/test_private_evaluation_metrics.py`
- Create: `tests/test_private_evaluation_runner.py`
- Create: `tests/test_evaluate_private_deepseek.py`

**Interfaces:**
- Import accepts only locally deidentified, business-approved, privacy-approved
  encrypted cases. The repository cannot serialize raw prompt or model output.
- Runner stratifies to 200 by category, language, direction, and risk;
  evaluates 20 Flash gate cases first, then 180 Flash cases, then the approved
  40-case Flash/Pro pair set.
- No retry. Any gate schema, safety, or grounding violation, or gate p95 over 12
  seconds, stops before remaining calls.
- Aggregate report contains only counts, rates, latency aggregates, model names,
  fixed metric names, and fixed error codes.

- [ ] **Step 1: Write offline fake-client tests first.** Cover exact case counts,
  deterministic strata, gate stop, no retry, no remaining calls after gate
  failure, pair selection, aggregate-only serialization, and no raw input,
  prompt, output, path, vault ID, or identifier leakage.
- [ ] **Step 2: Add threshold tests.** Require schema 100%, unsafe action and
  unsupported critical facts zero, mandatory-risk retention >=95%, category
  macro-F1 >=0.85, required-action recall >=0.90, human usefulness >=90%,
  fallback <=10%, and p95 <=12 seconds. Pro switch requires >=5 percentage
  points quality improvement, no safety regression, and p95 <=12.
- [ ] **Step 3: Run focused tests and record RED.**
- [ ] **Step 4: Implement encrypted evaluation repository, metrics, runner, and
  CLI with injected clients for tests.** Live execution requires explicit
  operator confirmation and backend key configuration; tests cannot use network.
- [ ] **Step 5: Run focused GREEN and commit.**
  `git commit -m "feat: add private DeepSeek evaluation gates"`

---

### Task 7: Close documentation, leakage guards, status, and full verification

**Files:**
- Modify: `docs/operations/testing_checklist.md`
- Modify: `docs/operations/review_checklist.md`
- Modify: `docs/operations/deployment_notes.md`
- Modify: `docs/operations/project_structure.md`
- Modify: `scripts/maintenance_scan.py`
- Create or modify: leakage/static/mechanical tests under `tests/`
- Regenerate: `docs/operations/project_status_log.md`

**Interfaces:**
- Maintenance scan reports only content-free counts and fixed finding codes.
- Repository leakage scan checks Git-tracked files, logs, test outputs, public
  SQLite fixtures, and generated status for secrets, real identifiers, raw mail,
  attachment names, vault/recovery material, and real-derived prose.

- [ ] **Step 1: Add leakage and closeout tests first and record RED.** Include
  allowlisted synthetic domains and fixed fixtures only; never print matched
  sensitive text.
- [ ] **Step 2: Update operational docs and maintenance scan.** Document init,
  inventory, explicit scan confirmation, attachment approval, verify,
  purge/revoke, recovery rewrap, knowledge review, snapshot publication,
  evaluation gate, rollback, and incident stop conditions.
- [ ] **Step 3: Run focused tests to GREEN.**
- [ ] **Step 4: Regenerate project status.**
  `python -B scripts/generate_project_status.py --output docs/operations/project_status_log.md`
- [ ] **Step 5: Run all required verification with provider disabled.**
  - `python -B -m unittest discover -s tests`
  - JavaScript syntax checks for every changed `.js` file
  - architecture, static, mechanical, dependency, documentation, and leakage
    guards
  - existing 50-case synthetic DeepSeek evaluator
  - `git diff --check`
  - `python -B scripts/maintenance_scan.py`
- [ ] **Step 6: Run final whole-branch specification and code-quality review.**
  Resolve only in-scope blockers; defer newly invented natural-language edge
  cases after one fix/re-review cycle.
- [ ] **Step 7: Commit closeout.**
  `git commit -m "docs: complete private mailbox analysis rollout"`

## Rollback

1. Set `EMAIL_AGENT_LLM_PROVIDER=disabled` and restart the backend.
2. Remove or disable access to the project-external runtime knowledge snapshot;
   the analyzer returns to generic rule output.
3. Do not run the administrator CLI. It has no scheduled or runtime hook.
4. Revoke a vault by deleting its DPAPI and recovery envelopes only after an
   explicit operator confirmation; retain no claim that lost encrypted data can
   be recovered without an intact offline recovery key.
5. Revert the task commits in reverse order if the code must be removed. Never
   modify mailbox data as part of rollback.

## Live-Operation Boundary

Implementation completion does not itself authorize a mailbox connection or a
DeepSeek call. After offline verification, the operator must separately run the
CLI, enter the mailbox app password interactively, confirm the content-free
inventory fingerprint, and provide any remote API key only in the backend
environment. Codex must not receive raw vault data or recovery material.
