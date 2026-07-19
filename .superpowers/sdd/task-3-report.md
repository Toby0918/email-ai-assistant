# Task 3 Implementation Report

Status: DONE
Date: 2026-07-16
Worktree: `C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.worktrees\multimodal-plan-c`
Branch: `codex/multimodal-plan-c`

## Summary

Task 3 now collects only bounded, visible business media from the verified
Tencent Exmail current-message context established by Task 2.

- The new pure classifier returns only `visible_attachment`,
  `inline_business_image`, or `rejected`.
- Visible attachment links and large current-body business images are accepted;
  signatures, portraits, logos, icons, trackers, repeated images, known thread
  history, hidden/offscreen/zero-layout media, external URLs, sibling UI images,
  and ambiguous ownership are rejected locally.
- Accepted inline images use opaque names such as `inline-image-1.jpg` and only
  the existing `filename`, `type`, `size`, and `content_base64` fields.
- Resource URLs remain exact same-origin Tencent HTTPS download/viewfile
  endpoints with a non-empty query and no URL credentials.
- Discovery is iterative and shares the 20-second phase deadline. Fetches retain
  the 20-candidate, 5-download, 10 MiB per-resource, and 25 MiB total caps.
- Context and resource identity are revalidated before and after fetch;
  redirects and stale results are discarded.

## Files changed in commit

Implementation and manifest:

- `frontend/browser_extension/content/exmail_visible_resource_classifier.js`
- `frontend/browser_extension/content/current_message_collector.js`
- `frontend/browser_extension/content/exmail_adapter.js`
- `frontend/browser_extension/manifest.json`

Tests:

- `tests/test_browser_extension_visible_resource_classifier.py`
- `tests/test_browser_extension_current_message_collector.py`
- `tests/test_browser_extension_manifest.py`
- `tests/test_browser_extension_static.py`
- `tests/test_browser_extension_task6_adapter.py`
- `tests/test_browser_extension_task6_contracts.py`
- `tests/test_resource_limitation_vertical_contract.py`

Task records:

- `.superpowers/sdd/progress.md`
- `.superpowers/sdd/task-3-brief.md`
- `.superpowers/sdd/task-3-report.md`
- `docs/superpowers/plans/2026-07-16-multimodal-current-email-analysis.md`

## TDD and verification evidence

All successful Python verification used the pinned Python 3.12.13 runtime with
the root project's locked site packages:

```powershell
$env:PYTHONPATH='C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages'
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ...
```

### Initial RED and GREEN

- Pure classifier RED: 16 tests, all failed because the classifier module did
  not exist. The same 16 tests passed after the minimal classifier was added.
- Integration RED reproduced five missing boundaries: business-photo payload,
  stale context discard, changed resource identity, verified `mainFrame`
  collection, and manifest load order.
- The combined focused implementation surface passed 97 tests.
- A separate repeated-CID test failed when two differently signed URLs shared
  the same opaque content ID, then passed after the minimal identity fix.
- Before independent review hardening, all 154 browser-extension tests passed.

### Review-derived RED and fixes

Independent review found four Important gaps: production thread selectors,
arbitrary sibling avatars treated as attachments, missing rendered/viewport
visibility, and unbounded candidate discovery before the phase deadline.

The exact regression set proved all four findings before production changes:

```text
Ran 4 tests in 0.160s
FAILED (failures=4)
```

The same set passed after the bounded fixes:

```text
Ran 4 tests in 0.150s
OK
```

Final independent re-review closed all four Important findings and reported no
remaining Critical or Important issue: `CLEAN`.

### Root fresh-review follow-up

Root review of the committed Task 3 implementation found two further Important
boundaries:

- `findVerifiedResourceContext` recursively materialized all document
  descendants before candidate discovery enforced its shared deadline and
  200-node budget;
- any approved-endpoint sibling anchor could become an attachment, including a
  profile/avatar link with image metadata.

Both exact tests failed before production changes:

```text
Ran 1 test in 0.060s
FAILED (failures=1)

Ran 1 test in 0.054s
FAILED (failures=1)
```

The bounded fix now consumes the already revalidated Task 2 roots and begins
iterative candidate traversal directly from the verified container under one
deadline, node, depth, and candidate state. Attachment classification requires
positive `download` control evidence and rejects avatar/profile/logo/signature
hints in both adapter discovery and the pure classifier.

Fresh re-review then found one Important visited-set regression when the
fallback `currentBodyRoot` was the same element as `currentMessageRoot`. Its
exact test first failed with only the PDF fetched:

```text
Ran 1 test in 0.055s
FAILED (failures=1)
```

The excluded root now consumes shared node budget without entering `visited`,
so the inline traversal can inspect the same verified fallback body. The final
five-case set passed and fresh re-review reported no remaining Critical or
Important finding: `CLEAN`.

```text
Ran 5 tests in 0.256s
OK
```

### Final extension GREEN

```text
Ran 161 tests in 5.942s
OK
```

### Full-suite evidence

The first correct-environment full run reached 1,235 tests with one expected
skip and one stale synthetic vertical-contract failure. That fixture still used
the pre-Task-2 `topLevelDocument` option, did not load the new classifier, and
provided no rendered geometry or viewport, so the collector correctly returned
no files. The fixture was aligned with the verified context and visibility
contract; its exact test then passed:

```text
Ran 1 test in 4.840s
OK
```

The fresh full-suite run after the fixture settled passed:

```text
Ran 1235 tests in 82.709s
OK (skipped=1)
```

The post-root-review correct-environment full suite passed:

```text
Ran 1238 tests in 82.300s
OK (skipped=1)
```

### JavaScript, manifest, and diff checks

- `node --check frontend/browser_extension/content/current_message_collector.js`
  -> exit 0.
- `node --check frontend/browser_extension/content/exmail_adapter.js`
  -> exit 0.
- `node --check frontend/browser_extension/content/exmail_visible_resource_classifier.js`
  -> exit 0.
- Manifest JSON parsing -> exit 0.
- `git diff --check` -> exit 0; only expected LF/CRLF conversion warnings were
  printed.

## Commit

- Original: `187235c33c1e583e0985531fefc860c88f41b7d4`
  (`feat: collect visible business media safely`).
- Root-review hardening subject: `fix: bind visible resources to verified controls`.
- This report is included in the hardening commit; its immutable hash is
  recorded by the outer handoff after commit creation.

## Concerns and boundaries

- No unresolved Critical or Important Task 3 concern remains after fresh
  re-review.
- The untracked Task 1, Task 2, and root Task 3 review-package files were not
  staged, edited, or committed.
- Project-status generation and maintenance/release scans remain deferred to
  the plan's later integration/release-gate task.
- Task 4 was not started. No backend, provider, live browser, mailbox, real
  email, image, attachment, key, `.env`, or API was accessed.

DONE
