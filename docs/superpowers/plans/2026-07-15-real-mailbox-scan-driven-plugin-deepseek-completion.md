---
last_update: 2026-07-15
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Real Mailbox Scan-Driven Plugin and DeepSeek Completion Plan

## Goal

Deliver the user-approved completion work in six independently reviewable
slices while preserving the existing administrator-only mailbox exception,
normal click-only browser runtime, private-data isolation, and default-disabled
provider posture.

## Global constraints

- The mailbox workflow remains manual, administrator-only, default-off, limited
  to one authorized account, fixed `imap.exmail.qq.com:993`, verified TLS, and a
  rolling 24-month window.
- The IMAP surface remains read-only and allowlisted. There is no scheduled job,
  polling loop, SMTP, flag mutation, arbitrary command, browser mailbox scan, or
  normal-backend mailbox route.
- The binding content rule is **no raw mail to Codex, DeepSeek, Git, or public SQLite**.
  Raw or identifying content remains only in the encrypted, project-external
  vault and never enters repository artifacts or public output.
- A code/test/plan approval never satisfies the separate live credential and fingerprint gate.
  Live credentials are entered interactively only after local preflight;
  `inventory` is content-free; the operator must stop and separately confirm its
  unchanged inventory fingerprint before `scan`.
- Automated tests remain offline and synthetic. They do not access IMAP, an
  external vault, a private dataset, DPAPI/BitLocker host state, or a provider.
- No slice adds a dependency unless a later approved brief explicitly requires
  it and its dependency test is RED first.

## Operator entrypoints

All runnable administrator commands start from the project root with one of:

```text
python -B -m scripts.manage_mailbox_vault ...
python -B -m scripts.manage_private_knowledge ...
python -B -m scripts.evaluate_private_deepseek ...
```

Architecture prose may continue to name the corresponding `.py` files. Operator
examples must not execute those files by path or depend on `PYTHONPATH`.

## Slice 1: Administrator entrypoints and governance

### Deliverables

- Add the tracked task brief and this tracked plan.
- Add a focused project-root subprocess contract for all three module
  entrypoints with `PYTHONPATH` removed.
- Use parser help for the two management CLIs. Use an invalid argument for the
  evaluator and require its fixed `argument_invalid` JSON because it has no help
  surface.
- Standardize relevant testing, deployment, and evaluator documentation on the
  module forms.
- Make `STOP after inventory` an explicit operator gate.

### Stop condition

Do not implement later-slice behavior. Verify and commit only the entrypoint and
documentation contract.

## Slice 2: Evaluation staging, dataset build, and interactive judge

### Deliverables

- Add the separately reviewed `stage-evaluation` handoff without granting the
  evaluator access to the raw vault.
- Add the bounded encrypted evaluation dataset `build` path and its offline
  validation gates. It consumes only `EvaluationStageV1`, requires exactly 200
  cases with complete strata/dual approvals and at least 40 Pro approvals, and
  creates a fresh UUIDv4 final namespace in a separate external directory with
  the same operator-supplied 32-byte hidden key but distinct final crypto.
- Add an explicit local interactive usefulness-judge adapter that remains
  non-serialized and unavailable by default. Only `run --interactive-judge` with
  exact confirmation, a real local TTY and a fixed exact-y readiness acknowledgement
  may enable it; the adapter receives only `UsefulnessJudgeView`, rejects terminal
  control/format characters, accepts one exact y/n, and creates no transcript.
- Keep automated tests on synthetic encrypted data and fake clients.
- Preserve 20 Flash + 180 Flash / 40 Pro, zero retry, aggregate-only persistence,
  and no automatic production model switch.

### Stop condition

Do not run a live evaluation, expose case-level output, or switch the production
model. Provider use remains separately authorized.

## Slice 3: Read-only runtime knowledge snapshot bootstrap

### Deliverables

- Add the normal-runtime bootstrap for the already verified, encrypted,
  read-only knowledge snapshot.
- Fail closed to immutable empty runtime cards and generic rules for every
  missing, invalid, expired, or inaccessible snapshot condition.
- Preserve the backend-only immutable `runtime_cards=()` seam and keep paths,
  keys, bootstrap state, vault state, and private metadata out of public output.

### Stop condition

Do not add a write path to normal runtime or broaden mailbox/provider access.

## Slice 4: Tencent context extraction, privacy diagnostics, and rule facts

### Deliverables

- Add only the approved Tencent current-message context extraction, preserving
  explicit-click and visible-current-message bounds.
- Add content-free privacy diagnostics without matched text, identifiers,
  paths, prompts, responses, or exception details.
- Add the approved deterministic rule facts and focused parity tests without
  treating mailbox content as instructions.

### Stop condition

Do not add background enumeration, another-message access, automatic mailbox
actions, or new public diagnostic fields.

## Slice 5: Task-card extension UI

### Deliverables

- Add the approved task-card presentation to the extension.
- Keep every generated action advisory and subject to human review.
- Preserve stale-message revalidation, current-message scoping, persistent
  provider disclosure, and the ban on send/delete/archive/move/reply actions.

### Stop condition

Do not change mailbox permissions, add an automatic action, or expose private
runtime metadata.

## Slice 6: Full verification, project status, and live inventory readiness

### Deliverables

- Run focused suites, the full offline suite, documentation/front-matter,
  architecture, transport, static, maintenance, and leakage guards.
- Regenerate `docs/operations/project_status_log.md` only in this final slice.
- Record readiness without claiming a live mailbox, vault, dataset, or provider
  run occurred.
- Prepare the operator for the separately authorized inventory-only readiness
  step using the module entrypoint.

### Stop condition

Stop before credential entry or any live connection. A local operator may later
authorize inventory only; after inventory the workflow stops again for review
and explicit fingerprint confirmation. `scan` is never implied by readiness.

## Verification and review cadence

Each slice follows test-first RED/GREEN, focused verification, diff review, and
one task-scoped commit. Critical or important review findings are fixed within
the same slice before the next slice starts. New natural-language edge cases
that expand the approved slice are deferred rather than silently widening it.

## Completion definition

Offline completion means all six slices and their guards pass, the status log is
current, and live readiness is documented. It does not mean a mailbox was
connected, a credential was entered, raw content was read, a vault was opened,
a private evaluation ran, or DeepSeek was called.
