---
last_update: 2026-07-13
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# DeepSeek Fallback Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every DeepSeek-to-rule fallback diagnosable through one sanitized local reason code while preserving the existing public response, deterministic fallback, privacy boundaries, and single-call behavior.

**Architecture:** A new focused diagnostic module owns allowlisted event fields and emits no untrusted content. The DeepSeek client attaches sanitized reason codes to existing fixed-message errors, the analysis router classifies validation stages and emits one terminal fallback event, and the local entrypoint configures a bounded rotating file handler that works under the Windows WMI launcher.

**Tech Stack:** Python 3.12.13, standard-library `logging`, `logging.handlers.RotatingFileHandler`, `unittest`, existing pinned `openai==2.45.0`, existing loopback HTTP service and PowerShell lifecycle manager.

## Global Constraints

- Do not add or upgrade any dependency. Keep Python 3.12.13, SQLite 3.50.4, `openai==2.45.0`, and `python-dotenv==1.2.2` unchanged.
- Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative` as safe defaults.
- Do not change prompts, the internal DeepSeek envelope, public API JSON, SQLite schema, frontend behavior, provider retry count, or fallback contents.
- Never log an API key, token, cookie, authorization value, prompt, raw exception, traceback, provider response, response body, email field, thread content, attachment name/text, URL, local path, commercial amount, or customer identifier.
- Log only fixed templates and allowlisted enum-like values. Unknown values must become `unknown` or another fixed safe value.
- Emit exactly one terminal fallback event per failed model analysis. Do not emit a second event inside lower layers.
- Keep every production function focused and below the project's recommended 50-line limit; keep every Python module below 300 lines.
- Use only synthetic values in tests. No automated, subagent, or Codex-run test may call the live DeepSeek API.
- When `log_file` is configured, install only the rotating file handler so one event produces one file entry on every platform. Use a stream handler only when no file is configured.
- Keep runtime smoke verification isolated on `127.0.0.1:8878` with a dedicated PID file and provider disabled. Restart the normal 8765 service from the main checkout only after branch integration.
- Use `apply_patch` for file edits. Each task follows RED -> GREEN -> focused verification -> commit.

---

### Task 1: Add the allowlisted diagnostic event sink

**Files:**
- Create: `backend/email_agent/analysis_diagnostics.py`
- Create: `tests/test_analysis_diagnostics.py`
- Modify: `backend/email_agent/__init__.py`

**Interfaces:**
- Produces: `log_analysis_fallback(*, code: str, stage: str, provider: str, model: str, output_mode: str, elapsed_ms: int) -> None`
- Produces: `FALLBACK_REASON_CODES: frozenset[str]`
- The function accepts no payload, exception, key, prompt, response, email, thread, attachment, URL, or path argument.

- [ ] **Step 1: Write failing allowlist and redaction tests**

Create `tests/test_analysis_diagnostics.py` with exactly these tests:

```python
from __future__ import annotations

import inspect
import unittest

from backend.email_agent.analysis_diagnostics import log_analysis_fallback


class AnalysisDiagnosticsTests(unittest.TestCase):
    def test_event_contains_only_allowlisted_values(self) -> None:
        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            log_analysis_fallback(
                code="provider_auth",
                stage="provider",
                provider="deepseek",
                model="deepseek-v4-flash",
                output_mode="model_led",
                elapsed_ms=123,
            )

        self.assertEqual(len(captured.output), 1)
        self.assertIn(
            "event=analysis_fallback code=provider_auth stage=provider "
            "provider=deepseek model=deepseek-v4-flash "
            "output_mode=model_led elapsed_ms=123",
            captured.output[0],
        )

    def test_unknown_values_cannot_inject_private_text(self) -> None:
        private = "PRIVATE_SECRET_PROMPT\nPRIVATE_URL"
        with self.assertLogs(
            "backend.email_agent.analysis_diagnostics", level="WARNING"
        ) as captured:
            log_analysis_fallback(
                code=private,
                stage=private,
                provider=private,
                model=private,
                output_mode=private,
                elapsed_ms=-9,
            )

        text = captured.output[0]
        self.assertNotIn("PRIVATE", text)
        self.assertIn("code=unexpected_analysis_error", text)
        self.assertIn("stage=analysis", text)
        self.assertIn("provider=unknown model=unknown output_mode=unknown", text)
        self.assertIn("elapsed_ms=0", text)

    def test_signature_has_no_sensitive_payload_channel(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(log_analysis_fallback).parameters),
            ("code", "stage", "provider", "model", "output_mode", "elapsed_ms"),
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_analysis_diagnostics -v
```

Expected: FAIL because `backend.email_agent.analysis_diagnostics` does not exist.

- [ ] **Step 3: Implement the fixed event contract**

Create `backend/email_agent/analysis_diagnostics.py` with this structure:

```python
"""Sanitized local diagnostics for model-to-rule fallback events."""

from __future__ import annotations

import logging


FALLBACK_REASON_CODES = frozenset({
    "provider_not_enabled", "budget_exhausted", "missing_key",
    "unsupported_model", "provider_timeout", "provider_auth",
    "provider_permission_or_balance", "provider_rate_limit",
    "provider_connection_error", "provider_server_error",
    "provider_http_error", "provider_request_failed",
    "response_incomplete", "response_empty", "envelope_invalid",
    "evidence_invalid", "safety_rejected_all", "public_schema_invalid",
    "public_language_invalid", "unexpected_analysis_error",
})
FALLBACK_STAGES = frozenset({
    "routing", "budget", "provider", "response", "envelope",
    "evidence", "safety", "schema", "language", "analysis",
})
SAFE_PROVIDERS = frozenset({"deepseek", "ollama", "openai", "disabled"})
SAFE_MODELS = frozenset({"deepseek-v4-flash", "deepseek-v4-pro", "local-model", "none"})
SAFE_OUTPUT_MODES = frozenset({"model_led", "conservative"})

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def log_analysis_fallback(
    *, code: str, stage: str, provider: str, model: str,
    output_mode: str, elapsed_ms: int,
) -> None:
    safe_code = code if code in FALLBACK_REASON_CODES else "unexpected_analysis_error"
    safe_stage = stage if stage in FALLBACK_STAGES else "analysis"
    safe_provider = provider if provider in SAFE_PROVIDERS else "unknown"
    safe_model = model if model in SAFE_MODELS else "unknown"
    safe_mode = output_mode if output_mode in SAFE_OUTPUT_MODES else "unknown"
    safe_elapsed = elapsed_ms if type(elapsed_ms) is int and elapsed_ms >= 0 else 0
    logger.warning(
        "event=analysis_fallback code=%s stage=%s provider=%s model=%s "
        "output_mode=%s elapsed_ms=%d",
        safe_code, safe_stage, safe_provider, safe_model, safe_mode, safe_elapsed,
    )
```

Add `analysis_diagnostics` to `backend/email_agent/__init__.py`'s exported module list without changing existing exports.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the Step 2 command again.

Expected: 3 tests pass and no private marker appears in output.

- [ ] **Step 5: Commit Task 1**

```powershell
git add backend/email_agent/analysis_diagnostics.py backend/email_agent/__init__.py tests/test_analysis_diagnostics.py
git commit -m "feat: add sanitized fallback diagnostics"
```

---

### Task 2: Classify DeepSeek client failures without exposing raw errors

**Files:**
- Modify: `backend/email_agent/llm_client.py:25-141`
- Modify: `tests/test_llm_client.py:120-390`

**Interfaces:**
- Changes: `LlmClientError(message: str, *, reason_code: str = "provider_request_failed")`
- Produces: `_deepseek_failure_reason(exc: BaseException) -> str`
- Existing exception messages and suppressed causes remain unchanged.

- [ ] **Step 1: Extend client tests with reason assertions**

Add assertions to the existing missing-key, unsupported-model, timeout, incomplete-response, empty-response, and generic-SDK-error tests:

```python
self.assertEqual(caught.exception.reason_code, "missing_key")
self.assertEqual(caught.exception.reason_code, "unsupported_model")
self.assertEqual(caught.exception.reason_code, "provider_timeout")
self.assertEqual(caught.exception.reason_code, "response_incomplete")
self.assertEqual(caught.exception.reason_code, "response_empty")
self.assertEqual(caught.exception.reason_code, "provider_request_failed")
```

Import `_deepseek_failure_reason` and add the following coarse HTTP classification test:

```python
def test_deepseek_status_errors_map_without_using_private_text(self) -> None:
    cases = {
        401: "provider_auth",
        402: "provider_permission_or_balance",
        403: "provider_permission_or_balance",
        429: "provider_rate_limit",
        500: "provider_server_error",
        503: "provider_server_error",
        418: "provider_http_error",
    }
    for status, expected in cases.items():
        with self.subTest(status=status):
            error = RuntimeError("PRIVATE_PROVIDER_BODY")
            error.status_code = status
            self.assertEqual(_deepseek_failure_reason(error), expected)
```

- [ ] **Step 2: Run the client tests and verify RED**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_llm_client -v
```

Expected: FAIL because `LlmClientError.reason_code` and `_deepseek_failure_reason` do not exist.

- [ ] **Step 3: Implement client reason codes**

Change the error type and add the SDK classifier:

```python
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI


class LlmClientError(RuntimeError):
    """Raised when the LLM client cannot produce an analysis."""

    def __init__(
        self, message: str, *, reason_code: str = "provider_request_failed"
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _deepseek_failure_reason(exc: BaseException) -> str:
    status = getattr(exc, "status_code", None)
    if status == 401:
        return "provider_auth"
    if status in {402, 403}:
        return "provider_permission_or_balance"
    if status == 429:
        return "provider_rate_limit"
    if isinstance(status, int) and 500 <= status <= 599:
        return "provider_server_error"
    if isinstance(status, int):
        return "provider_http_error"
    if isinstance(exc, APITimeoutError):
        return "provider_timeout"
    if isinstance(exc, APIConnectionError):
        return "provider_connection_error"
    return "provider_request_failed"
```

Attach fixed reason codes to every current DeepSeek failure site. The request boundary becomes:

```python
except TimeoutError:
    raise LlmClientError(
        "DeepSeek analysis request timed out.", reason_code="provider_timeout"
    ) from None
except Exception as exc:
    raise LlmClientError(
        "DeepSeek analysis request failed.",
        reason_code=_deepseek_failure_reason(exc),
    ) from None
```

Use `missing_key`, `unsupported_model`, `response_incomplete`, and `response_empty` at the corresponding fixed-message raises. Do not store `exc`, use `str(exc)`, or attach the original cause.

- [ ] **Step 4: Run client and static tests and verify GREEN**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_llm_client tests.test_static_linter_constraints -v
```

Expected: all tests pass; fixed public-safe error messages remain unchanged.

- [ ] **Step 5: Commit Task 2**

```powershell
git add backend/email_agent/llm_client.py tests/test_llm_client.py
git commit -m "fix: classify DeepSeek client failures"
```

---

### Task 3: Emit one terminal reason from the analysis route

**Files:**
- Modify: `backend/email_agent/analysis_model_routes.py:82-203`
- Modify: `tests/test_analyzer.py:810-1085`
- Modify: `tests/test_static_linter_constraints.py:99-270`

**Interfaces:**
- Consumes: `LlmClientError.reason_code`
- Consumes: `log_analysis_fallback(...)`
- Produces internally: `_AnalysisFallback(code: str, stage: str)` and `_diagnosed_fallback(...)`
- Returns: the same complete rule fallback object as before.

- [ ] **Step 1: Add failing stage and single-event tests**

Add a helper to `tests/test_analyzer.py` that captures the diagnostic logger, then add synthetic cases for:

```python
def test_model_led_provider_reason_is_logged_once(self) -> None:
    with self.assertLogs(
        "backend.email_agent.analysis_diagnostics", level="WARNING"
    ) as captured, patch(
        "backend.email_agent.analysis_model_routes.generate_analysis",
        side_effect=LlmClientError(
            "PRIVATE", reason_code="provider_auth"
        ),
    ):
        result = analyze_current_email(
            self._model_email(), config=self._deepseek_config()
        )

    self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
    self.assertEqual(len(captured.output), 1)
    self.assertIn("code=provider_auth stage=provider", captured.output[0])
    self.assertNotIn("PRIVATE", captured.output[0])


def test_model_led_malformed_envelope_has_specific_diagnostic(self) -> None:
    with self.assertLogs(
        "backend.email_agent.analysis_diagnostics", level="WARNING"
    ) as captured:
        result = analyze_current_email(
            self._model_email(),
            llm_generate=lambda _prompt: "not json",
            config=self._deepseek_config(),
        )

    self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
    self.assertEqual(len(captured.output), 1)
    self.assertIn("code=envelope_invalid stage=envelope", captured.output[0])
```

Add these isolated cases. Each captures exactly one event and preserves the rule result:

```python
def test_model_led_budget_exhaustion_has_specific_diagnostic(self) -> None:
    budget = AnalysisBudget(deadline=4.9, _clock=lambda: 0.0)
    with self.assertLogs(
        "backend.email_agent.analysis_diagnostics", level="WARNING"
    ) as captured:
        result = analyze_current_email(
            self._model_email(), config=self._deepseek_config(), budget=budget
        )
    self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
    self.assertEqual(len(captured.output), 1)
    self.assertIn("code=budget_exhausted stage=budget", captured.output[0])


def test_model_led_evidence_failure_has_specific_diagnostic(self) -> None:
    with patch(
        "backend.email_agent.analysis_model_routes.parse_deepseek_analysis_v1",
        return_value={},
    ), patch(
        "backend.email_agent.analysis_model_routes.validate_envelope_evidence",
        side_effect=ValueError("PRIVATE_EVIDENCE"),
    ), self.assertLogs(
        "backend.email_agent.analysis_diagnostics", level="WARNING"
    ) as captured:
        result = analyze_current_email(
            self._model_email(), llm_generate=lambda _prompt: "{}",
            config=self._deepseek_config(),
        )
    self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
    self.assertEqual(len(captured.output), 1)
    self.assertIn("code=evidence_invalid stage=evidence", captured.output[0])
    self.assertNotIn("PRIVATE_EVIDENCE", captured.output[0])


def test_model_led_all_rejected_has_specific_diagnostic(self) -> None:
    def rejected(_envelope, *, fallback, **_kwargs):
        return SafeMergeResult(copy.deepcopy(fallback), False, ("all",))

    with patch(
        "backend.email_agent.analysis_model_routes.parse_deepseek_analysis_v1",
        return_value={},
    ), patch(
        "backend.email_agent.analysis_model_routes.validate_envelope_evidence",
        return_value={},
    ), patch(
        "backend.email_agent.analysis_model_routes.merge_deepseek_analysis_v1",
        side_effect=rejected,
    ), self.assertLogs(
        "backend.email_agent.analysis_diagnostics", level="WARNING"
    ) as captured:
        result = analyze_current_email(
            self._model_email(), llm_generate=lambda _prompt: "{}",
            config=self._deepseek_config(),
        )
    self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
    self.assertEqual(len(captured.output), 1)
    self.assertIn("code=safety_rejected_all stage=safety", captured.output[0])


def test_model_led_public_schema_failure_has_specific_diagnostic(self) -> None:
    def merged(_envelope, *, fallback, **_kwargs):
        analysis = copy.deepcopy(fallback)
        analysis["summary"] = "模型输出仅用于合成测试。"
        return SafeMergeResult(analysis, True, ())

    with patch(
        "backend.email_agent.analysis_model_routes.parse_deepseek_analysis_v1",
        return_value={},
    ), patch(
        "backend.email_agent.analysis_model_routes.validate_envelope_evidence",
        return_value={},
    ), patch(
        "backend.email_agent.analysis_model_routes.merge_deepseek_analysis_v1",
        side_effect=merged,
    ), patch(
        "backend.email_agent.analysis_model_routes.validate_analysis_result",
        side_effect=ValueError("PRIVATE_SCHEMA"),
    ), self.assertLogs(
        "backend.email_agent.analysis_diagnostics", level="WARNING"
    ) as captured:
        result = analyze_current_email(
            self._model_email(), llm_generate=lambda _prompt: "{}",
            config=self._deepseek_config(),
        )
    self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
    self.assertEqual(len(captured.output), 1)
    self.assertIn("code=public_schema_invalid stage=schema", captured.output[0])
    self.assertNotIn("PRIVATE_SCHEMA", captured.output[0])


def test_model_led_public_language_failure_has_specific_diagnostic(self) -> None:
    def merged(_envelope, *, fallback, **_kwargs):
        analysis = copy.deepcopy(fallback)
        analysis["summary"] = "模型输出仅用于合成测试。"
        return SafeMergeResult(analysis, True, ())

    with patch(
        "backend.email_agent.analysis_model_routes.parse_deepseek_analysis_v1",
        return_value={},
    ), patch(
        "backend.email_agent.analysis_model_routes.validate_envelope_evidence",
        return_value={},
    ), patch(
        "backend.email_agent.analysis_model_routes.merge_deepseek_analysis_v1",
        side_effect=merged,
    ), patch(
        "backend.email_agent.analysis_model_routes.validate_public_language",
        side_effect=ValueError("PRIVATE_LANGUAGE"),
    ), self.assertLogs(
        "backend.email_agent.analysis_diagnostics", level="WARNING"
    ) as captured:
        result = analyze_current_email(
            self._model_email(), llm_generate=lambda _prompt: "{}",
            config=self._deepseek_config(),
        )
    self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
    self.assertEqual(len(captured.output), 1)
    self.assertIn("code=public_language_invalid stage=language", captured.output[0])
    self.assertNotIn("PRIVATE_LANGUAGE", captured.output[0])


def test_unexpected_analysis_failure_has_specific_diagnostic(self) -> None:
    with patch(
        "backend.email_agent.analysis_model_routes.build_deepseek_untrusted_context",
        side_effect=RuntimeError("PRIVATE_ANALYSIS"),
    ), self.assertLogs(
        "backend.email_agent.analysis_diagnostics", level="WARNING"
    ) as captured:
        result = analyze_current_email(
            self._model_email(), config=self._deepseek_config()
        )
    self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
    self.assertEqual(len(captured.output), 1)
    self.assertIn(
        "code=unexpected_analysis_error stage=analysis", captured.output[0]
    )
    self.assertNotIn("PRIVATE_ANALYSIS", captured.output[0])
```

Wrap the existing `test_safe_partial_model_merge_uses_ai_model_label` call with:

```python
with self.assertNoLogs(
    "backend.email_agent.analysis_diagnostics", level="WARNING"
):
    result = analyze_current_email(...)
```

Add this complete mechanical test to `tests/test_static_linter_constraints.py`:

```python
def test_analysis_diagnostic_calls_use_only_safe_keywords(self) -> None:
    path = ROOT / "backend" / "email_agent" / "analysis_model_routes.py"
    tree = ast.parse(read_text(path))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "log_analysis_fallback"
    ]
    self.assertEqual(len(calls), 1)
    self.assertEqual(
        {item.arg for item in calls[0].keywords},
        {"code", "stage", "provider", "model", "output_mode", "elapsed_ms"},
    )
```

Add a mechanical test that parses every `log_analysis_fallback(...)` call and asserts its keyword set is exactly:

```python
{
    "code", "stage", "provider", "model", "output_mode", "elapsed_ms"
}
```

- [ ] **Step 2: Run route and static tests and verify RED**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_analyzer tests.test_static_linter_constraints -v
```

Expected: FAIL because the route does not emit diagnostic events or distinguish validation stages.

- [ ] **Step 3: Centralize diagnosed fallback**

Add a private signal that carries only fixed values:

```python
class _AnalysisFallback(RuntimeError):
    def __init__(self, code: str, stage: str) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage
```

At `route_analysis` entry, record `started_at = time.monotonic()`. Replace every fallback return with `_diagnosed_fallback(...)`. Catch in this order:

```python
except LlmClientError as exc:
    return _diagnosed_fallback(
        context, started_at, code=exc.reason_code, stage="provider"
    )
except _AnalysisFallback as exc:
    return _diagnosed_fallback(
        context, started_at, code=exc.code, stage=exc.stage
    )
except Exception:
    return _diagnosed_fallback(
        context, started_at,
        code="unexpected_analysis_error", stage="analysis",
    )
```

Implement the only logging call site:

```python
def _diagnosed_fallback(
    context: AnalysisRouteContext, started_at: float, *, code: str, stage: str,
) -> dict[str, Any]:
    provider = context.config.llm_provider
    model = (
        context.config.deepseek_model if provider == "deepseek"
        else "local-model" if provider == "ollama" else "none"
    )
    elapsed_ms = max(0, int((time.monotonic() - started_at) * 1000))
    log_analysis_fallback(
        code=code, stage=stage, provider=provider, model=model,
        output_mode=context.config.deepseek_output_mode,
        elapsed_ms=elapsed_ms,
    )
    return _rule_fallback(context.fallback)
```

In `_run_model_led`, wrap envelope parsing, evidence validation, safety merge, final schema validation, and public-language validation separately. Convert their exceptions to `_AnalysisFallback` with the codes/stages from the design. Raise `safety_rejected_all` when `merged.used_model` is false. Raise `budget_exhausted` when the post-prompt provider budget is unavailable.

In `_run_conservative`, convert parse/schema failures to `public_schema_invalid` and no surviving augmentation to `safety_rejected_all`. Keep successful output and engine labels unchanged.

- [ ] **Step 4: Run route, client, diagnostic, and static tests and verify GREEN**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_analysis_diagnostics tests.test_llm_client tests.test_analyzer tests.test_static_linter_constraints -v
```

Expected: all tests pass, each fallback test captures one event, accepted model output captures none, and no private marker appears.

- [ ] **Step 5: Commit Task 3**

```powershell
git add backend/email_agent/analysis_model_routes.py tests/test_analyzer.py tests/test_static_linter_constraints.py
git commit -m "fix: diagnose model fallback stages"
```

---

### Task 4: Configure bounded Windows-compatible service logging

**Files:**
- Modify: `backend/email_agent/logging_config.py:1-16`
- Modify: `scripts/run_local_debug.py:1-35`
- Create: `tests/test_logging_config.py`
- Modify: `tests/test_run_local_debug.py:1-48`

**Interfaces:**
- Changes: `configure_logging(level: str = "INFO", *, log_file: str | Path | None = None) -> None`
- `scripts/run_local_debug.py` uses `ROOT / "outputs" / "local_debug_service.log"`.
- The Windows service manager remains unchanged because the application writes the file directly.

- [ ] **Step 1: Add failing real-file and entrypoint-order tests**

Create `tests/test_logging_config.py` with an isolated subprocess test:

```python
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]


class LoggingConfigTests(unittest.TestCase):
    def test_configured_file_handler_writes_utf8_event(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "service.log"
            code = (
                "import logging; "
                "from backend.email_agent.logging_config import configure_logging; "
                f"configure_logging('INFO', log_file={str(path)!r}); "
                "logging.getLogger('synthetic').warning("
                "'event=analysis_fallback code=provider_timeout')"
            )
            result = subprocess.run(
                [sys.executable, "-B", "-c", code], cwd=ROOT,
                check=False, capture_output=True, text=True, timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "event=analysis_fallback code=provider_timeout",
                path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
```

In `tests/test_run_local_debug.py`, import `SimpleNamespace`, `MagicMock`, `call`, `patch`, `load_config`, and `scripts.run_local_debug`. Add a test that patches `parse_args`, `load_config`, `configure_logging`, and `run_server`; attach the latter two to one manager and assert:

```python
self.assertEqual(
    manager.mock_calls,
    [
        call.configure(
            config.log_level,
            log_file=run_local_debug.ROOT / "outputs" / "local_debug_service.log",
        ),
        call.run_server(host="127.0.0.1", port=8765, database_path=None),
    ],
)
```

- [ ] **Step 2: Run logging and entrypoint tests and verify RED**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_logging_config tests.test_run_local_debug -v
```

Expected: FAIL because `configure_logging` has no `log_file` argument and the entrypoint does not configure logging.

- [ ] **Step 3: Implement rotating file logging and startup wiring**

Update `logging_config.py`:

```python
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 2
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(
    level: str = "INFO", *, log_file: str | Path | None = None
) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handlers: list[logging.Handler]
    if log_file is None:
        handlers = [logging.StreamHandler()]
    else:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers = [RotatingFileHandler(
            path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )]
    logging.basicConfig(
        level=numeric_level, format=LOG_FORMAT, handlers=handlers, force=True,
    )
```

Update `run_local_debug.py` to import `load_config` and `configure_logging`, then call:

```python
config = load_config()
configure_logging(
    config.log_level,
    log_file=ROOT / "outputs" / "local_debug_service.log",
)
run_server(host=host, port=args.port, database_path=args.database)
```

Do not print configuration, key presence, provider errors, or request content.

- [ ] **Step 4: Run logging, entrypoint, manager, and linter tests and verify GREEN**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_logging_config tests.test_run_local_debug tests.test_manage_local_service tests.test_static_linter_constraints -v
```

Expected: all tests pass and the isolated file contains the synthetic event.

- [ ] **Step 5: Commit Task 4**

```powershell
git add backend/email_agent/logging_config.py scripts/run_local_debug.py tests/test_logging_config.py tests/test_run_local_debug.py
git commit -m "fix: persist sanitized service diagnostics"
```

---

### Task 5: Document operations, update status, and run release verification

**Files:**
- Modify: `docs/conventions/logging.md`
- Modify: `docs/operations/troubleshooting.md`
- Modify: `docs/operations/deployment_notes.md`
- Modify: `docs/api/backend_api_contract.md`
- Modify: `docs/operations/deepseek_fallback_diagnostics_task_brief.md`
- Modify: `docs/superpowers/specs/2026-07-13-deepseek-fallback-diagnostics-design.md`
- Modify: `docs/operations/project_status_log.md` through the generator
- Modify: `tests/test_deepseek_documentation_contracts.py`

**Interfaces:**
- Documents: `outputs/local_debug_service.log` as the operator-only diagnostic source.
- Documents: `Get-Content outputs\local_debug_service.log -Tail 30 | Select-String 'event=analysis_'`.
- Confirms: diagnostics do not enter the public API or SQLite.

- [ ] **Step 1: Add failing documentation contract assertions**

Add a test to `tests/test_deepseek_documentation_contracts.py` that reads the four operational/contract documents and requires these exact concepts:

```python
required = (
    "analysis_fallback",
    "provider_auth",
    "provider_permission_or_balance",
    "provider_timeout",
    "envelope_invalid",
    "evidence_invalid",
    "safety_rejected_all",
    "local_debug_service.log",
    "public API",
    "raw exception",
)
```

Assert the combined text contains every required value and explicitly says logs must not contain keys, prompts, email/attachment content, provider output, or raw exceptions.

- [ ] **Step 2: Run the documentation contract test and verify RED**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_deepseek_documentation_contracts -v
```

Expected: FAIL because current operational docs do not define the new reason-code and rotating-log contract.

- [ ] **Step 3: Update operational and contract documentation**

Document all of the following without adding provider secrets or real message data:

```text
- Rule fallback remains a successful public analysis response.
- The backend logs exactly one terminal allowlisted reason code locally.
- The browser receives no provider/account diagnostic detail.
- The rotating log is outputs/local_debug_service.log with two bounded backups.
- Operators read only the latest event lines with the documented PowerShell command.
- Raw exceptions, tracebacks, keys, prompts, provider responses, emails, threads,
  attachments, URLs, paths, and customer identifiers are forbidden in logs.
- Automated verification does not call DeepSeek.
```

Mark the design `status: active`, update the task brief execution record with actual commits and fresh test evidence, and leave the user-triggered synthetic live diagnostic as the only deferred item.

- [ ] **Step 4: Run focused documentation and constraint checks**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest tests.test_deepseek_documentation_contracts tests.test_generate_project_status tests.test_static_linter_constraints tests.test_architecture_constraints tests.test_mechanical_rule_constraints -v
```

Expected: all focused documentation and mechanical tests pass.

- [ ] **Step 5: Generate project status**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B scripts\generate_project_status.py --output docs\operations\project_status_log.md
```

Expected: exit 0; the status log records the new files and current document counts without `.env`, key, email, or log content.

- [ ] **Step 6: Run complete post-generation verification**

Run:

```powershell
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest discover -s tests
& 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B scripts\maintenance_scan.py --output outputs\cleanup_report.md
node --check frontend\local_debug_page\app.js
node --check frontend\browser_extension\popup.js
node --check frontend\browser_extension\content\exmail_adapter.js
node --check frontend\browser_extension\shared\api_client.js
node --check frontend\browser_extension\shared\render_analysis.js
git diff --check
git status --short --ignored
```

Expected: full Python suite has zero failures; maintenance scan reports no findings; every JavaScript syntax command exits 0; diff check is clean; ignored `.env`, SQLite, outputs, and logs remain unstaged.

- [ ] **Step 7: Verify an isolated service without invoking DeepSeek**

Run:

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:EMAIL_AGENT_LLM_PROVIDER = 'disabled'
& $py -B scripts\manage_local_service.py start --host 127.0.0.1 --port 8878 --pid-file outputs\local_debug_service_verify.pid
try {
    & $py -B scripts\manage_local_service.py status --host 127.0.0.1 --port 8878 --pid-file outputs\local_debug_service_verify.pid
    Invoke-RestMethod -Uri 'http://127.0.0.1:8878/api/health' -Method Get
} finally {
    & $py -B scripts\manage_local_service.py stop --host 127.0.0.1 --port 8878 --pid-file outputs\local_debug_service_verify.pid
}
```

Expected: the isolated managed service reports `running`, health returns `ok=true`, cleanup stops it, and no analysis POST or DeepSeek request is made. After branch integration, restart the normal 8765 service from the main checkout so it retains the operator's existing backend-only `.env` configuration.

- [ ] **Step 8: Commit Task 5**

```powershell
git add docs/conventions/logging.md docs/operations/troubleshooting.md docs/operations/deployment_notes.md docs/api/backend_api_contract.md docs/operations/deepseek_fallback_diagnostics_task_brief.md docs/superpowers/specs/2026-07-13-deepseek-fallback-diagnostics-design.md docs/operations/project_status_log.md tests/test_deepseek_documentation_contracts.py
git commit -m "docs: document fallback diagnostics"
```

After this commit, do not perform the live synthetic analysis. Hand the user the exact test action and log-reading command; the user-triggered click may incur provider usage and is the next separately visible step.
