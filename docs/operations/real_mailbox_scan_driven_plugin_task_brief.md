---
last_update: 2026-07-15
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Real Mailbox Scan-Driven Plugin and DeepSeek Completion Task Brief

## 1. Task name

Standardize administrator module entrypoints and establish the governance
contract for the approved six-slice real-mailbox-scan-driven plugin and DeepSeek
completion program.

## 2. Task type

`docs`

## 3. Current status

`implemented`

Task 1 is implemented offline. This status does not authorize a live mailbox
connection, external-vault operation, private dataset read, credential entry,
or DeepSeek request.

## 4. Objective

Make all administrator tools runnable from the project root through stable
module entrypoints, record the six approved implementation slices, and make the
post-`inventory` human stop an executable documentation contract. Preserve the
separation between the administrator-only mailbox workflow and the normal
click-only browser runtime.

## 5. Non-goals

- Do not connect to IMAP or enter a mailbox credential.
- Do not open an external vault or private evaluation dataset.
- Do not call DeepSeek, OpenAI, Ollama, Qwen, Gemma, or another provider.
- Do not implement `stage-evaluation`, evaluation dataset `build`, runtime
  snapshot bootstrap, Tencent extension extraction, new diagnostics, rule-fact
  behavior, or task-card UI changes.
- Do not change the public API, SQLite schema, AI output JSON, prompts, browser
  permissions, mailbox actions, provider defaults, or dependencies.
- Do not regenerate `docs/operations/project_status_log.md`; that belongs to
  Slice 6.

## 6. Background and references

The repository already contains isolated mailbox-ingest, private-knowledge, and
private-evaluation packages. The user approved a six-slice completion program
and explicitly authorized work on `master`, while retaining a separate live
authorization gate.

Binding references:

- `AGENTS.md`
- `docs/operations/project_status_log.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/operations/authorized_mailbox_ingest_task_brief.md`
- `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`
- `docs/templates/agent_task_brief_template.md`
- `docs/superpowers/plans/2026-07-15-real-mailbox-scan-driven-plugin-deepseek-completion.md`

## 7. Scope

Task 1 adds or updates only:

- administrator module-entrypoint subprocess and documentation tests;
- the tracked six-slice task brief and implementation plan;
- testing, deployment, and private-evaluation operator documentation;
- the existing rollout-closeout documentation contract.

The administrator entrypoints are exactly:

```text
python -B -m scripts.manage_mailbox_vault ...
python -B -m scripts.manage_private_knowledge ...
python -B -m scripts.evaluate_private_deepseek ...
```

Architecture prose may still name a `scripts/manage_*.py` file. Runnable
operator examples must use the module forms above and must not rely on an
ambient `PYTHONPATH`.

## 8. Technical approach

### Slice 1: Administrator entrypoints and governance

Prove all three module entrypoints reach their parsers from the project root
without `PYTHONPATH`, standardize operator examples, and lock the inventory stop
gate in tests and docs.

### Slice 2: Evaluation staging, dataset build, and interactive judge

Later work adds the separately reviewed evaluation handoff, bounded encrypted
dataset build, and local non-serialized interactive judge. It is not part of
Task 1.

### Slice 3: Read-only runtime knowledge snapshot bootstrap

This slice adds a fail-closed, startup-only read-only runtime snapshot bootstrap
with immutable empty-card fallback. It remains disabled by default, runs once
before server start, and exposes no reload, polling, hot update, or status
endpoint. It does not expand Task 1 mailbox access or public schemas.
The configured snapshot alias and its prevalidated target remain separate through
the descriptor-bound read, while reserved private-knowledge request fields are
removed before either analyzer branch so untrusted payloads cannot reach the
internal runtime seam.

### Slice 4: Tencent context extraction, privacy diagnostics, and rule facts

Later work adds only the approved click-scoped Tencent context, content-free
diagnostics, and deterministic rule facts. It is not part of Task 1.

### Slice 5: Task-card extension UI

Later work adds the human-reviewed task-card presentation without mailbox
actions or permission expansion. It is not part of Task 1.

### Slice 6: Full verification, project status, and live inventory readiness

Later work performs full offline verification, regenerates project status, and
stops before live credential entry. Readiness never implies `scan` approval.

Across all slices, the mailbox exception remains manual, administrator-only,
default-off, limited to one authorized account at fixed
`imap.exmail.qq.com:993`, verified TLS, and a rolling 24-month window. Transport
remains read-only: `LIST`, `EXAMINE`, `UID SEARCH`, and bounded `UID FETCH` with
`BODY.PEEK`. There is no schedule, background poller, SMTP, flag mutation,
arbitrary IMAP command, browser mailbox scan, or normal-backend mailbox route.

The binding content rule is **no raw mail to Codex, DeepSeek, Git, or public SQLite**.
Raw or identifying content may exist only in the authorized encrypted,
project-external vault and must not enter repository artifacts or public output.

## 9. Data structures and interface changes

### Database changes

None.

### API changes

None.

### AI output JSON changes

None.

### Prompt changes

None.

### Operator interface changes

Documentation and tests standardize runnable commands on the three module
entrypoints listed in Section 7. Existing CLI commands and arguments are
unchanged.

## 10. Security and privacy checklist

- [x] Task 1 adds no mailbox connection, credential entry, vault operation, or
  private dataset operation.
- [x] No automatic send, delete, archive, move, forward, reply, scan, or model
  action is added.
- [x] No API key, mailbox credential, token, raw message, private identifier, or
  real attachment is added to Git, docs, tests, logs, or public SQLite.
- [x] The administrator workflow remains one-account, fixed-endpoint,
  rolling-24-month, manual, and default-off.
- [x] `inventory` remains content-free and precedes any bounded content scan.
- [x] `scan` still requires the unchanged inventory fingerprint through
  `--confirm-inventory-fingerprint`.
- [x] Automated Task 1 tests use parser-only subprocesses and synthetic/static
  contracts; they do not call a provider or mailbox.
- [x] Later live operation still requires the separate live credential and fingerprint gate.

## 11. Prompt injection protection

Task 1 does not change a prompt, parser, analysis request, or model path. The
existing protections remain binding:

- mailbox subject, body, headers, filenames, and attachment text are untrusted
  data rather than system instructions;
- no instruction embedded in mailbox content is executed;
- system prompts, credentials, other messages, vault material, private mappings,
  and provider configuration are not disclosed;
- generated text cannot automatically commit the user to price, delivery,
  payment, contract, quality, or legal terms.

## 12. Acceptance criteria

1. All three module entrypoints reach their parser from the project root after
   `PYTHONPATH` is removed.
2. The two management CLIs expose parser help without accessing IMAP or a vault.
3. The evaluator invalid-command probe returns only fixed
   `{"code": "argument_invalid", "ok": false}` JSON and does not use a help,
   dataset, credential, judge, or provider path.
4. Runnable administrator examples use only the approved module entrypoints.
5. Each relevant operator document orders the gate as module `inventory`, then
   `STOP after inventory`, then fingerprint-confirmed module `scan`.
6. This brief contains all 18 filled sections with one task type and a canonical
   current status.
7. Documentation/front-matter, architecture, mailbox-transport, static, and
   focused Task 1 guards pass offline; `git diff --check` is clean.

## 13. Test plan

- Run the focused administrator module-entrypoint contract.
- Run the focused ordering-hardening test after reviewer-requested coverage is
  added; because the documents are already correct, record it as hardening and
  do not claim a RED cycle.
- Run rollout-closeout and documentation/front-matter guards.
- Run architecture, mailbox-transport, and static-linter guards.
- Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and
  `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative` during verification.
- Do not rerun the whole-workspace maintenance scan in this review fix because
  it would reopen the known ignored SQLite artifact; use no mailbox, vault,
  dataset, or provider action.

## 14. Rollback plan

Revert the Task 1 commits. No database migration, vault mutation, credential
cleanup, runtime configuration rollback, provider rollback, or browser rollback
is required because Task 1 changes only docs and tests.

## 15. Human confirmation required

- [x] The user approved the six-slice implementation program.
- [x] The user explicitly authorized Task 1 work on `master`.
- [x] The user confirmed the reviewer-requested ordering hardening.
- [ ] Before any live action, a local operator must provide separate written
  authorization, validate one account and the external encrypted storage
  controls, and approve credential entry.
- [ ] The first separately authorized live action is `inventory` only.
- [ ] After `inventory`, the operator must stop, review the content-free result,
  and explicitly confirm the unchanged fingerprint before any `scan`.

No unresolved human decision remains for the offline Task 1 implementation.

## 16. Pre-execution checklist

- [x] Read `AGENTS.md`.
- [x] Read `docs/operations/project_status_log.md`.
- [x] Read the active tooling, architecture, and linter constraints.
- [x] Read the task-brief template and relevant mailbox governance documents.
- [x] Confirmed the Task 1 objective, non-goals, exact files, and stop boundary.
- [x] Confirmed no new dependency or runtime implementation is required.
- [x] Confirmed tests must be offline and use only parser/static/synthetic paths.
- [x] Confirmed no live mailbox, external vault, private dataset, credential, or
  provider action is authorized.

## 17. Remote provider private-context checklist

Task 1 does not change remote AI input or runtime knowledge. These existing
constraints were checked and remain unchanged:

- [x] Provider remains disabled by default; DeepSeek output mode remains
  conservative by default.
- [x] Every remote path retains the single backend-only deidentification and
  residual-scan gate.
- [x] `runtime_cards` remains an immutable empty tuple by default and accepts
  only verified `RuntimeKnowledgeCard` values.
- [x] No environment, path, key, bootstrap, vault, DPAPI, BitLocker, or frontend
  field crosses the runtime seam.
- [x] Reserved private-knowledge payload fields are removed before injected and
  default analyzer dispatch while ordinary current-email fields remain intact.
- [x] The original snapshot alias is revalidated against the prevalidated target
  before descriptor open and after the bounded read.
- [x] Knowledge rendering remains identifier-free, deterministic, at most eight
  cards, and at most 4,000 characters.
- [x] Resolver and mapping remain closed before the provider call and cannot
  reach provider, parser, API, SQLite, logs, or exceptions.
- [x] Provider-output placeholders, restoration hints, and private metadata
  markers remain rejected before parsing.
- [x] Public API, SQLite, frontend renderer, and diagnostic schema remain
  unchanged.
- [x] Privacy and budget failures retain the existing fixed safety and budget
  diagnostics.
- [x] Backend/provider/parser/minimum/reserve/frontend budgets remain exactly
  `13/10/8/5/2/15` seconds.
- [x] Persistent pre-click disclosure remains unchanged.
- [x] Verification remains offline and does not call a live provider, mailbox,
  vault, DPAPI, or BitLocker operation.

## 18. Post-execution record

Actual tracked Task 1 files:

- `docs/operations/deployment_notes.md`
- `docs/operations/private_deepseek_evaluation.md`
- `docs/operations/real_mailbox_scan_driven_plugin_task_brief.md`
- `docs/operations/testing_checklist.md`
- `docs/superpowers/plans/2026-07-15-real-mailbox-scan-driven-plugin-deepseek-completion.md`
- `tests/test_administrator_module_entrypoints.py`
- `tests/test_rollout_closeout_contracts.py`

Recorded verification before review hardening:

- focused Task 1 and closeout contracts: 9 tests passed;
- documentation, architecture, static, and mailbox-transport guards: 57 tests
  passed;
- full offline suite under disabled/conservative settings: 1,050 tests passed
  with one expected platform skip;
- Task 1 file-scoped content-free leakage scan: `total=0`;
- committed diff check: clean.

Reviewer-requested hardening verification:

- the ordering-focused test passed: one test, `OK`;
- the full focused Task 1, closeout, documentation/front-matter, architecture,
  static, and mailbox-transport guard command passed: 57 tests, `OK`;
- no RED cycle is claimed for this hardening because the reviewed operator
  documents were already correctly ordered.

The automated whole-workspace maintenance scanner opened the pre-existing
ignored `outputs/email_agent.sqlite3` read-only and returned only the aggregate
finding `public_sqlite / LEAK_PRIVATE_IDENTIFIER count=244`. No human manually
inspected its rows or matched values, and the artifact was not modified, copied,
staged, or committed. It must be separately isolated or disposed of by the
local operator before any real mailbox operation; Task 1 did not perform that
state-changing action.

Uncompleted work is exactly Slices 2 through 6. Continue only after Task 1
review approval, preserve module entrypoints, and retain the separate live
credential and fingerprint gate.
