---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# DeepSeek Envelope Subdiagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the existing `envelope_invalid` rule fallback while adding one content-free, allowlisted detail that identifies the coarse private-envelope boundary rejected by the DeepSeek response.

**Architecture:** The private-envelope parser assigns one fixed detail to its existing generic exception. The analysis router carries that internal enum to the single terminal fallback point. The existing diagnostic logger canonicalizes it into a strict seven-argument event, and the dedicated handler rejects any noncanonical record. Public API responses, SQLite data, prompts, provider requests, rule fallback output, and frontend behavior remain unchanged.

**Tech Stack:** Python 3.12.13, standard-library `json`, `logging`, and `unittest`; existing pinned `openai==2.45.0`; existing loopback HTTP service and PowerShell lifecycle manager.

## Global Constraints

- Do not add or upgrade dependencies.
- Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative` as safe defaults.
- Do not change the DeepSeek prompt, private envelope fields, public response schema, SQLite schema, frontend, provider endpoint, timeout, retry count, or rule fallback contents.
- Never log provider output, JSON keys, JSON paths, field values, exception text, prompt text, email or attachment content, API keys, tokens, URLs, paths, customer identifiers, or stack traces.
- The only detail values are `not_applicable`, `json_syntax`, `top_level_shape`, `schema_version`, `analysis_shape`, `attachment_shape`, and `field_evidence_shape`.
- Every non-envelope fallback must use `detail=not_applicable`; invalid caller-supplied detail must fail closed to `not_applicable`.
- Emit exactly one terminal `analysis_fallback` event per failed model analysis. Do not add intermediate parser, client, or router logging.
- Preserve the generic public exception text and suppressed causes for every private-envelope failure.
- Keep production functions focused and below the recommended 50-line limit. Extract the fixed exception taxonomy into `deepseek_envelope_errors.py` and keep both production modules at or below the recommended 300-line limit.
- Use only synthetic `example.test` data. No subagent or automated test may call DeepSeek.
- The normal service and the DeepSeek API may be used only after all offline verification passes, and at most one synthetic analysis request may be made.
- Use `apply_patch` for edits. Every implementation task follows RED -> GREEN -> focused verification -> commit.
- Review is capped at one specification review and one code-quality review per implementation task. Newly discovered natural-language edge cases outside this approved design go to follow-up work instead of extending the loop.

---

### Task 1: Classify private-envelope validation boundaries

**Files:**
- Modify: `tests/test_deepseek_analysis_schema.py`
- Create: `backend/email_agent/deepseek_envelope_errors.py`
- Modify: `backend/email_agent/deepseek_analysis_schema.py`

**Interfaces:**
- Changes: `DeepSeekEnvelopeError(detail: object = "not_applicable")`
- Changes: `_invalid(detail: object = "not_applicable") -> NoReturn`
- Preserves: `str(DeepSeekEnvelopeError(...)) == ERROR_TEXT`
- Preserves: `parse_deepseek_analysis_v1(raw) -> dict[str, Any]`

- [ ] **Step 1: Write parser-detail tests before production code**

Update the existing test helper so RED is an assertion failure rather than an `AttributeError`:

```python
def assert_invalid(
    self,
    operation: Callable[[], object],
    *,
    detail: str | None = None,
) -> None:
    with self.assertRaises(DeepSeekEnvelopeError) as caught:
        operation()
    self.assertEqual(str(caught.exception), ERROR_TEXT)
    self.assertIsNone(caught.exception.__cause__)
    if detail is not None:
        self.assertEqual(getattr(caught.exception, "detail", None), detail)
```

Add these exact test cases, all through `parse_deepseek_analysis_v1()` except the constructor-only allowlist test:

```text
test_exception_detail_is_allowlisted_and_public_message_remains_generic
test_parse_reports_json_syntax_detail
test_parse_reports_top_level_shape_detail
test_parse_reports_schema_version_detail
test_parse_reports_analysis_shape_detail
test_parse_reports_attachment_shape_detail
test_parse_reports_field_evidence_shape_detail
```

Use these synthetic mutations:

```python
self.assert_invalid(
    lambda: parse_deepseek_analysis_v1("{not-json"),
    detail="json_syntax",
)

candidate = valid_envelope()
candidate["unexpected"] = True
self.assert_invalid(
    lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
    detail="top_level_shape",
)

candidate = valid_envelope()
candidate["schema_version"] = "other"
self.assert_invalid(
    lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
    detail="schema_version",
)

candidate = valid_envelope()
candidate["analysis"]["priority"] = "PRIVATE_INVALID"
self.assert_invalid(
    lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
    detail="analysis_shape",
)

candidate = valid_envelope()
candidate["attachment_augmentations"][0]["source_id"] = 7
self.assert_invalid(
    lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
    detail="attachment_shape",
)

candidate = valid_envelope()
candidate["field_evidence"]["summary"] = "not-a-list"
self.assert_invalid(
    lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
    detail="field_evidence_shape",
)
```

The constructor test must verify a valid built-in detail is retained, a free-form string and a `str` subclass become `not_applicable`, the message remains `ERROR_TEXT`, and no private marker appears in the message.

- [ ] **Step 2: Run focused parser tests and verify RED**

```powershell
$oldProvider = $env:EMAIL_AGENT_LLM_PROVIDER
try {
    $env:EMAIL_AGENT_LLM_PROVIDER = 'disabled'
    & 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_deepseek_analysis_schema -v
} finally {
    if ($null -eq $oldProvider) {
        Remove-Item Env:EMAIL_AGENT_LLM_PROVIDER -ErrorAction SilentlyContinue
    } else {
        $env:EMAIL_AGENT_LLM_PROVIDER = $oldProvider
    }
}
```

Expected: new assertions fail because the exception has no `detail` and all boundaries currently collapse to one generic error.

- [ ] **Step 3: Implement the fixed parser taxonomy**

Create `backend/email_agent/deepseek_envelope_errors.py` so the existing 292-line schema module remains within the project size guideline:

```python
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, NoReturn


ERROR_TEXT = "DeepSeek analysis envelope is invalid."
ENVELOPE_ERROR_DETAILS = frozenset({
    "not_applicable",
    "json_syntax",
    "top_level_shape",
    "schema_version",
    "analysis_shape",
    "attachment_shape",
    "field_evidence_shape",
})


class DeepSeekEnvelopeError(ValueError):
    def __init__(self, detail: object = "not_applicable") -> None:
        super().__init__(ERROR_TEXT)
        self.detail = (
            detail
            if type(detail) is str and detail in ENVELOPE_ERROR_DETAILS
            else "not_applicable"
        )


def raise_invalid_envelope(detail: object = "not_applicable") -> NoReturn:
    raise DeepSeekEnvelopeError(detail) from None


def decode_provider_json(
    raw: str | bytes | bytearray,
    object_pairs_hook: Callable[[list[tuple[str, Any]]], dict[str, Any]],
) -> Any:
    if not isinstance(raw, (str, bytes, bytearray)):
        raise_invalid_envelope("json_syntax")
    try:
        return json.loads(raw, object_pairs_hook=object_pairs_hook)
    except (ValueError, RecursionError, TypeError, UnicodeDecodeError):
        raise_invalid_envelope("json_syntax")


def validate_at_boundary(
    detail: str,
    validator: Callable[..., Any],
    *args: object,
) -> Any:
    try:
        return validator(*args)
    except DeepSeekEnvelopeError:
        raise_invalid_envelope(detail)
```

In `deepseek_analysis_schema.py`, remove the local `json` import, error constant, exception class, `NoReturn` import, and bottom `_invalid()` implementation, then re-export the same names and alias the helpers:

```python
from collections.abc import Collection, Mapping
from typing import Any

from .deepseek_envelope_errors import (
    ERROR_TEXT, DeepSeekEnvelopeError, decode_provider_json as _decode_json,
    raise_invalid_envelope as _invalid,
    validate_at_boundary as _validate_boundary,
)
```

Move the JSON-decoding boundary out of the large schema module so schema validation can never be reclassified as JSON syntax:

```python
def parse_deepseek_analysis_v1(
    raw: str | bytes | bytearray,
) -> dict[str, Any]:
    value = _decode_json(raw, _object_without_duplicate_keys)
    return validate_deepseek_analysis_v1(value)
```

Classify the exact validation boundary without recording keys, paths, or values:

```python
def validate_deepseek_analysis_v1(value: object) -> dict[str, Any]:
    envelope = _validate_boundary("top_level_shape", _object, value, ENVELOPE_FIELDS)
    if envelope["schema_version"] != SCHEMA_VERSION:
        _invalid("schema_version")
    _validate_boundary("analysis_shape", _validate_analysis, envelope["analysis"])
    _validate_boundary(
        "attachment_shape",
        _validate_attachments,
        envelope["attachment_augmentations"],
    )
    _validate_boundary(
        "field_evidence_shape",
        _validate_field_evidence_shape,
        envelope["field_evidence"],
    )
    return envelope
```

`_object_without_duplicate_keys()` must call `_invalid("json_syntax")` on a duplicate. No other validator may record dynamic context. Keeping `validate_at_boundary()` in the new auxiliary module prevents the existing 292-line schema from growing past the project guideline; add a test assertion that both `deepseek_envelope_errors.py` and `deepseek_analysis_schema.py` contain no more than 300 physical lines.

- [ ] **Step 4: Run focused parser tests and verify GREEN**

Run the Step 2 command again.

Expected: all parser tests pass, including six fixed detail boundaries, fixed public error text, and no exception cause.

- [ ] **Step 5: Commit Task 1**

```powershell
git add backend/email_agent/deepseek_envelope_errors.py backend/email_agent/deepseek_analysis_schema.py tests/test_deepseek_analysis_schema.py
git commit -m "fix: classify DeepSeek envelope failures"
```

---

### Task 2: Extend the canonical diagnostic sink safely

**Files:**
- Modify: `tests/test_analysis_diagnostics.py`
- Modify: `tests/test_logging_config.py`
- Modify: `backend/email_agent/analysis_diagnostics.py`
- Modify: `backend/email_agent/logging_config.py`

**Interfaces:**
- Changes: `FALLBACK_EVENT_TEMPLATE` from six to seven arguments
- Produces: `FALLBACK_DETAILS: frozenset[str]`
- Changes: `log_analysis_fallback(..., output_mode: str, detail: str, elapsed_ms: int) -> None`

- [ ] **Step 1: Write logger and filter tests before production code**

Update the signature contract to exactly:

```python
(
    "code",
    "stage",
    "provider",
    "model",
    "output_mode",
    "detail",
    "elapsed_ms",
)
```

Update every canonical event to:

```text
event=analysis_fallback code=provider_auth stage=provider provider=deepseek model=deepseek-v4-flash output_mode=model_led detail=not_applicable elapsed_ms=123
```

Add tests with these exact behaviors:

```python
for detail in (
    "json_syntax",
    "top_level_shape",
    "schema_version",
    "analysis_shape",
    "attachment_shape",
    "field_evidence_shape",
):
    log_analysis_fallback(
        code="envelope_invalid",
        stage="envelope",
        provider="deepseek",
        model="deepseek-v4-flash",
        output_mode="model_led",
        detail=detail,
        elapsed_ms=123,
    )
```

- Each fixed envelope detail appears unchanged.
- A free-form detail and a `str` subclass become `not_applicable`; the private marker does not appear.
- `provider_auth` with `detail="analysis_shape"` becomes `detail=not_applicable`.
- Direct `LogRecord` values with free-form detail, `str`-subclass detail, `bool` detail, or non-envelope code plus envelope detail are rejected by the production handler filter.
- `envelope_invalid + not_applicable` is accepted so fail-closed canonicalization never drops the required terminal event.
- Root, library, near-miss-template, exception, `exc_text`, and stack records remain rejected.

- [ ] **Step 2: Run focused diagnostic tests and verify RED**

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_analysis_diagnostics tests.test_logging_config -v
```

Expected: failures show the missing `detail` parameter, old six-argument template, and old filter arity.

- [ ] **Step 3: Implement the seven-argument fail-closed sink**

In `analysis_diagnostics.py`, add exactly:

```python
FALLBACK_DETAILS = frozenset({
    "not_applicable",
    "json_syntax",
    "top_level_shape",
    "schema_version",
    "analysis_shape",
    "attachment_shape",
    "field_evidence_shape",
})

FALLBACK_EVENT_TEMPLATE = (
    "event=analysis_fallback code=%s stage=%s provider=%s model=%s "
    "output_mode=%s detail=%s elapsed_ms=%d"
)
```

Extend the keyword-only logger signature and canonicalization:

```python
safe_detail = _allowlisted_value(
    detail,
    FALLBACK_DETAILS,
    "not_applicable",
)
if safe_code != "envelope_invalid":
    safe_detail = "not_applicable"
logger.warning(
    FALLBACK_EVENT_TEMPLATE,
    safe_code,
    safe_stage,
    safe_provider,
    safe_model,
    safe_mode,
    safe_detail,
    safe_elapsed,
)
```

In `logging_config.py`, require the exact template, no exception/stack metadata, a seven-item built-in tuple, and:

```python
if type(detail) is not str or detail not in FALLBACK_DETAILS:
    return False
if code != "envelope_invalid" and detail != "not_applicable":
    return False
```

Keep the existing isolated handler topology and rotation settings unchanged.

- [ ] **Step 4: Run focused diagnostic tests and verify GREEN**

Run the Step 2 command again.

Expected: all diagnostic and logging-configuration tests pass; unsafe direct records are absent from the sink.

- [ ] **Step 5: Commit Task 2**

```powershell
git add backend/email_agent/analysis_diagnostics.py backend/email_agent/logging_config.py tests/test_analysis_diagnostics.py tests/test_logging_config.py
git commit -m "fix: add allowlisted fallback detail field"
```

---

### Task 3: Propagate parser detail to the single terminal fallback

**Files:**
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_static_linter_constraints.py`
- Modify: `backend/email_agent/analysis_model_routes.py`

**Interfaces:**
- Changes: `_AnalysisFallback(code: str, stage: str, detail: str = "not_applicable")`
- Changes: `_diagnosed_fallback(..., detail: str = "not_applicable")`
- Preserves: exact rule-fallback object identity/equality and one terminal log event

- [ ] **Step 1: Write route propagation tests before production code**

Update all existing fallback-event assertions to include `detail=not_applicable`, except malformed private-envelope cases.

For malformed JSON, assert all three invariants:

```python
self.assertEqual(result, self._expected_model_email_rule_fallback())
self.assertEqual(len(captured.output), 1)
self.assertIn(
    "code=envelope_invalid stage=envelope provider=deepseek "
    "model=deepseek-v4-flash output_mode=model_led "
    "detail=json_syntax",
    captured.output[0],
)
```

Patch the parser with `side_effect=DeepSeekEnvelopeError("schema_version")` and assert the exact fallback, one event, and `detail=schema_version`. Keep provider, evidence, safety, schema, language, and unexpected-analysis failures at `not_applicable`.

Update the mechanical keyword test to require exactly:

```python
{
    "code",
    "stage",
    "provider",
    "model",
    "output_mode",
    "detail",
    "elapsed_ms",
}
```

- [ ] **Step 2: Run focused route tests and verify RED**

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_analyzer tests.test_static_linter_constraints -v
```

Expected: failures show that `_AnalysisFallback` drops detail and the terminal logger call lacks the new argument.

- [ ] **Step 3: Implement internal-only detail propagation**

Import `DeepSeekEnvelopeError`, then extend the fallback object:

```python
class _AnalysisFallback(Exception):
    def __init__(
        self,
        code: str,
        stage: str,
        detail: str = "not_applicable",
    ) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage
        self.detail = detail
```

Use a dedicated envelope wrapper so other stages cannot accidentally carry an envelope detail:

```python
def _run_envelope_stage(action: Callable[[], _T]) -> _T:
    try:
        return action()
    except DeepSeekEnvelopeError as exc:
        raise _AnalysisFallback(
            "envelope_invalid",
            "envelope",
            exc.detail,
        ) from exc
    except Exception as exc:
        raise _AnalysisFallback(
            "envelope_invalid",
            "envelope",
        ) from exc
```

Replace only the current model-led parse `_run_stage(...)` call with `_run_envelope_stage(...)`. Carry `failure.detail` to `_diagnosed_fallback()`, add its keyword parameter, and pass it to the existing single `log_analysis_fallback()` call. Do not touch `_rule_fallback(context.fallback)`.

- [ ] **Step 4: Run focused route tests and verify GREEN**

Run the Step 2 command again.

Expected: all route and mechanical tests pass, malformed JSON emits one `json_syntax` event, and returned fallback data is unchanged.

- [ ] **Step 5: Commit Task 3**

```powershell
git add backend/email_agent/analysis_model_routes.py tests/test_analyzer.py tests/test_static_linter_constraints.py
git commit -m "fix: propagate envelope failure details"
```

---

### Task 4: Synchronize operator documentation and contracts

**Files:**
- Modify: `tests/test_deepseek_documentation_contracts.py`
- Modify: `docs/conventions/logging.md`
- Modify: `docs/operations/troubleshooting.md`
- Modify: `docs/operations/deployment_notes.md`
- Modify: `docs/api/backend_api_contract.md`
- Modify: `docs/operations/deepseek_envelope_subdiagnostics_task_brief.md`
- Modify: `docs/superpowers/specs/2026-07-13-deepseek-envelope-subdiagnostics-design.md`
- Modify: `docs/superpowers/plans/2026-07-14-deepseek-envelope-subdiagnostics.md`

- [ ] **Step 1: Add documentation-contract tests before editing active docs**

Add `test_envelope_subdiagnostic_contract_is_explicit` and require the active logging, troubleshooting, deployment, backend API, design, task brief, and plan documents to contain:

```text
detail=
not_applicable
json_syntax
top_level_shape
schema_version
analysis_shape
attachment_shape
field_evidence_shape
```

Also require language that non-envelope fallbacks use `not_applicable` and that provider output, JSON keys, paths, and values are prohibited. The backend API document must explicitly call this an operator-only log change, not a public response field.

- [ ] **Step 2: Run documentation tests and verify RED**

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_deepseek_documentation_contracts -v
```

Expected: active operator documents still describe the six-argument event and fail the new contract.

- [ ] **Step 3: Update the active documentation**

- `docs/conventions/logging.md`: replace the canonical template with the seven-argument form; list all seven detail values; state that unknown values fail closed and non-envelope failures are `not_applicable`.
- `docs/operations/troubleshooting.md`: map the six envelope details to the next coarse investigation area; explicitly state that the detail cannot reconstruct provider content.
- `docs/operations/deployment_notes.md`: add the fixed detail field to backend-only diagnostic verification.
- `docs/api/backend_api_contract.md`: document the operator-only event extension and state that no public API response field was added.
- Design/task brief/plan: record approval and implementation state without claiming tests that have not yet run.

Use this exact canonical contract in logging and backend API documentation:

```text
event=analysis_fallback code=<allowlisted code> stage=<allowlisted stage> provider=<allowlisted provider> model=<allowlisted model> output_mode=<allowlisted mode> detail=<allowlisted detail> elapsed_ms=<non-negative integer>
```

Use this exact safety paragraph in each active operator document, translated only when the surrounding document is Chinese:

```text
The detail allowlist is not_applicable, json_syntax, top_level_shape,
schema_version, analysis_shape, attachment_shape, and field_evidence_shape.
Every non-envelope fallback uses not_applicable. This operator-only log field
is not added to the public API or SQLite, and it must never contain or be used
to reconstruct provider output, JSON keys, paths, values, or exception text.
```

Use these exact troubleshooting mappings:

```text
json_syntax -> JSON decoding or duplicate-key rejection
top_level_shape -> exact top-level object/key-set validation
schema_version -> fixed private-envelope version validation
analysis_shape -> nested analysis field/type/enum validation
attachment_shape -> attachment augmentation validation
field_evidence_shape -> field-evidence map/list validation
```

- [ ] **Step 4: Run documentation tests and verify GREEN**

Run the Step 2 command again.

Expected: documentation-contract tests pass with no public API/schema implication.

- [ ] **Step 5: Commit Task 4**

```powershell
git add docs tests/test_deepseek_documentation_contracts.py
git commit -m "docs: document envelope subdiagnostics"
```

---

### Task 5: Complete offline verification and update project status

**Files:**
- Modify: `docs/operations/deepseek_envelope_subdiagnostics_task_brief.md`
- Regenerate: `docs/operations/project_status_log.md`
- Generate locally, do not commit unless already tracked by policy: `outputs/cleanup_report.md`

- [ ] **Step 1: Run all focused Python suites**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$oldProvider = $env:EMAIL_AGENT_LLM_PROVIDER
try {
    $env:EMAIL_AGENT_LLM_PROVIDER = 'disabled'
    & $py -B -m unittest tests.test_deepseek_analysis_schema tests.test_analysis_diagnostics tests.test_logging_config tests.test_analyzer tests.test_static_linter_constraints tests.test_deepseek_documentation_contracts -v
} finally {
    if ($null -eq $oldProvider) {
        Remove-Item Env:EMAIL_AGENT_LLM_PROVIDER -ErrorAction SilentlyContinue
    } else {
        $env:EMAIL_AGENT_LLM_PROVIDER = $oldProvider
    }
}
```

Expected: all focused tests pass and no network call occurs.

- [ ] **Step 2: Run complete unit discovery with provider disabled**

```powershell
$oldProvider = $env:EMAIL_AGENT_LLM_PROVIDER
try {
    $env:EMAIL_AGENT_LLM_PROVIDER = 'disabled'
    & 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest discover -s tests
} finally {
    if ($null -eq $oldProvider) {
        Remove-Item Env:EMAIL_AGENT_LLM_PROVIDER -ErrorAction SilentlyContinue
    } else {
        $env:EMAIL_AGENT_LLM_PROVIDER = $oldProvider
    }
}
```

Expected: `OK`; any failure blocks status generation and live verification.

- [ ] **Step 3: Run JavaScript, diff, and sensitive-content checks**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$jsFiles = rg --files frontend -g '*.js'
foreach ($file in $jsFiles) { node --check $file }
git diff --check
& $py -B -m unittest tests.test_architecture_constraints -v
```

Expected: every JS syntax check exits zero, `git diff --check` is empty, and the repository's audited architecture guard reports no raw secret literal. Use this existing guard instead of a broad regex so intentional synthetic redaction fixtures such as `Bearer synthetic-secret` remain explicitly allowed by the reviewed test policy.

- [ ] **Step 4: Record actual results, regenerate status, and rescan**

Fill the task brief execution record with exact files and test counts, set it to `implemented`, and then run:

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -B scripts\generate_project_status.py --output docs\operations\project_status_log.md
$oldProvider = $env:EMAIL_AGENT_LLM_PROVIDER
try {
    $env:EMAIL_AGENT_LLM_PROVIDER = 'disabled'
    & $py -B -m unittest discover -s tests
} finally {
    if ($null -eq $oldProvider) {
        Remove-Item Env:EMAIL_AGENT_LLM_PROVIDER -ErrorAction SilentlyContinue
    } else {
        $env:EMAIL_AGENT_LLM_PROVIDER = $oldProvider
    }
}
& $py -B scripts\maintenance_scan.py --output outputs\cleanup_report.md
git diff --check
git status --short
```

Expected: generated status names this task, full discovery remains `OK`, maintenance scan reports no blocking issue, and only intended files are modified.

- [ ] **Step 5: Commit verification documentation**

```powershell
git add docs/operations/deepseek_envelope_subdiagnostics_task_brief.md docs/operations/project_status_log.md docs/superpowers/plans/2026-07-14-deepseek-envelope-subdiagnostics.md
git commit -m "docs: record envelope diagnostic verification"
```

---

### Task 6: Run one authorized synthetic DeepSeek verification

**Files:**
- Runtime-only: `outputs/local_debug_service.log`
- No production or test file may be edited to influence the result.

- [ ] **Step 1: Confirm the release gate**

Do not continue unless Task 5 has fresh passing evidence, the worktree contains no unexpected file, and backend provider configuration remains server-side. Never print or inspect the API key.

- [ ] **Step 2: Restart and health-check the managed service**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -B scripts\manage_local_service.py restart
& $py -B scripts\manage_local_service.py status
(Invoke-RestMethod 'http://127.0.0.1:8765/api/health').ok
```

Expected: service status is `running` and health is `True`. If startup or health fails, stop without an API analysis call.

- [ ] **Step 3: Verify non-sensitive provider routing without exposing the key**

```powershell
$configJson = & $py -B -c "import json; from backend.email_agent.config import load_config; c=load_config(); print(json.dumps({'provider': c.llm_provider, 'model': c.deepseek_model, 'output_mode': c.deepseek_output_mode}))"
if ($LASTEXITCODE -ne 0) { throw 'Backend configuration preflight failed.' }
$safeConfig = $configJson | ConvertFrom-Json
$safeConfig | Format-List provider, model, output_mode
if ($safeConfig.provider -ne 'deepseek' -or $safeConfig.output_mode -ne 'model_led') {
    throw 'Synthetic API verification requires deepseek + model_led; no request was sent.'
}
```

Expected: only provider, model, and output mode are printed; provider is `deepseek` and output mode is `model_led`. The command never reads, tests, or prints the API key. A mismatch stops before the one allowed request.

- [ ] **Step 4: Make exactly one synthetic analysis request and isolate new log lines**

```powershell
$logPath = 'outputs\local_debug_service.log'
$lineCountBefore = if (Test-Path -LiteralPath $logPath) {
    @(Get-Content -LiteralPath $logPath).Count
} else {
    0
}

$payload = @{
    user_confirmed = $true
    subject = 'SYNTHETIC ENVELOPE DETAIL TEST'
    from = 'customer@example.test'
    to = @('sales@example.test')
    sent_at = '2026-07-14T12:00:00Z'
    body_text = 'Please acknowledge synthetic PO TEST-2026-001 and confirm the delivery review date by 2026-07-20.'
    attachments = @()
} | ConvertTo-Json -Depth 6

$response = Invoke-RestMethod `
    -Method Post `
    -Uri 'http://127.0.0.1:8765/api/analyze-current-email' `
    -ContentType 'application/json; charset=utf-8' `
    -Body ([Text.Encoding]::UTF8.GetBytes($payload)) `
    -TimeoutSec 40

$response.analysis.analysis_engine | Format-List
$newLogLines = @(Get-Content -LiteralPath $logPath) |
    Select-Object -Skip $lineCountBefore
$newFallbackEvents = @($newLogLines | Select-String 'event=analysis_fallback')
$newFallbackEvents
```

Expected outcomes are intentionally both acceptable:

- Model accepted: engine identifies DeepSeek and `$newFallbackEvents.Count -eq 0`.
- Rule fallback: engine identifies Rule fallback, `$newFallbackEvents.Count -eq 1`, and that event includes one canonical detail. For `code=envelope_invalid`, the detail must be one of the six envelope values; for every other allowlisted code it must be `not_applicable`.

Only those two outcomes pass live verification. A timeout, request error, Rule fallback with zero or multiple new events, an unknown code/stage/detail, an envelope event with `not_applicable`, or a non-envelope event with a specific envelope detail fails verification. Record the fixed failure state, do not retry, and do not mark the task verified. Do not display provider output or any secret. Record only engine, reason code, stage, fixed detail, and elapsed time.

- [ ] **Step 5: Record the result and decide the separate follow-up**

If the result is one of the six envelope details, add exactly one content-free line to the task brief execution record using this form, and list the next correction under unfinished follow-up work instead of changing the prompt or provider route:

```text
Synthetic live verification: engine=<fixed engine label>; code=<allowlisted code or none>; stage=<allowlisted stage or none>; detail=<allowlisted detail or none>; elapsed_ms=<non-negative integer or not_applicable>.
```

Only after one of the two passing live outcomes, keep the valid front-matter value `status: active`, set `last_update: 2026-07-14`, record `verified` in each document's execution/status section, check completed plan boxes, and run the final offline gate with provider explicitly disabled. For any failed live outcome, record `live verification failed`, leave the documents active but unverified, do not check the final plan box, and stop after the no-retry record:

```powershell
$oldProvider = $env:EMAIL_AGENT_LLM_PROVIDER
try {
    $env:EMAIL_AGENT_LLM_PROVIDER = 'disabled'
    & $py -B scripts\generate_project_status.py --output docs\operations\project_status_log.md
    & $py -B -m unittest discover -s tests
    & $py -B scripts\maintenance_scan.py --output outputs\cleanup_report.md
} finally {
    if ($null -eq $oldProvider) {
        Remove-Item Env:EMAIL_AGENT_LLM_PROVIDER -ErrorAction SilentlyContinue
    } else {
        $env:EMAIL_AGENT_LLM_PROVIDER = $oldProvider
    }
}
git diff --check
git status --short
```

Expected: status generation succeeds, full discovery is `OK` without network access, maintenance scan has no blocking issue, and only intended documentation files remain for the final record commit.

```powershell
git add docs/operations/deepseek_envelope_subdiagnostics_task_brief.md docs/operations/project_status_log.md docs/superpowers/specs/2026-07-13-deepseek-envelope-subdiagnostics-design.md docs/superpowers/plans/2026-07-14-deepseek-envelope-subdiagnostics.md
git commit -m "docs: record envelope subdiagnostic verification"
```
