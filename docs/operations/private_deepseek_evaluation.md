---
last_update: 2026-07-20
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

## Documentation-only V2 gold-standard contract

This section is a documentation-only V2 contract for a future separately
authorized implementation. Task 9 does not implement V2 and does not open a real
V2 dataset. Current staging, build, verify, and run code continues to implement
only the V1 contract below.

V1 compatibility is mandatory: V1 datasets remain valid and readable through the
V1 path, a future reader must dispatch by the exact schema version, and there is
no in-place V1-to-V2 migration. A V2 build must create a new encrypted frame with
a fresh namespace, nonce, V2-specific purpose, and independently reviewed cases;
it must never rewrite or silently reinterpret a V1 dataset.

### Ordered deidentified evidence

`PrivateEvaluationCaseV2` replaces the single flattened thread field with an
immutable tuple of `DeidentifiedThreadSegmentV2` values. Segments are ordered
oldest-to-newest, have contiguous positions, use an opaque random segment ID, and
carry a fixed role such as `historical_message` or `current_message`. Exactly one
segment is the current message. Every segment is independently deidentified,
residual-scanned, bounded, and contains no raw mailbox identifier, address,
filename, URL, path, source hash, restoration value, or exact business identifier.

Each case is derived from one selected exact current raw record. After local
deidentification, that record appears exactly once as `current_message` and must not reappear as historical_message.
The current request must bind to that current_message segment. A missing,
duplicated, ambiguous, or differently bound current segment must fail closed
before reference authoring or candidate generation.

The case also contains reviewed attachment bindings as immutable
`ReviewedAttachmentBindingV2` values. Each binding uses an opaque random binding
ID, points only to an in-case segment ID, records a fixed attachment kind plus
content/truncation/limitation state, and carries bounded deidentified extracted or
visual evidence. It contains no binary, private locator, filename, URL, path,
cookie, token, mailbox ID, or content-derived hash. An attachment enters V2 only
after its text or visual evidence and its segment association receive current
business and privacy_security review; `parsed` status alone is not approval or a
semantic correctness label.

Both approvals bind one immutable attachment evidence-and-association revision; any evidence, truncation state, limitation, or segment association changes invalidates both approvals and must fail closed until independent reviewers have approved the new revision.

### Encrypted structured human gold

Each case binds an encrypted `StructuredHumanReferenceV2`. It records a bounded
human-authored current request, resolved historical decisions, cross-source
findings, required checks, expected category/risks/actions, reply constraints, and
opaque evidence bindings to the ordered segments or reviewed attachments. It may
not contain raw quotations or identifiers. Every material reference statement
must be evidence-bound, and the reference revision requires independent business and privacy_security approvals by distinct actors.

Strict candidate/reference separation applies. The structured reference is
authored, reviewed, approved, and cryptographically sealed before candidate generation.
Candidate generation receives only the approved deidentified evidence and cannot access or decrypt the reference, approvals, rubric, or prior verdict.
A reference author cannot see candidate output; a candidate cannot write, revise,
or approve the reference. The interactive comparison presents the same complete
deidentified evidence, the sealed reference criteria, and one unlabeled candidate
to a blinded human judge without provider and model identity, route, latency,
fallback label, or previous verdict. The judge remains a human decision maker;
model self-grading is prohibited.

Only aggregate-only reporting may persist. The prohibited artifacts include raw ChatGPT transcripts
used as source, reference, fixture, report, or training artifacts. A manually
consulted second opinion must be rewritten as a new structured human reference and
approved from the deidentified evidence; its transcript is not retained. The
prohibited operations include automatic training, automatic upload of a
dataset/reference as a training corpus, model self-grading, and any automatic production model switch.
A future training or V2
execution project requires a new written plan, authorization gate, implementation,
and offline review; this Task 9 documentation grants none of them.

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
`thread_text`, and attachments are empty. This is intentional V1 behavior, not the
future reviewed-attachment V2 contract. Any residual or callback failure rejects
the complete 200-case batch and writes no partial file.

The output suffix is exactly `.pkevalstage`. It uses AES-256-GCM, a fresh random
nonce, bounded atomic replacement, reparse rejection, and distinct magic,
purpose, and namespace from `.pkeval`, raw vault, and private knowledge. The
absolute path is outside the complete Project Container protected root,
OneDrive, system temp, raw vault, and every other private store. The protected
root is derived internally from freshly revalidated placement and cannot be
supplied or narrowed through CLI, config, request, or environment input.
Post-replacement validation excludes only the exact target
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
only raw-vault reader; in the latter, `build` reads only the reviewed `.pkevalstage`,
while `verify` and `run` read only the final `.pkeval`. The latter never imports or
reads the raw vault.

## Stage to final dataset build

```text
python -B -m scripts.evaluate_private_deepseek build --staging <external.pkevalstage> --dataset <external.pkeval>
```

`build` prompts once for the same operator-supplied 32-byte base64 key through
hidden `getpass`. It has no key flag, environment, `.env`, key-file, namespace,
force or overwrite surface. It decrypts only `EvaluationStageV1`, revalidates
exactly 200 unique cases, full category/language/direction/risk strata, current
business/privacy approvals, and at least 40 explicit Pro-pair approvals through
`EvaluationDatasetV1` plus deterministic selection.

The final dataset gets a fresh UUIDv4 `dataset_namespace`; it never reuses the
stage namespace. The final frame keeps `.pkeval` magic and
`private-evaluation-dataset/v1`, with a fresh random nonce, so stage/final magic,
HKDF purpose, namespace and nonce remain distinct even though the master key is
the same. The final target must be outside the complete Project Container
protected root, OneDrive, temp, raw vault, and every private store; it must not
exist and passes bounded descriptor,
reparse, parent/target identity and race checks. The publication helper's successful
return is the final commit point; code never rolls back or unlinks the target by
pathname. All reportable checks precede that point, and only best-effort internal-
stage cleanup follows. Pre-publication failure leaves no partial final file and the
reviewed stage is never deleted.

Build constructs zero provider clients and zero judge, performs zero network
calls, writes zero logs/transcripts/per-case files, and succeeds only with the
fixed identifier-free `dataset_built` / 200 result.

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
  supports them. Reads and legacy staged-overwrite writes revalidate the original
  and resolved path, reparse state, parent identity, and target identity before
  and after the sensitive operation. Create-only final publication performs all
  target validation before the atomic link and performs no target-identity check
  after the final commit point. On Windows these read, legacy-overwrite, and
  pre-publication identity checks are an in-process best-effort mitigation; the
  project does not claim absolute protection against an actor with the same user
  privileges who can race kernel namespace operations.
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

The synchronous local usefulness judge receives only repr-hidden
`UsefulnessJudgeView` and returns a boolean. The default live CLI returns
`human_judge_unavailable` before key or client construction unless the operator
supplies `--interactive-judge`, the exact confirmation, real local TTY stdin and
stdout, and one fixed exact-y readiness acknowledgement before key loading. The
adapter rejects ESC, C0/C1, bidi/format and other terminal controls before it
displays deidentified subject/thread and the
production-gated public summary/category/risk/action/draft fields, then reads one
exact lowercase `y` or `n`. Invalid input, EOF or terminal failure maps to fixed
`human_judge_failed` and stops before the next provider call. Provider and judge
exception text is not logged, serialized or included in repr.

The program creates no transcript, prompt/provider-output export, per-case JSON,
verdict file, cache or resume state. Only the aggregate report persists. It cannot
prevent external terminal or operating-system capture, so the real local TTY is a
private operator surface.

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
python -B -m scripts.evaluate_private_deepseek build --staging <external.pkevalstage> --dataset <external.pkeval>
python -B -m scripts.evaluate_private_deepseek verify --dataset <external.pkeval>
python -B -m scripts.evaluate_private_deepseek run --dataset <external.pkeval> \
  --report <aggregate.json> \
  --confirm-private-evaluation I_CONFIRM_200_FLASH_40_PRO \
  --interactive-judge
```

There are no model, endpoint, key, key-file, namespace, prompt, case, threshold,
retry, stream, batch, force/overwrite, transcript/export/save/output or
production-switch overrides.
Models are fixed to `deepseek-v4-flash` and `deepseek-v4-pro`; the endpoint is the
fixed backend endpoint. `verify` never creates a client. Only the script may
lazy-import the existing provider client factory after all local preflight. The
live key is obtained with hidden `getpass`, decoded as exactly 32 bytes, and the
mutable copy is wiped; invalid or missing input maps to `evaluation_key_unavailable`.

The exact `run` gate order is parse, explicit interactive flag, exact confirmation,
stdin/stdout TTY, fixed exact-y readiness acknowledgement, hidden key, dataset
decrypt/schema/selection, provider
configuration, client construction and calls. The runner remains sequential 20
Flash + 180 Flash / 40 approved Pro, zero retry, no automatic production model
switch, and aggregate-only persistence.
