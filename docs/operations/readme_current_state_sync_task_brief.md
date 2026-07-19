---
last_update: 2026-07-19
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# README Current-State Sync Task Brief

## Task

Synchronize the root README with the already implemented and documented
multimodal current-email release state.

## Type and status

- Type: `docs`
- Status: `completed`

## Goal

Correct stale public onboarding facts without changing runtime behavior. The README
must identify extension `0.2.3`, document the disabled-by-default OpenAI/DeepSeek
route controls, and distinguish the completed bounded current-click smokes from the
still-pending automatic attachment smoke.

## Non-goals

- No production, frontend, backend, prompt, schema, or environment-default changes.
- No new live provider, mailbox, attachment, or vault operation.
- No disclosure of real email content, credentials, paths, or API keys.
- No modification of the operator's existing deployment-notes work.

## Evidence

- `frontend/browser_extension/manifest.json` is version `0.2.3`.
- `.env.example` defines the fixed OpenAI multimodal route, optional DeepSeek text
  fallback, direct DeepSeek route, and disabled defaults.
- `docs/operations/project_status_log.md` records completed Task 9 bounded smokes
  and the separately gated pending Task 5 attachment smoke.
- `docs/decisions/0007-multimodal-current-email-analysis.md` is the authoritative
  provider, privacy, budget, and rollback decision.

## Scope

- `README.md`
- `tests/test_multimodal_documentation_contracts.py`
- `docs/operations/readme_current_state_sync_task_brief.md`
- generated `docs/operations/project_status_log.md`

## Approach

1. Add a documentation-contract regression test before editing the README.
2. Update only stale README statements and preserve the click-only mailbox boundary.
3. Run focused documentation tests, the full suite, status generation, maintenance,
   leakage, and diff checks.

## Interfaces and data

- Database: none.
- API: none.
- AI JSON: none.
- Prompt: none.
- Configuration behavior: none; README only mirrors `.env.example`.

## Security and privacy

- [x] Providers remain disabled by default.
- [x] API keys remain backend-only.
- [x] Current-message analysis remains click-only.
- [x] No mailbox scan, send, delete, move, or archive behavior is added.
- [x] No real mailbox, attachment, provider, vault, DPAPI, or private dataset is used.
- [x] Pending live attachment validation still requires fresh explicit authorization.
- [x] The approved persistent disclosure covers current visible text, selected
  images, and files, including residual identification and retention limitations.

## Acceptance

1. README and manifest both state extension `0.2.3`.
2. README lists the current OpenAI, DeepSeek fallback, and direct DeepSeek controls.
3. README states that all providers are disabled by default.
4. README distinguishes completed Task 9 smokes from pending Task 5 attachment smoke.
5. README no longer contains the stale `0.2.2` or never-ran-current-click statements.
6. README preserves the exact approved remote-provider disclosure.
7. README states that an eligible OpenAI failure may attempt one configured
   DeepSeek text fallback before deterministic rules, subject to the shared budget.
8. Documentation contracts, full tests, maintenance, leakage, and diff checks pass.

## Test plan

- Focused RED/GREEN documentation-contract test.
- `python -B -m unittest tests.test_multimodal_documentation_contracts`
- `python -B -m unittest discover -s tests`
- `python -B scripts/generate_project_status.py --output docs/operations/project_status_log.md`
- `python -B scripts/maintenance_scan.py --fail-on-high`
- `git diff --check`

## Rollback

Revert the documentation-only commit. No runtime or data rollback is required.

## Human confirmation

The operator approved the README update after reviewing the identified stale facts.

## Pre-execution checklist

- [x] Read `AGENTS.md`, current status, README, manifest, `.env.example`, and ADR 0007.
- [x] Confirmed the exact factual corrections and non-goals.
- [x] Confirmed the isolated worktree and synthetic/offline verification boundary.

## Post-execution record

- Added a contract test that derives the extension version from `manifest.json`
  and provider defaults from `.env.example` instead of duplicating them silently.
- Preserved the exact approved remote-processing disclosure and documented the
  eligible OpenAI-to-DeepSeek-to-rules fallback order.
- Focused documentation/configuration suite: 48 tests passed.
- Full suite: 1460 tests passed with 1 expected skip.
- Leakage/status/maintenance tests: 41 passed.
- Architecture/static/mechanical constraints: 59 passed.
- Maintenance scan: no findings; `git diff --check`: passed.
- Independent security and factual-accuracy review findings were incorporated;
  both final re-reviews passed with no blocker or important finding.
