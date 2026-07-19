# Task 2 Implementation Report

Status: DONE
Date: 2026-07-16
Worktree: `C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.worktrees\multimodal-plan-c`
Branch: `codex/multimodal-plan-c`

## Summary

Task 2 now reads the current visible Tencent Exmail message automatically from
the verified top document or exactly one unique visible, accessible,
same-origin Tencent `mainFrame`.

- The resolver requires prioritized subject evidence, a disjoint verified
  From/To header, and one owned visible current-body root.
- The collector returns the verified current body plus reliable
  oldest-to-newest history. Ambiguous, authored, or unowned history collapses
  to current-body-only.
- Reliable thread-only aggregate roots require full normalized text ownership;
  an authored nested history block cannot turn an ordinary body into an
  aggregate.
- Verified header metadata is authoritative over body, history, navigation, or
  background lookalikes.
- The context token binds document, frame, subject, header, current-body,
  location, and evidence text. Collection output is discarded if revalidation
  detects any identity or text change.
- Current-body extraction now walks browser-like child nodes, retains ordinary
  visible descendant text, and excludes nested authored body/history
  containers before the adapter or collector can consume them.
- Frame and message evidence must have a positive rendered rectangle,
  intersect the viewport, and have nonzero inline and computed opacity.
  Semantic `BR` nodes retain line breaks when their style/ancestor path is
  visible even when the browser reports a legitimate zero-width rectangle.
- Read-view evidence no longer accepts generic headings, generic subject
  attributes, or arbitrary descendants containing From/To text.
- Frame traversal is not recursive. No `all_frames`, host-permission expansion,
  mailbox traversal, navigation, Task 3 resource classification, or live access
  was added.

## Files changed in commit

Implementation and manifest:

- `frontend/browser_extension/content/exmail_visible_context.js`
- `frontend/browser_extension/content/current_message_collector.js`
- `frontend/browser_extension/content/exmail_adapter.js`
- `frontend/browser_extension/manifest.json`

Tests:

- `tests/test_browser_extension_manifest.py`
- `tests/test_browser_extension_behavior.py`
- `tests/test_browser_extension_tencent_legacy_context.py`
- `tests/test_browser_extension_task6_adapter.py`
- `tests/test_browser_extension_current_message_collector.py`
- `tests/test_browser_extension_static.py`
- `tests/test_browser_extension_task6_contracts.py`

Task records:

- `.superpowers/sdd/progress.md`
- `.superpowers/sdd/task-2-brief.md`
- `docs/superpowers/plans/2026-07-16-multimodal-current-email-analysis.md`

## TDD and verification evidence

All successful Python verification used the pinned Python 3.12.13 runtime with
the root project's locked site packages:

```powershell
$env:PYTHONPATH='C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages'
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ...
```

### Baseline

The original six-module browser-extension focus passed before Task 2 tests:

```text
Ran 86 tests in 2.441s
OK
```

### Initial focused RED

Command:

```powershell
python -m unittest tests.test_browser_extension_manifest tests.test_browser_extension_behavior tests.test_browser_extension_tencent_legacy_context tests.test_browser_extension_task6_adapter tests.test_browser_extension_current_message_collector tests.test_browser_extension_static
```

Result after tests and before production implementation:

```text
Ran 96 tests in 2.861s
FAILED (failures=10)
```

The intended failures covered the missing resolver and manifest entry, legacy
`mainFrame` body/history extraction, missing-header and duplicate-body gates,
duplicate visible frames, stale navigation discard, and preservation of a
verified current body when history is ambiguous.

### Review-derived RED and fixes

Fresh review produced additional targeted RED evidence before each fix:

- Five-case ownership set: `Ran 5 tests`, `FAILED (failures=5)` for a non-`qm`
  body overwritten by sibling history, authored header/history markup, and the
  structured sibling visibility boundary.
- Three-case trust set: `Ran 3 tests`, `FAILED (failures=3)` for unverified page
  metadata, an authored heading that blocked the host subject, and a nested
  authored body that replaced the outer verified body.
- Document-level background history: `Ran 1 test`, `FAILED (failures=1)`.
- Exact non-`qm` nested-history aggregate spoof: `Ran 1 test`,
  `FAILED (failures=1)`.

The final targeted ownership/aggregate groups passed, and the independent
reviewer refreshed after every fix.

The final hardening review identified three additional Important boundaries.
The exact six-case reviewer set was preserved RED before production changes:

```text
Ran 6 tests in 0.297s
FAILED (failures=6)
```

Those cases proved that the previous fixed-text fake DOM masked descendant
aggregation, that zero-area/offscreen/transparent frames were treated as
visible, and that a generic heading/header/body triad could satisfy the
resolver. After the bounded fixes, the exact same set passed:

```text
Ran 6 tests in 0.267s
OK
```

The full Tencent legacy-context module then passed 29 tests. A broader run
exposed two older fake DOMs without geometry/viewport support; their fixtures
were upgraded with deterministic browser-like rectangles, viewport dimensions,
and opacity. One resource-boundary fixture was also moved under a valid Tencent
read envelope so it no longer contradicted the forged-triad rejection rule.

A second review found that the full positive-area gate ran before the semantic
`BR` branch, so browser-realistic `Hello<br>World` content with a zero-width
rendered `BR` collapsed to `HelloWorld`. The three-case focused test preserved
the exact RED while proving hidden controls were already safe:

```text
Ran 3 tests in 0.152s
FAILED (failures=1)
```

The resolver now separates style/ancestor reachability from rectangle
intersection. Only semantic `BR` uses the former; frame, body, subject, header,
and ordinary descendant candidates retain the full positive-area gate. The
same focused set then passed:

```text
Ran 3 tests in 0.140s
OK
```

### Final extension GREEN

The expanded seven-module extension command added the stale manifest-contract
module and passed:

The original implementation surface passed 112 tests. After the first five
review regressions and realistic fixture upgrades, the same seven-module
surface passed 117 tests. With the three semantic line-break cases, it passed:

```text
Ran 120 tests in 4.103s
OK
```

### Full-suite evidence

An initial full-suite attempt used a nonexistent worktree-local `.venv` path.
It produced dependency import errors for `openai` and `bs4` and also revealed
one genuine stale manifest assertion. The assertion was updated to require the
new resolver-before-collector-before-adapter load order while retaining the
same bounded permissions.

The first full run with the correct locked dependency path reached 1,191 tests
and had one unrelated local server socket abort in the `INVALID_HOST` subcase.
That exact server test immediately passed in isolation:

```text
Ran 1 test in 0.510s
OK
```

Final full suite after the semantic line-break correction:

```text
Ran 1209 tests in 81.529s
OK (skipped=1)
```

### JavaScript, manifest, and diff checks

- `node --check frontend/browser_extension/content/exmail_visible_context.js`
  -> exit 0.
- `node --check frontend/browser_extension/content/current_message_collector.js`
  -> exit 0.
- `node --check frontend/browser_extension/content/exmail_adapter.js`
  -> exit 0.
- Manifest JSON parsing -> exit 0.
- `git diff --check` and `git diff --cached --check` -> exit 0; only expected
  LF/CRLF conversion warnings were printed.

## Commit

- Original subject: `fix: read visible Tencent message context`
- Original hash: `476a57a6b81f6bc127ed7ec19c7843c6eb979f9c`
- Hardening subject: `fix: harden Tencent visible context`
- Hardening hash: `32904cc3729890271f1db84182e93b75b204dffa`
- Semantic line-break subject: `fix: preserve visible email line breaks`
- This report is included in the semantic line-break commit; its immutable hash
  is recorded by the outer handoff after commit creation.

## Concerns and boundaries

- No unresolved Task 2 production or test concern remains after the requested
  hardening pass.
- The two untracked Task 1 review-package files and both untracked Task 2 review
  packages were not staged, edited, or committed.
- Project-status generation and maintenance/release scans remain deferred to
  the plan's later integration/release-gate task.
- Task 3 was not started. No browser, mailbox, real email, image, attachment,
  provider, key, `.env`, or live API was accessed.

DONE
