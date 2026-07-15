---
last_update: 2026-07-15
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Private Evaluation Build and Interactive Judge Task Brief

## 1. Task name

Build the encrypted final private-evaluation dataset and add the explicit
real-TTY-only usefulness judge for Slice 2B.

## 2. Task type

`feature`

## 3. Current status

`completed`

This brief is the active Slice 2B contract. It supersedes only the older frozen
two-command/non-interactive assumptions; it does not rewrite the historical
execution record in `private_deepseek_evaluation_task_brief.md`.

## 4. Objective

Add fixed `build`, `verify`, and `run` module-entrypoint surfaces. `build` consumes
only the reviewed encrypted `.pkevalstage` and creates one strict encrypted
`.pkeval`. `run --interactive-judge` exposes an ephemeral real local TTY judge
that receives only `UsefulnessJudgeView`. Persist only the aggregate report.

## 5. Non-goals

- No network, live DeepSeek, IMAP, raw-vault, private-knowledge-store, DPAPI,
  BitLocker, public SQLite, browser or normal-runtime access during implementation.
- No transcript, per-case JSON, prompt/provider-output export, sample, cache,
  resume file, model override, retry, automatic switch or production mutation.
- No live evaluation, mailbox scan, status regeneration, maintenance scan or
  later-slice runtime/UI work.

## 6. Background and references

Binding references are `AGENTS.md`, the active 2026-07-15 six-slice plan,
`.superpowers/sdd/real-mailbox-task-2b-brief.md`, ADR 0006, the three active
constraint documents, and `docs/operations/private_deepseek_evaluation.md`.

Task 2A already creates an encrypted, deidentified `EvaluationStageV1` with
exactly 200 cases. The evaluator never receives raw mailbox or vault access.
The implementation base is `20a41de48d1c951df36df05f5adbfd924d92d749`.

## 7. Scope

- `backend/private_evaluation/dataset_builder.py`
- `backend/private_evaluation/staging_values.py`
- `backend/private_evaluation/terminal_judge.py`
- `backend/private_evaluation/terminal_text_safety.py`
- narrow create-only support in the existing final repository
- `scripts/evaluate_private_deepseek.py`
- focused unit and mechanical guards
- active constraints, ADR, evaluator runbook, testing/deployment notes, project
  structure, task template, logging rules and the active six-slice plan

## 8. Technical approach

`build` loads one hidden base64 key, decrypts only `EvaluationStageV1`, and
revalidates exactly 200 unique cases, full production strata, current business
and privacy approvals, and at least 40 explicit Pro-pair approvals through
`EvaluationDatasetV1` and deterministic selection. It generates a fresh UUIDv4
final namespace and uses the same operator-supplied 32-byte master key with
distinct final magic, HKDF purpose and random nonce.

The final target is create-only and in a separate project/OneDrive/temp/raw-vault/
private-store-external directory. Reparse, parent/target identity, race and write
failures leave no partial final file. Atomic no-clobber publication never overwrites
a post-validation racer; rollback removes only the exact published identity and
never a competitor. The stage is never automatically deleted.

`run` order is parse, explicit `--interactive-judge`, exact confirmation, real
local stdin/stdout TTY, fixed exact-y readiness acknowledgement, hidden key,
dataset decrypt/schema/selection, judge
construction, provider configuration, client construction and calls. The adapter
receives only `UsefulnessJudgeView`, displays deidentified input and
production-gated public output only after rejecting terminal control/format
characters, and accepts one exact lowercase y/n.

## 9. Data structures and interface changes

### Database changes

None. SQLite is forbidden for this domain.

### API changes

No public HTTP API change. The isolated CLI adds:

```text
python -B -m scripts.evaluate_private_deepseek build --staging <external.pkevalstage> --dataset <external.pkeval>
python -B -m scripts.evaluate_private_deepseek verify --dataset <external.pkeval>
python -B -m scripts.evaluate_private_deepseek run --dataset <external.pkeval> --report <external aggregate report> --confirm-private-evaluation I_CONFIRM_200_FLASH_40_PRO --interactive-judge
```

### AI output JSON and prompt changes

None. The runner continues to use the existing production gates and fixed prompt.

## 10. Security and privacy checklist

- [x] Stage and final frames use distinct magic, purpose, namespace and nonce.
- [x] Keys have only hidden getpass input and mutable-copy wiping.
- [x] Build creates zero provider, judge and network activity.
- [x] TTY judge input is exactly `UsefulnessJudgeView`.
- [x] Fixed exact-y readiness rejects EOF/cancel/invalid input before hidden key.
- [x] Terminal control/format characters fail before untrusted rendering.
- [x] Invalid input, EOF or terminal failure becomes fixed
  `human_judge_failed` before the next provider call.
- [x] No case/actor/dataset ID, path, key, raw JSON, approval, mapping or exception
  text enters fixed output, aggregate report, log or repr.
- [x] The program creates no transcript and documents that it cannot prevent
  external terminal capture.

## 11. Prompt injection protection

Stage case text remains untrusted data. The evaluator retains the single
production private-context, strict JSON, evidence, grounding, safety and public
merge path. Terminal text is displayed, never executed, logged or serialized.

## 12. Acceptance criteria

1. Stage-to-final synthetic round trip proves fresh namespace and distinct
   magic/purpose/nonce under the same key.
2. Invalid stage/key/tamper/count/coverage/approval/path/race/write conditions
   fail closed without a partial final file or stage deletion; atomic publication
   never overwrites or identity-cleanup-deletes a competitor.
3. Build and verify create zero provider/judge/network calls.
4. Run without flag, with wrong confirmation, non-TTY/redirection or readiness
   EOF/cancel/invalid input stops before key or client construction.
5. The judge accepts only exact y/n and failure stops before the next call.
6. Existing sequential 20 Flash + 180 Flash / 40 Pro, zero retry, no automatic
   production model switch and aggregate-only persistence remain green.
7. Import, CLI override, documentation, AST, diff and changed-file leakage guards
   pass using only synthetic/offline inputs.

## 13. Test plan

- Run focused dataset-builder, terminal-judge, CLI, repository, selection,
  runner and reporting suites.
- Run architecture/static/mechanical/documentation guards relevant to evaluation.
- Parse changed Python files with `ast`; no JavaScript files are expected.
- Run `git diff --check` and changed-file-scoped leakage only.
- Do not run maintenance scan, status regeneration, live provider, IMAP, raw
  vault, private dataset or ignored SQLite.

## 14. Rollback plan

Revert the single Slice 2B commit. Do not run `build` or `run`; leave provider
disabled. No mailbox, vault, database, browser or production-model rollback is
required because the implementation is isolated and default-off.

## 15. Human confirmation required

- [x] The user approved the six-slice plan and Slice 2B implementation.
- [x] The exact confirmation string remains fixed.
- [ ] A separate operator authorization is still required before any real key,
  stage, dataset, TTY judgment or provider call.
- [ ] Qualifying Pro remains only a candidate result and requires a separate
  production decision; there is no automatic switch.

## 16. Pre-execution checklist

- [x] Read `AGENTS.md`, project status, tooling/architecture/linter constraints,
  parent plan and complete Slice 2B brief.
- [x] Confirmed clean base `20a41de` and focused baseline.
- [x] Confirmed no new dependency or public/runtime schema change.
- [x] Confirmed strict RED before production implementation.
- [x] Confirmed live/mailbox/vault/provider/maintenance/status actions are out of
  scope.

## 17. Remote provider private-context checklist

- [x] Provider remains disabled by default and construction stays lazy.
- [x] Models remain fixed Flash/Pro with one sequential call, zero retry,
  non-streaming JSON-only options and fixed timeouts.
- [x] Every input/output retains the existing production privacy and safety gates.
- [x] No resolver, mapping, path, key, stage metadata or case identifier reaches
  provider or parser.
- [x] Automated tests use fake clients and no network.
- [x] The aggregate result cannot mutate production configuration.

## 18. Post-execution record

To be completed in `.superpowers/sdd/real-mailbox-task-2b-report.md` with the
commit hash, exact RED/GREEN commands, independent review, changed-file leakage
result and residual risks. No real mailbox, vault, private stage/dataset or
provider evidence may be copied into that report.
