---
last_update: 2026-07-11
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: implementation_plan
---

# Final Re-review Blockers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This task must remain with the current single fix agent; do not dispatch subagents.

**Goal:** Close the five blocking findings in `.superpowers/sdd/final-rereview.md` without weakening current-message, privacy, timeout, or fallback boundaries.

**Architecture:** Keep the browser acquisition layer fail-closed, but replace extension-only trust markers with strict Tencent Exmail structural allowlists. Carry reason codes through the frontend/backend limitation boundary, expand the deterministic insight capacity to the provable maximum, extract only constructed PII-safe attachment facts, and enforce loopback-only Ollama endpoints before request construction.

**Tech Stack:** Browser-extension JavaScript, Python 3.12 standard library, `unittest`, SQLite, existing PDF/DOCX/XLSX/OCR test doubles.

## Global Constraints

- No real Tencent Exmail account, message, attachment, authenticated download, or smoke validation.
- No automatic send, delete, archive, move, forward, or reply.
- Strict RED before production changes for every blocker; append exact evidence to `.superpowers/sdd/final-fix-report.md`.
- Limitation objects contain only allowlisted `code`, `filename`, `type`, `size`, and canonical `limitation` fields.
- Five accepted files, maximum frontend limitations including aggregate omission, and one backend operational limitation must remain representable end to end.
- Each blocker ends with focused verification and one Conventional Commit.

---

### Task 1: Immediate timeout rejection

**Files:**
- Modify: `tests/test_browser_extension_current_message_collector.py`
- Modify: `frontend/browser_extension/content/current_message_collector.js`

**Interfaces:**
- Consumes: `collectVisibleResources(doc, options)` and the existing per-resource deadline.
- Produces: deadline limitation with immediate promise settlement even when `reader.read()` and `reader.cancel()` never settle.

- [ ] Add a Node behavior case whose `read()` and `cancel()` return never-settling promises and race collection against a short external watchdog.
- [ ] Run the exact test and record the expected watchdog failure.
- [ ] Make timeout callbacks synchronous: call `AbortController.abort()` and fire-and-forget cancellation; never await cleanup in the deadline catch path.
- [ ] Run collector, popup re-enable, and JavaScript syntax tests.
- [ ] Commit with `fix: reject resource timeouts immediately`.

### Task 2: Loopback-only Ollama

**Files:**
- Modify: `tests/test_llm_client.py`
- Modify: `backend/email_agent/llm_client.py`
- Modify: `docs/superpowers/specs/2026-07-09-phase-two-attachment-thread-analysis-design.md`
- Modify: `docs/operations/deployment_notes.md`
- Modify: `docs/constraints/tooling_constraints.md`

**Interfaces:**
- Consumes: `AppConfig.ollama_base_url`.
- Produces: `_ollama_endpoint(base_url: str) -> str` only for `localhost` or `ipaddress.ip_address(host).is_loopback` with no userinfo.

- [ ] Add table-driven tests for accepted `localhost`, `127.0.0.1`, another `127/8` address, and `[::1]`, plus rejected remote IPv4, remote IPv6, DNS host, and userinfo URLs.
- [ ] Run the rejection test and record that a remote URL reaches request construction/network mocking.
- [ ] Validate the parsed hostname with `ipaddress`; keep all rejection inside the existing sanitized `LlmClientError` boundary.
- [ ] Update active docs to state loopback-only and run config/LLM/docs guards.
- [ ] Commit with `fix: restrict Ollama to loopback`.

### Task 3: Production-shaped Exmail resource trust

**Files:**
- Modify: `tests/test_browser_extension_task6_adapter.py`
- Modify: `tests/test_browser_extension_current_message_collector.py`
- Modify: `frontend/browser_extension/content/exmail_adapter.js`
- Modify: `frontend/browser_extension/content/current_message_collector.js`

**Interfaces:**
- Consumes: the verified visible subject/header/body extraction and strict Exmail attachment endpoint validation.
- Produces: `{currentMessageContainer, verifiedResourceCandidates}` from allowlisted host container/control classes outside the body.

- [ ] Replace the adapter fixture's extension attributes with a sanitized read-message structure using allowlisted Exmail-style read container, attachment list, and attachment item classes; include a forged body download link.
- [ ] Run the focused adapter case and record that no production-shaped control is collected.
- [ ] Find the allowlisted read-message ancestor containing the verified body and visible subject/header relationship; search only allowlisted attachment/inline containers outside the body; return no context on ambiguity or absence.
- [ ] Make collector host-control validation use the same strict structural/control allowlist rather than extension marker attributes.
- [ ] Run adapter/collector/manifest/static tests and commit with `fix: map Exmail resource controls structurally`.

### Task 4: Lossless reason-coded limitation capacity

**Files:**
- Modify: `frontend/browser_extension/content/current_message_collector.js`
- Modify: `frontend/browser_extension/content/exmail_adapter.js`
- Modify: `frontend/browser_extension/shared/api_client.js`
- Modify: `backend/email_agent/api.py`
- Modify: `backend/email_agent/resource_limitations.py`
- Modify: `backend/email_agent/analysis_projection.py`
- Modify: `backend/email_agent/analyzer.py`
- Modify: `tests/test_resource_limitation_vertical_contract.py`
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_api.py`
- Modify: `docs/api/backend_api_contract.md`
- Modify: `docs/data/analysis_result_schema.md`

**Interfaces:**
- Produces limitation codes `unsupported_type`, `frontend_limit`, `resource_unavailable`, `resource_read_failed`, `collection_timeout`, `candidate_omission`, and `operational_failure`.
- Produces deterministic code-to-type/status mapping and a maximum of five parsed plus eight frontend limitation insights plus one operational insight.

- [ ] Add a vertical maximum-cardinality test with five parsed files, eight frontend limitations including aggregate omission, and a forced backend operational failure; assert every expected code-derived outcome reaches analyzer output, SQLite, and renderer.
- [ ] Run it and record truncation plus text-inferred status failures.
- [ ] Add `code` to every JS/Python projection; canonicalize by code only; reserve the frontend aggregate slot and append/prioritize backend operational failure without truncating it.
- [ ] Raise deterministic attachment insight capacity to fourteen and keep exact schema-safe insight fields.
- [ ] Run vertical/API/analyzer/database/renderer tests and commit with `fix: preserve limitation reasons at capacity`.

### Task 5: Useful PII-safe attachment facts

**Files:**
- Create: `backend/email_agent/attachment_facts.py`
- Modify: `backend/email_agent/attachment_parser.py`
- Modify: `backend/email_agent/attachment_text.py`
- Modify: `tests/test_attachment_parser.py`
- Modify: `docs/data/analysis_result_schema.md`

**Interfaces:**
- Produces: `extract_attachment_facts(text: str, metadata_facts: list[str] | None) -> list[str]` with at most five constructed facts.
- Consumes: raw bounded parser text before generic long-number redaction; every returned value passes display sanitization.

- [ ] Add PDF, DOCX paragraph/table, XLSX, and OCR canaries for labeled seven-digit RFQ/PO/order/invoice/tracking values, quantity/measurement, amount/cost/currency, explicit due facts, sanitized requested actions, and quality signals; include email/phone/card/path/URL/raw-prose canaries.
- [ ] Assert useful facts exist in result/prompt/SQLite while every private canary remains absent; run and record missing evidence.
- [ ] Extract labeled identifiers before generic numeric redaction, construct facts from allowlisted patterns/table header-value pairs, and sanitize bounded requested-action clauses.
- [ ] Keep fixed generic summaries and never return arbitrary first lines or contiguous prefixes.
- [ ] Run parser/analyzer/database/schema guards and commit with `fix: restore safe attachment facts`.

### Task 6: Final verification and report

**Files:**
- Modify if generated content changes: `docs/operations/project_status_log.md`
- Append: `.superpowers/sdd/final-fix-report.md`

- [ ] Regenerate the project status log.
- [ ] Run `python -m unittest discover -s tests`.
- [ ] Run `python -B scripts/maintenance_scan.py --fail-on-high`.
- [ ] Run manifest, front-matter/static, architecture, mechanical, status-generator, and maintenance-scan guards.
- [ ] Run `node --check` for every frontend JavaScript file.
- [ ] Run `git diff --check` and require an empty `git status --short`.
- [ ] Record the pending real Tencent Exmail smoke explicitly as not performed and retain only the nonblocking debt named in the re-review.
