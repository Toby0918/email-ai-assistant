# Task 5 Implementation Report

Status: ROOT REVIEW FIXES DONE - RE-REVIEW PENDING
Date: 2026-07-16
Worktree: `C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.worktrees\multimodal-plan-c`
Branch: `codex/multimodal-plan-c`

## Summary

Task 5 adds a provider-neutral request carrier and one-call OpenAI Responses
multimodal client while preserving the existing DeepSeek text-only contract.

- `ModelAnalysisRequest` contains only locally deidentified text and Task 4
  `PreparedMediaAsset` objects. It is frozen, slot-backed, and excluded from
  repr output.
- OpenAI receives one user message beginning with `input_text`. Every binary
  item is immediately preceded by an opaque `UNTRUSTED_BINARY_SOURCE
  attachment:N` marker. Images use high-detail data URLs; PDFs use high-detail
  `input_file` entries with opaque provider filenames.
- The client fixes the model to `gpt-5.6-sol` and the endpoint to
  `https://api.openai.com/v1`, including when `OPENAI_BASE_URL` is present in
  the process environment. It disables retries, storage, streaming, and tools,
  caps output at 2,400 tokens, uses JSON-object output with low verbosity and
  bounded reasoning, and enforces a maximum 35-second call budget.
- Only completed, non-empty `response.output_text` is accepted. Timeout,
  provider, incomplete, empty, and private-output failures use fixed
  `LlmClientError.reason_code` values without provider exception details.
- The privacy preflight constructs the multimodal request only after text
  deidentification succeeds. Accepted model output crosses the existing
  private-output gate before it can return.
- Dispatch independently revalidates a fixed 512 KiB nonblank text bound,
  placeholder/residual privacy safety, exact media types and byte limits,
  aggregate/count limits, and duplicate object/provider-filename rejection.
  Repeated source IDs remain valid for distinct assets.
- Unsupported ambient OpenAI organization, project, custom-header, and admin
  key configuration fails closed before client construction. A configured
  API key must be an exact nonblank string.
- Raw media is copied only into temporary mutable snapshots, encoded before
  client construction, and wiped in `finally`; later source-buffer mutation
  cannot alter the provider payload.
- DeepSeek still receives its exact existing Chat Completions request and only
  the request's text field. The OpenAI client never uses the Files API.

## Files in scope

Implementation:

- `backend/email_agent/model_request.py`
- `backend/email_agent/openai_multimodal_client.py`
- `backend/email_agent/llm_client.py`
- `backend/email_agent/prompt_context.py`
- `backend/email_agent/private_context_gate.py`

Tests:

- `tests/test_openai_multimodal_client.py`
- `tests/test_llm_client.py`
- `tests/test_prompt_context.py`
- `tests/test_private_context_gate.py`

Task records:

- `.superpowers/sdd/task-5-brief.md`
- `.superpowers/sdd/task-5-report.md`
- `.superpowers/sdd/progress.md`

## TDD evidence

All successful Python runs used the pinned Python 3.12.13 runtime with the
repository `.venv` and Python 3.12 site packages on `PYTHONPATH`.

- Initial focused RED ran 23 tests and produced five expected import/interface
  errors for the missing request module, OpenAI client, prompt constant, and
  prepared-media privacy-gate seam.
- The first focused GREEN passed 69 tests.
- A dedicated fixed-endpoint RED failed because the endpoint constant and
  explicit constructor argument were absent. It passed after the client fixed
  the official endpoint independently of ambient `OPENAI_BASE_URL`.
- A private-output-gate RED exposed an unexpected gate exception. It passed
  after the client converted it to the fixed `provider_output_invalid` code
  while suppressing raw exception detail.
- The pre-review focused client/prompt/privacy matrix passed:

```text
Ran 74 tests in 0.741s
OK
```

### Mechanical and full-suite evidence

The first mechanical run correctly found two modules over 300 lines and one
function over 50 lines. A pure helper/layout refactor closed those findings;
the final files are at or below the repository limits. The static,
architecture, and mechanical matrix passed 56 tests.

The correct-environment full suite passed before this final records-only
update:

```text
Ran 1303 tests in 95.756s
OK (skipped=1)
```

### Root fresh-review fix closure

Fresh review of `67744bf1faa4c8abf3c9693daa56dff61f055c72` found
three dispatch-boundary gaps: blank/unbounded or directly wrapped private
text, mutable media revalidation/snapshot timing, and ambient SDK configuration
inherited by the pinned client.

- The first exact RED ran 17 OpenAI-client tests and produced 23 expected
  failures across blank/cap/private-text probes, eight post-construction media
  probes, both late-buffer mutations, and four ambient SDK variables. The
  legitimate repeated-source-ID case remained green.
- The first two refinement RED tests produced four expected failures for a
  whitespace key, two non-string keys, and the immutable raw snapshot. An
  exact string-subclass extension then reproduced all four invalid key cases,
  including the newly added subclass probe, before the exact-type fix.
- The architecture gate failed once when the scanner was imported outside its
  exact allowlisted bridge. Dispatch privacy validation now reuses
  `private_context_gate`, preserving the architecture contract.
- One final RED reproduced a raw encoding exception escaping before client
  construction. It now maps to fixed `invalid_request` while the temporary raw
  snapshot is wiped and the exception detail is suppressed.

Final verification after all production changes:

```text
Ran 85 tests in 0.794s
OK

Ran 56 tests in 3.155s
OK

Ran 1315 tests in 90.634s
OK (skipped=1)
```

`git diff --check` exited 0 with only the checkout's expected LF-to-CRLF
conversion warnings.

### Final fresh re-review metadata closure

Fresh re-review of `b8ecc6a58740369a4d004ad9226f3d8eb5be3070`
found that an exact `PreparedMediaAsset` could still hold `str` subclasses in
its five metadata fields. Task 4 value validation accepted their underlying
values, while custom formatting behavior could alter the later provider
marker or media payload.

- One exact dispatch RED produced 15 expected subtest failures: each of
  `source_id`, `provider_filename`, `mime_type`, `kind`, and `detail` accepted
  subclasses with custom `__format__`, `__str__`, or `__eq__` behavior and
  reached client construction.
- Dispatch now requires all five fields to have exact `str` type immediately
  before the existing Task 4 post-init revalidation and mutable snapshot.
- The existing positive case with two distinct assets sharing one plain
  `source_id` remains accepted.

Final seam verification:

```text
Ran 86 tests in 0.820s
OK

Ran 56 tests in 3.203s
OK

Ran 1316 tests in 90.956s
OK (skipped=1)
```

### Deleted-slot fixed-error closure

The final targeted review found that metadata attribute reads occurred just
outside the fixed-error `try`. Deleting one slot from an exact
`PreparedMediaAsset` could therefore expose a raw `AttributeError` before
client construction.

- One six-slot RED produced five raw errors for deleted `source_id`,
  `provider_filename`, `mime_type`, `kind`, and `detail`; the deleted `buffer`
  case already mapped to fixed `invalid_request` and served as the positive
  completeness control.
- The five metadata reads and exact-string validation now occur inside the
  existing fixed-error `try`, after the temporary wipe buffer is initialized.
- All six deleted-slot cases map to content-free `invalid_request`; all 15
  subclass probes still fail closed, and plain repeated source IDs remain
  accepted.

Final targeted closure verification:

```text
Ran 87 tests in 0.836s
OK

Ran 56 tests in 3.256s
OK

Ran 1317 tests in 89.181s
OK (skipped=1)
```

## Security and scope boundaries

- No original filename, filesystem path, private URL, cookie, token, provider
  exception detail, raw binary, or prepared Base64 is logged, persisted, or
  included in public repr output.
- No live provider, browser, mailbox, real email, real attachment, API key, or
  `.env` was accessed. Tests use only synthetic text/binary fixtures and an
  offline async fake whose Files API raises if touched.
- No public API response, SQLite schema, dependency pin, attachment sanitation
  policy, or DeepSeek request payload changed.
- Project-status generation and maintenance/release scans remain deferred to
  the later integration/release-gate task.
- Pre-existing untracked review-package files remain outside this commit.

## Review state

The final targeted root-review fix scope and verification are frozen for fresh
re-review.
Task 6 must not start until that gate closes.
