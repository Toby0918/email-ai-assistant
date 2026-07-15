---
last_update: 2026-07-15
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Private DeepSeek Evaluation Contract

## Boundary

The private evaluator is an administrator-run, project-external, aggregate-only
workflow. It is not a browser feature, normal backend route, scheduled job, raw
mailbox reader, knowledge authority reader, or production model switch. Automated
tests use synthetic fake clients only. The evaluator never serializes a rendered
prompt, raw input, provider response, case-level outcome, human-judge view, or
source sample.

## Reviewed evaluation staging

The administrator creates the evaluator handoff only through local
`stage-evaluation`; it is not in `NETWORK_COMMANDS` and requests no mailbox app
password. `StageEvaluationSelectionV1` contains exactly 200 unique reviewed
record/case bindings plus vault ID, authorization `scope_fingerprint`, reviewed
`inventory_fingerprint`, rolling window, expiry, current-revision approvals,
production stratum, and expected enum metadata. It contains no subject, body,
address, filename, locator, or source content.

Each selected raw record is opened one record at a time inside the administrator
vault CLI, structurally deidentified, residual-scanned, converted to one
`PrivateEvaluationCaseV1`, then closed together with its restoration mapping
before the next record. The evaluation-only source validates each record's
inventory fingerprint before plaintext release, performs no evidence accumulation,
and retains no domain, message/thread ID, or other raw-derived identifier across
records. The final case uses fixed identifier-free subject,
sender, recipients, and time values; only the deidentified full mail text enters
`thread_text`, and attachments are empty. Any residual or callback failure rejects
the complete 200-case batch and writes no partial file.

The output suffix is exactly `.pkevalstage`. It uses AES-256-GCM, a fresh random
nonce, bounded atomic replacement, reparse rejection, and distinct magic,
purpose, and namespace from `.pkeval`, raw vault, and private knowledge. The
absolute path is outside the project, OneDrive, system temp, raw vault, and every
other private store. Post-replacement validation excludes only the exact target
from the descendant scan; sibling and descendant stores remain rejected. The
32-byte staging/evaluation key comes only from hidden
interactive base64 input; it has no flag, environment, `.env`, key-file, stdout,
log, repr, exception, or persistence surface, and mutable copies are wiped.
Success is exactly `evaluation_stage_complete` with 200 accepted and zero
rejected. Failure output is a fixed code/count only, and parser/local validation
is exactly `argument_invalid`.

```text
python -B -m scripts.manage_mailbox_vault stage-evaluation --vault <external-vault> --authorization-id <non-sensitive-id> --account <authorized-account> --selection-manifest <absolute-reviewed.json> --staging-dataset <external.pkevalstage>
```

Only `scripts/manage_mailbox_vault.py` and `scripts.evaluate_private_deepseek.py`
bridge the evaluation package: the former may use only staging modules and is the
only raw-vault reader; the latter reads only a separately built final `.pkeval`
and never imports or reads the raw vault.

## Encrypted dataset

- Suffix: `.pkeval`; schema: `PrivateEvaluationDatasetV1`.
- AES-256-GCM frame: magic `PKEVAL01`, version `1`, 12-byte random nonce,
  16-byte tag, maximum 8 MiB.
- Independent mutable 32-byte key and UUIDv4 namespace.
- HKDF-SHA256 derives 32 bytes with namespace UUID bytes as salt and exact info
  `private-evaluation-dataset/v1`; AAD is the complete frame header plus that
  purpose string.
- Wrong key, namespace, magic, version, length, purpose, nonce or tag fails with
  a fixed content-free code.
- The absolute file path must be outside the project, OneDrive and system temp,
  contain no reparse component, and not overlap a raw vault or another private
  store. The key has no CLI/env argument and is wiped from a mutable copy.
- Dataset reads use a bounded descriptor and no-follow flags where the platform
  supports them. Reads and staged atomic writes revalidate the original and
  resolved path, reparse state, parent identity, and target identity before and
  after the sensitive operation. On Windows these pre/post identity checks are
  an in-process best-effort mitigation; the project does not claim absolute
  protection against an actor with the same user privileges who can race kernel
  namespace operations.
- Descendant marker discovery reads directory metadata only, never file content;
  a reparse point, inaccessible entry, depth/entry bound, or metadata error fails
  closed instead of weakening raw-vault/private-store separation.

The dataset contains exactly the keys `schema_version`, `dataset_namespace`, and
`cases`, with 200 to 1000 unique cases. Each `PrivateEvaluationCaseV1` contains
exactly `schema_version`, `case_id`, `revision`, `approvals`, `stratum`,
`deidentified_email`, and `expected`.

Approvals are current-revision `business` and `privacy_security` approvals by
distinct actors, plus nullable `pro_pair`. Strata use production category and
risk enums, `zh-CN|en`, `inbound|outbound|thread`, and risk or `none`.
Deidentified email fields are exactly `subject`, `sender`, `recipients`, `cc`,
`sent_at`, `thread_text`, and `attachments`; attachment fields are only `kind`
and `text`, with `image|pdf|xlsx|docx`. Expected fields are exactly `category`,
`mandatory_risk_types`, and `required_action_types`.

All text is bounded UTF-8, already placeholderized, idempotently safe under the
Task 4 residual scanner, and contains no real name, address, email/domain/phone,
URL, path, filename, message/attachment/order/invoice/tracking identifier,
exact amount/date, source hash, vault/authority/card ID, or restoration data.
The repository stores only this structured encrypted data.

## Selection

Selection derives a separate HMAC key with HKDF-SHA256, namespace salt and exact
info `private-evaluation-selection/v1`. It groups by all four stratum fields,
sorts cases by `HMAC-SHA256(key, b"case/v1\0" + case_id_utf8)` then case ID,
sorts groups by the corresponding HMAC of `b"stratum/v1\0"` plus canonical
stratum JSON, and round-robins groups until exactly 200 are selected.

The first 20 form the Flash gate; the remaining 180 run only after gate PASS.
The 40 paired cases are selected from valid `pro_pair` cases inside the same 200
using the same round-robin method and label `pair/v1\0`. Fewer than 40 fails
before calls. There are exactly 200 Flash calls and, only after Flash acceptance,
40 Pro calls. The pair phase reuses cached Flash outcomes, is sequential and
non-streaming, and has zero retry, replacement or repeated Flash call.

## Production gates

Each case is rendered from its structured deidentified fields. Runner invokes
the exact Task 5 `build_private_model_context` and
`provider_output_is_private_safe` gates with no skip, bypass, mapping, resolver
or alternate provider path. Runtime cards are an externally verified immutable
tuple and default empty. The runner then applies the production strict DeepSeek
schema, evidence, grounding, model-text safety, public merge and public-schema
predicates. Inputs containing placeholders remain idempotent; provider outputs
containing placeholders or private markers fail privacy.

The injected synchronous local usefulness judge receives only repr-hidden
in-memory views and returns a boolean. The default live CLI has no judge adapter
and returns `human_judge_unavailable` before any provider client is constructed.
Provider and judge exceptions map to fixed codes; their text is not logged,
serialized or included in repr.

## Gates and metrics

Any schema, safety, grounding, privacy or aggregate-serialization violation in
the first 20 cases stops immediately. After 20 complete Flash outcomes, nearest-
rank p95 greater than 12.0 seconds stops. Flash acceptance after all 200 requires:

- schema success `1.00`;
- unsafe action/unconditional commitment count `0`;
- unsupported critical fact count `0`;
- mandatory-risk micro recall at least `0.95`;
- fixed-production-enum category macro-F1 at least `0.85`;
- required-action micro recall at least `0.90`;
- human usefulness at least `0.90`, including fallbacks in the denominator;
- fallback rate at most `0.10`;
- end-to-end nearest-rank p95 at most `12.0` seconds.

Quality is the equal mean of risk recall, macro-F1, action recall and usefulness.
Pro qualifies only when paired quality improves by at least `0.05`, Pro schema is
`1.00`, unsafe and unsupported counts are zero, mandatory-risk recall does not
regress versus paired Flash, and Pro p95 is at most `12.0` seconds. The evaluator
reports `pro_candidate_qualified`; it never changes production configuration.

## Aggregate report

The exact top-level keys are:

```text
schema_version, status_code, models, counts, metrics,
error_code_counts, decision_code
```

Values are fixed strings/model names, integers, finite numbers, or null. Status
codes are `blocked`, `gate_stopped`, `flash_complete`, and `comparison_complete`.
Decision codes are `not_evaluated`, `gate_failed`, `flash_rejected`,
`retain_flash`, and `pro_candidate_qualified`.

Allowed error counts are:

```text
operator_confirmation_required
dataset_unavailable
evaluation_key_unavailable
dataset_decrypt_invalid
dataset_schema_invalid
dataset_case_count_invalid
dataset_strata_incomplete
pair_approval_insufficient
provider_configuration_unavailable
human_judge_unavailable
human_judge_failed
provider_error
schema_violation
safety_violation
grounding_violation
privacy_violation
latency_gate_failed
aggregate_serialization_violation
fallback_observed
```

Reports must not contain any case, namespace or actor ID, timestamp, path, row,
stratum, prompt, input, response, matched text, source or sample. Writes use an
atomic same-directory replacement.

## CLI

```text
python -B -m scripts.evaluate_private_deepseek verify --dataset <external.pkeval>
python -B -m scripts.evaluate_private_deepseek run --dataset <external.pkeval> \
  --report <aggregate.json> \
  --confirm-private-evaluation I_CONFIRM_200_FLASH_40_PRO
```

There are no model, endpoint, key, prompt, case, threshold or retry overrides.
Models are fixed to `deepseek-v4-flash` and `deepseek-v4-pro`; the endpoint is the
fixed backend endpoint. `verify` never creates a client. Only the script may
lazy-import the existing provider client factory after all local preflight. The
live key is obtained with hidden `getpass`, decoded as exactly 32 bytes, and the
mutable copy is wiped; invalid or missing input maps to `evaluation_key_unavailable`.
