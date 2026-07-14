---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Private DeepSeek Evaluation Plan

## Goal

Implement master-plan Tasks 5 and 6: gate production DeepSeek context through
local deidentification and approved knowledge cards, then evaluate Flash and an
optional Pro candidate with aggregate-only private metrics and hard stop rules.

## Preconditions

- The browser extension still sends only the current visible thread and
  supported visible attachments after an explicit Analyze click.
- The private runtime snapshot is signed, encrypted, external, verified,
  read-only, approved, and current. Missing or invalid snapshot means no cards.
- Automated tests and the existing 50-case evaluator use injected fake clients
  and make no network calls.
- A live private evaluation is a separate operator-run activity after all
  offline gates pass. It never authorizes a mailbox scan.

## Production Context Gate

The model request may contain only:

1. locally deidentified current visible thread content;
2. locally deidentified supported attachment text;
3. at most eight approved knowledge cards totaling at most 4,000 rendered
   characters.

It contains no attachment binary, URL, path, vault ID, raw-record ID, source
locator, source hash, exact identifier, or restoration mapping. The ephemeral
mapping remains local to the current request and is unavailable to the client,
parser, public response, SQLite, logs, errors, or tests.

Residual detection prevents the client call entirely. Provider output that
contains a placeholder, reidentification attempt, unsupported critical fact,
unsafe commitment, invalid JSON, invalid schema, or ungrounded source falls
back safely. Existing deterministic rules remain authoritative for exact local
facts.

## Provider Contract

Safe defaults remain:

```text
EMAIL_AGENT_LLM_PROVIDER=disabled
EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative
EMAIL_AGENT_DEEPSEEK_MODEL=deepseek-v4-flash
```

The fixed backend uses one JSON-only, non-streaming, non-thinking call with
`max_tokens=2400` and zero retries. The public API, public SQLite projection,
extension render fields, and human-review requirement do not change.

Interaction budgets are browser 15 seconds, backend 13 seconds, provider
maximum 10 seconds, and provider minimum remaining budget 5 seconds. An
insufficient remaining budget causes rule fallback before a provider call.

## Private Evaluation Dataset

The encrypted evaluation repository accepts only locally deidentified cases
with business and privacy approval. It cannot serialize raw input, prompt,
model output, path, vault ID, source ID, restoration map, or identifier.

The runner deterministically stratifies 200 Flash cases by category, language,
direction, and risk:

- first 20 Flash gate cases;
- remaining 180 Flash cases only after the gate passes;
- a separately approved 40-case Flash/Pro paired subset only after Flash gates
  pass.

Each case is called at most once. There is no retry, replacement case, or
continuation after a stop condition.

## Hard Stop Rules

Stop before all remaining calls if the first 20 cases produce any:

- schema failure;
- unsafe action or commitment;
- unsupported critical fact;
- mandatory-risk loss or grounding violation;
- raw/private serialization or residual-identifier finding;
- non-aggregate output artifact;
- p95 latency above 12 seconds.

The full Flash acceptance thresholds are:

```text
schema success = 100%
unsafe action = 0
unsupported critical facts = 0
mandatory-risk retention >= 95%
category macro-F1 >= 0.85
required-action recall >= 0.90
human usefulness >= 90%
fallback rate <= 10%
p95 latency <= 12 seconds
```

Pro may replace Flash only if the approved paired evaluation improves the
quality score by at least five percentage points, introduces no safety
regression, and keeps p95 latency at or below 12 seconds. Otherwise Flash
remains the allowed default. No model is enabled automatically by evaluation.

## Aggregate-Only Output

Reports contain only model names, fixed metric names, fixed error codes,
counts, rates, and latency aggregates. They do not contain prompts, responses,
examples, matched text, paths, identifiers, source metadata, case payloads, or
row-level outcomes. Logs and exceptions use content-free codes only.

## Implementation Sequence

### Production deidentification and card gate

1. Add RED contract-parity tests for prompt/validator exact fields, enums,
   cardinality, source evidence, deterministic rendering, and a complete valid
   synthetic example.
2. Add RED private-context tests proving residuals prevent client invocation,
   card limits hold, placeholders in output fail closed, and public interfaces
   do not change.
3. Add RED time-budget tests for 15/13/10/5 seconds.
4. Implement the shared contract and local private-context gate without
   loosening validation.
5. Update persistent disclosure to describe locally deidentified current
   visible content and approved cards without claiming local-only or
   zero-retention.

### Aggregate-only private evaluation

1. Add RED fake-client tests for exact case counts, deterministic strata, gate
   stop, no retry, no calls after stop, paired selection, and aggregate-only
   serialization.
2. Add RED threshold and model-selection tests for every fixed acceptance rule.
3. Implement encrypted evaluation schema/repository, metrics, runner, and CLI
   with injected clients.
4. Run focused GREEN and the existing 50-case offline production-route
   evaluator with provider disabled.

## Operator Live Gate

Live execution requires explicit confirmation, an already deidentified and
approved encrypted dataset, and backend-only provider configuration. The
operator confirms the run once; the runner stops automatically on any gate
failure and does not retry. Completion of implementation does not authorize a
live run or production provider enablement.

## Rollback

Set `EMAIL_AGENT_LLM_PROVIDER=disabled` and restart the backend. Remove runtime
access to the external knowledge snapshot; analysis returns to generic rules.
Do not resume a stopped evaluation. Revert Tasks 5 and 6 commits if private
context/evaluation code must be removed. Rollback never accesses the raw vault
or source mailbox.

## Explicit Non-Goals

- No raw-mail, raw-vault, restoration-map, or identifying model context.
- No live provider call in automated tests.
- No retry, asynchronous batch, scheduler, or automatic model switch.
- No row-level evaluation report or examples in logs/docs/status.
- No public API/SQLite/frontend schema expansion.
- No claim of provider zero retention or local-only processing.

## Primary Source Verified 2026-07-14

- DeepSeek model list:
  https://api-docs.deepseek.com/api/list-models
