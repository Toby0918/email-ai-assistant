---
last_update: 2026-07-13
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: product_spec
---

# DeepSeek Fallback Diagnostics Design

## Decision Summary

Add backend-only, sanitized diagnostics for DeepSeek attempts that end in the deterministic rule fallback. The diagnostics must identify the failing stage without recording any API key, prompt, email field, attachment text, provider response body, raw exception text, customer identifier, or private URL.

The public analysis API remains unchanged. Users continue to see `analysis_engine.source=rule_fallback`; an operator diagnoses the cause from the local rotating service log. This preserves the existing fail-closed behavior while making the provider path supportable.

The user approved this direction on 2026-07-13 by instructing Codex to execute the diagnostic patch. Written-spec review and implementation are complete; the only deferred item is the user-triggered synthetic live diagnostic after integration and restart.

## Pre-implementation Evidence

- The service is healthy and returns successful rule results.
- The effective local configuration is `provider=deepseek`, `model=deepseek-v4-flash`, `output_mode=model_led`, and a 25-second provider timeout.
- The configured key is present and has a plausible non-placeholder shape, but remote authentication has not been independently proven.
- The service started after the `.env` update, so a missed restart is not the leading explanation.
- DNS resolution and TCP port 443 connectivity to the fixed DeepSeek host work.
- `analysis_model_routes.py` currently converts budget exhaustion, provider failures, invalid provider output, evidence failures, safety rejection, schema failures, and language failures to the same rule result.
- `llm_client.py` currently converts almost every SDK exception to one generic client error.
- The Windows WMI service-launch path does not redirect process output, and the current service log is empty.

This evidence identifies an observability defect, not the final external provider failure. The patch must expose the sanitized failing stage before any provider-specific correction is attempted.

## Implementation Status

- The backend defines fixed reason/stage/provider/model/output-mode allowlists and canonicalizes caller-owned values before logging.
- Client failures map only from SDK exception classes and coarse HTTP status, without retaining or formatting the original exception.
- The analysis route has one terminal fallback helper and one production `log_analysis_fallback(...)` call site; every failure still returns the same complete rule fallback.
- The local entrypoint loads configuration, initializes a dedicated diagnostic sink, and then starts the loopback server.
- The diagnostic logger owns the active UTF-8 log at `outputs/local_debug_service.log`; it rotates at `1 MB` (`1_000_000` bytes) and keeps `two backups`.
- The public API, SQLite, frontend, prompt, provider context, and deterministic fallback remain unchanged.
- Automated tests use synthetic provider doubles and do not call DeepSeek.

## Considered Approaches

### Approach A: Sanitized internal diagnostic codes in a local rotating log

This is the approved approach.

- Classify failures at the provider, response, envelope, evidence, safety, schema, language, and budget boundaries.
- Log only allowlisted codes and non-sensitive runtime metadata.
- Configure the diagnostic logger to write its own rotating file so the behavior is reliable under the Windows WMI launcher without becoming an application or library log sink.
- Keep rule fallback behavior and the public API unchanged.

This provides enough evidence to select the next fix without weakening privacy or fail-closed behavior.

### Approach B: Log raw SDK exceptions and model output

Rejected. Raw exceptions can contain response bodies, request details, endpoints, account metadata, or other provider-supplied text. Model output can reproduce private email or attachment content. This approach conflicts with project logging and privacy rules.

### Approach C: Return diagnostics in the public API and render them in the extension

Rejected for this patch. It expands the public contract, exposes provider/account state to the browser, and creates a larger frontend and security review. Operator-local logs are sufficient for the immediate diagnosis.

## Diagnostic Contract

Every diagnostic event uses a fixed event name and allowlisted fields:

```text
event=analysis_fallback
code=<allowlisted reason code>
stage=<allowlisted stage>
provider=<allowlisted configured provider>
model=<allowlisted configured model label>
output_mode=<allowlisted configured mode>
elapsed_ms=<non-negative integer>
```

No diagnostic call accepts the email payload, prompt, attachment bundle, provider response, API key, raw exception, subject, sender, recipient, filename, source text, database record, or request URL.

Initial reason codes:

```text
provider_not_enabled
budget_exhausted
missing_key
unsupported_model
provider_timeout
provider_auth
provider_permission_or_balance
provider_rate_limit
provider_connection_error
provider_server_error
provider_http_error
provider_request_failed
response_incomplete
response_empty
envelope_invalid
evidence_invalid
safety_rejected_all
public_schema_invalid
public_language_invalid
unexpected_analysis_error
```

The logger records one terminal fallback event per analysis attempt. An accepted model result may record one `analysis_model_accepted` event with the same safe metadata, but it must not record generated content or facts.

## Component Design

### Provider client

`llm_client.py` retains sanitized `LlmClientError` messages and adds an allowlisted reason code. Known SDK exception classes and HTTP status groups map to the codes above. The raw SDK exception is never interpolated into a log message, public response, or new exception string.

HTTP status classification is limited to coarse operational groups: authentication, permission or balance, rate limit, server error, and other HTTP error. It does not record response headers or bodies.

### Analysis route

`analysis_model_routes.py` identifies the stage that failed:

- no remaining provider budget;
- provider client failure;
- incomplete or empty completion;
- internal envelope parse failure;
- evidence/source validation failure;
- no model-authored field surviving the safety merge;
- final public schema failure;
- final public language failure;
- unexpected analysis failure.

Only the fixed `response_incomplete` and `response_empty` reasons map to
`stage=response`; every other `LlmClientError` reason maps to `stage=provider`.

In conservative mode, `parse_legacy_result` performs JSON parsing, repair, and public schema validation only. The exported internal `validate_conservative_language` validator runs in a separate route `_run_stage`, so failures map to `public_schema_invalid` / `schema` and `public_language_invalid` / `language`, respectively.

It emits the terminal sanitized event and then returns the same complete deterministic rule fallback used today. Diagnostics must never change the returned analysis object.

### Logging configuration

`logging_config.py` configures `backend.email_agent.analysis_diagnostics` as a dedicated diagnostic sink. Its rotating UTF-8 file handler is never attached to the root logger. The diagnostic logger uses `propagate=False`, and both logger and handler use a fixed `WARNING` threshold independent of the configured general service level. Rotation under `outputs/local_debug_service.log` uses `maxBytes=1_000_000` (`1 MB`) and `backupCount=2` (`two backups`). No dependency is added.

The handler accepts only the exact fallback-event template with exact built-in allowlisted arguments and a non-negative built-in integer. It rejects records from OpenAI, HTTPX, HTTP core, arbitrary application loggers, child loggers, direct free-form diagnostic messages, non-WARNING records, string subclasses, booleans, exceptions, and stack information. Reconfiguration replaces and closes the prior diagnostic handler, leaving exactly one writer. File mode installs one rotating handler; no-file mode installs one filtered diagnostic stream handler. A canonical fallback is therefore written exactly once whether the configured general level is DEBUG, INFO, WARNING, ERROR, CRITICAL, or an invalid level.

`run_local_debug.py` loads backend configuration, initializes the diagnostic sink before starting the HTTP server, and then starts the same loopback-only service. Because the diagnostic logger owns the file handler, Windows WMI startup no longer depends on inherited stdout or stderr redirection.

The existing service manager remains responsible only for lifecycle, PID, health, and attachment cleanup. It must not read or print `.env` values.

## Public And Persistence Boundaries

- No public request field changes.
- No public response field changes.
- No SQLite schema or stored-analysis changes.
- No frontend changes.
- No prompt or provider context changes.
- No retry is added.
- No paid API call is added to automated tests.
- No diagnostic content is persisted in SQLite.

## Privacy And Security Requirements

- Never log an API key, token, authorization value, cookie, prompt, raw provider exception, response body, email body, subject, sender, recipient, thread content, attachment name, attachment text, source ID, private URL, local attachment path, commercial amount, or customer identifier.
- Never use `logger.exception` for expected provider or validation fallback paths because its traceback can include unsafe exception representations.
- Use fixed message templates and allowlisted enum-like values.
- Treat logging failure as an operational startup problem; it must not weaken provider validation or expose raw data through an alternate channel.
- Preserve explicit-click gating, current-visible-message scope, backend-only key storage, human review, and all no-mailbox-action rules.

## Testing Strategy

Use test-driven development with synthetic values only:

1. Client tests prove each safe provider failure category and prove raw exception text is absent.
2. Route tests prove budget, envelope, evidence, safety, schema, language, and unexpected failures produce the intended code while returning the exact rule fallback.
3. Logging tests prove the dedicated rotating handler writes safe events, rejects SDK/HTTP/application/private direct records, remains independent of every configured general level, and never sits on the root logger.
4. Entrypoint tests prove logging is configured before the server starts and uses the configured level.
5. Regression tests prove accepted model output still reports `ai_model`, failed output still reports `rule_fallback`, and no second provider attempt occurs.
6. Static/mechanical tests scan the diagnostic implementation for raw exception interpolation and sensitive-field logging.
7. Full unit, documentation, maintenance, and syntax checks run after the focused tests.

No automated or Codex-run live DeepSeek call is permitted. After the patch and service restart, the user performs one synthetic Analyze action. The next decision is based on the emitted reason code.

## Operational Test Flow

1. Restart the local service so the new logging configuration is active.
2. Confirm `/api/health` returns success.
3. Clear or note the current end of `outputs/local_debug_service.log` without deleting historical user data.
4. Submit the existing synthetic email through the local page or synthetic PowerShell request.
5. Read only the newest `analysis_fallback` or `analysis_model_accepted` event.
6. If the result is `analysis_model_accepted`, confirm the public engine is `ai_model` and begin a separate synthetic accuracy evaluation.
7. If it is a fallback code, correct only that root cause and repeat once.

## Acceptance Criteria

1. A DeepSeek fallback produces exactly one sanitized terminal reason code in the local service log.
2. Authentication, permission or balance, rate limit, connection, timeout, server, response, envelope, evidence, safety, schema, language, and budget failures are distinguishable where the code boundary has evidence.
3. The log contains no key, prompt, email or attachment content, raw exception, response body, private URL, or customer identifier.
4. Windows-managed service startup writes application diagnostics to `outputs/local_debug_service.log`.
5. The public API, SQLite schema, frontend, prompt, and deterministic fallback remain unchanged.
6. Automated tests use only synthetic inputs and perform no live provider call.
7. Focused tests, full `unittest` discovery, static/architecture/mechanical guards, documentation checks, maintenance scan, project-status generation, and `git diff --check` pass before completion.
8. The dedicated diagnostic sink has one filtered writer, does not propagate to root, and emits exactly one canonical event for DEBUG through CRITICAL and invalid general levels.

Implementation and offline release verification do not perform the user-visible synthetic Analyze action. That single user-triggered live diagnostic remains deferred because it can consume provider usage.

## Rollback

Revert the diagnostic and logging commits. Provider behavior remains safe during rollback because the existing rule fallback is unchanged. Independently, setting `EMAIL_AGENT_LLM_PROVIDER=disabled` and restarting restores rule-only operation.
