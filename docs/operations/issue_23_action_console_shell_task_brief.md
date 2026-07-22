---
last_update: 2026-07-22
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 23 Action Console shell task brief

## 1. Task name

```text
establish the formal Action Console shell
```

## 2. Task type

```text
feature | docs | test
```

## 3. Current status

```text
implemented
```

## 4. Goal

Implement GitHub issue #23 as an additive UI-only change. Give the formal
browser side panel and local debug result surface the validated Variant A
Action Console shell, with relaxed readable density and the approved scrolling
behavior, while preserving the existing Analyze and copy-only draft flows.

## 5. Non-goals

- Do not replace, reorder, close, or modify any item in the original development plan.
- Do not implement issues #24 through #27: decision hero semantics, action queue,
  draft redesign, or evidence-layer redesign.
- Do not promote prototype variants, synthetic mailbox chrome, the floating
  switcher, prototype state simulation, or prototype code into production.
- Do not change result semantics, shared field bindings, backend code, API,
  schema, prompt, provider routing, extension permissions, persistence, or the
  explicit Analyze click boundary.
- Do not access a live mailbox or provider and do not add automatic send,
  delete, archive, move, forward, reply, navigation, or scanning behavior.

## 6. Background and sources

Issue #23 is one of five approved additive UI tickets. Its design reference is
the validated `prototype/current-email-ui-preview@3e02b3d`, Variant A, but the
formal implementation is rewritten from the production baseline `d7c2371`.

Relevant sources:

- `AGENTS.md`
- GitHub issue #23
- `docs/product/feature_scope.md`
- `docs/api/frontend_backend_flow.md`
- `docs/decisions/0007-multimodal-current-email-analysis.md`
- `docs/operations/browser_extension_side_panel_task_brief.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`

## 7. Scope

Expected additions or changes:

- `frontend/browser_extension/popup.html`
- `frontend/browser_extension/popup.css`
- `frontend/local_debug_page/index.html`
- `frontend/local_debug_page/styles.css`
- `frontend/browser_extension/shared/analysis_components.css`
- focused frontend tests under `tests/`
- this task brief and the generated project status log

Existing JavaScript bindings should remain unchanged unless a test proves that
an outer-shell-only markup adjustment requires a matching public field lookup.

## 8. Technical approach

1. Add behavior-focused RED tests for the shared public shell, preserved control
   order and bindings, and the two approved scroll ownership modes.
2. Add only semantic outer-shell wrappers and CSS hooks needed by both formal
   surfaces. Preserve all existing result field IDs and the shared renderer.
3. Apply the approved warm neutral background, dark teal hierarchy, restrained
   mint action color, calm card treatment, and relaxed spacing without changing
   what any result means or introducing later-ticket components.
4. Keep the extension on one natural document scrollbar. Permit only the wide
   local debug result column to scroll internally, and restore document scrolling
   at the narrow breakpoint.

## 9. Data structure and interface changes

### Database

None.

### Public API

None.

### AI output JSON

None.

### Prompt

None.

## 10. Security and privacy checks

- [x] No live mailbox, real message, provider, credential, cookie, token, or key is read.
- [x] No email is sent, deleted, archived, moved, forwarded, or replied to.
- [x] The frontend continues to call only the existing loopback backend after Analyze.
- [x] The exact persistent remote-processing disclosure remains visible and before Analyze.
- [x] Email and attachment text remains untrusted display content.
- [x] Tests and visual verification use synthetic content only.
- [x] No browser storage, new permission, dependency, or persistence surface is added.

## 11. Prompt-injection protection

Displayed email and analysis text remains inert untrusted text. This UI-only task
does not execute content, create links from URL-shaped text, change the prompt,
or expose system instructions, keys, database content, or other messages.

## 12. Acceptance criteria

1. Both formal frontend surfaces use the approved spacing rhythm, card treatment,
   color hierarchy, and readable density without changing analysis semantics.
2. The exact persistent disclosure stays visible, uncollapsed, and before Analyze.
3. Analyze, status, all existing result fields, five closed native details, and
   the copy-only draft remain reachable with their existing bindings.
4. Long text wraps without horizontal scrolling; interactive controls remain at
   least 44px with a visible keyboard focus indicator.
5. The browser side panel has one natural document scroll owner; wide local debug
   may scroll its result column; narrow local debug uses document scrolling.
6. No backend, contract, provider, permission, persistence, or click-boundary change occurs.
7. Verification remains synthetic and offline and includes focused checks, full
   regression, generated project status, and maintenance scanning.

## 13. Test plan

- Run focused frontend tests before editing to record the baseline.
- Add and observe one failing public shell/structure test before its implementation.
- Add and observe one failing local-debug scroll ownership test before its implementation.
- Run the affected static and behavior suites after each vertical slice.
- Run Node syntax checks for the existing frontend scripts.
- Generate `docs/operations/project_status_log.md`, then run
  `python -m unittest discover -s tests` once as the final full regression.
- Run `python -B scripts/maintenance_scan.py` and the repository leakage scan.
- Do not call a live provider, mailbox, vault, DPAPI, BitLocker, or remote endpoint.

## 14. Rollback

Revert the issue #23 commit. There is no data migration, API migration, provider
configuration, extension permission, or persistent browser state to roll back.

## 15. Human confirmation needed

None. The user explicitly authorized implementation, and issue #23 fixes the
public seams and exclusions. Issues #24 through #27 remain separate approvals and
implementation work.

## 16. Pre-execution checklist

- [x] Read `AGENTS.md`, project status, core constraints, and documentation rules.
- [x] Read issue #23 and the relevant product, API, side-panel, and ADR documents.
- [x] Confirmed the formal base is `d7c2371`, not the prototype branch.
- [x] Confirmed the TDD seams: public DOM/accessibility structure, existing shared
  renderer bindings, and public responsive scroll ownership.
- [x] Confirmed no live mailbox, provider, identifying fixture, or new dependency is needed.
- [x] Preserved the unrelated untracked `frontend/browser_extension.crx` in the main worktree.

## 17. Remote provider private-context checklist

- [x] Providers remain disabled by default; routes, models, retries, and budgets are unchanged.
- [x] The exact approved persistent pre-click disclosure remains unchanged.
- [x] Public API, SQLite, renderer fields, diagnostics, prompts, and runtime knowledge are unchanged.
- [x] Frontend POST wait remains 60 seconds and visible-resource collection remains 20 seconds.
- [x] Verification is offline and uses no mailbox, vault, DPAPI, BitLocker, or provider.

## 18. Administrator stage-evaluation checklist

Not applicable. This task does not change stage evaluation.

## 19. Final dataset build and interactive judge checklist

Not applicable. This task does not change private evaluation.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable. This task does not change incremental sync or current-click evidence.

## 21. Post-execution record

Actual files changed:

- `frontend/browser_extension/popup.html`
- `frontend/browser_extension/popup.css`
- `frontend/browser_extension/shared/analysis_components.css`
- `frontend/local_debug_page/index.html`
- `frontend/local_debug_page/styles.css`
- `tests/test_action_console_shell.py`
- this task brief and the generated project status log

Verification record:

- The two public shell and scrolling seams were implemented through observed
  RED -> GREEN tests.
- The focused 86-test frontend regression, frontend Node syntax checks, and
  offline wide/narrow visual inspection passed before final project verification.
- The final full regression, maintenance scan, and leakage scan run after project
  status generation and are reported in the implementation handoff.

Unfinished within issue #23:

- None. Issues #24 through #27 remain intentionally untouched and continue as
  separate additive tickets under the unchanged original plan.
