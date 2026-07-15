---
last_update: 2026-07-15
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Real Mailbox Scan-Driven Plugin and DeepSeek Completion Task Brief

## 1. Task name

Complete the approved real-mailbox-scan-driven plugin and DeepSeek workflow in
six bounded implementation slices.

## 2. Task type

`feature | security | docs | test`

## 3. Current state

Approved for offline implementation. Approval of this brief does not authorize
a live mailbox connection, an external-vault read, a private dataset read, a
credential entry, or a DeepSeek request.

## 4. Objective

Finish the separately authorized administrator workflow and the normal
click-only browser experience without combining their trust boundaries. The
work must remain reviewable in six slices, with executable tests at every
boundary and a final explicit stop before any live mailbox content read.

## 5. Approved six-slice program

1. **Slice 1: Administrator entrypoints and governance**
2. **Slice 2: Evaluation staging, dataset build, and interactive judge**
3. **Slice 3: Read-only runtime knowledge snapshot bootstrap**
4. **Slice 4: Tencent context extraction, privacy diagnostics, and rule facts**
5. **Slice 5: Task-card extension UI**
6. **Slice 6: Full verification, project status, and live inventory readiness**

Each slice stops at its documented boundary. Later-slice work is not pulled
forward merely because an interface already exists.

## 6. Administrator entrypoint contract

Operators run the administrator tools from the project root only through these
module entrypoints:

```text
python -B -m scripts.manage_mailbox_vault ...
python -B -m scripts.manage_private_knowledge ...
python -B -m scripts.evaluate_private_deepseek ...
```

Text that names a `scripts/manage_*.py` file as an architecture boundary may
remain. Runnable operator examples must use the module forms above so imports
do not depend on an ambient `PYTHONPATH`.

## 7. Mailbox authorization boundary

The mailbox exception remains an administrator-only, manual, default-off
workflow for one authorized account at fixed `imap.exmail.qq.com:993`, with TLS
certificate verification and a rolling 24-month window. Its transport remains
read-only: `LIST`, `EXAMINE`, `UID SEARCH`, and bounded `UID FETCH` with
`BODY.PEEK`. It has no schedule, background poller, browser entrypoint, normal
backend route, SMTP path, flag mutation, or arbitrary IMAP command.

The operator sequence is two phase. `inventory` returns only content-free
counts, sizes, opaque folder metadata, UIDVALIDITY, date scope, and an
inventory fingerprint. The run must stop there. `scan` is a later live action
and requires an operator to review and repeat the unchanged fingerprint through
`--confirm-inventory-fingerprint`.

Plan approval is not the live gate. The separate live credential and fingerprint gate
requires fresh local authorization, interactive credential entry after local
preflight, review of the content-free inventory, and explicit confirmation of
the unchanged fingerprint. Credentials are never command-line, environment,
`.env`, log, report, test, or repository input.

## 8. Data handling and privacy

The binding rule is: **no raw mail to Codex, DeepSeek, Git, or public SQLite**.
Raw or identifying mailbox content may exist only in the authorized encrypted
project-external vault. It must not enter docs, tests, fixtures, logs, reports,
status files, maintenance output, public API responses, or browser storage.

Only locally deidentified, residual-clean, independently reviewed knowledge or
evaluation data may cross into its later isolated workflow. DeepSeek remains
disabled by default, and automated verification uses synthetic data and fake
clients only.

## 9. Current slice scope

Slice 1 may:

- add this tracked task brief and the matching tracked implementation plan;
- add a subprocess contract for the three module entrypoints from the project
  root with `PYTHONPATH` absent;
- standardize testing, deployment, and evaluator operator examples on module
  entrypoints;
- make the post-`inventory` human stop explicit.

Slice 1 must not implement `stage-evaluation`, evaluation dataset `build`, the
runtime snapshot bootstrap, Tencent extension extraction, new diagnostics,
rule-fact behavior, or task-card UI changes.

## 10. Interfaces and storage

- Database change: none.
- Public API change: none.
- AI output JSON change: none.
- Prompt change: none.
- Dependency change: none.
- Live credential or content access: none.

## 11. Acceptance criteria

1. All three module entrypoints reach their parser from the project root with
   no `PYTHONPATH` dependency.
2. The evaluator invalid-argument probe returns only fixed
   `argument_invalid` JSON and does not invoke help, a provider, or a dataset.
3. Runnable administrator examples use the three approved module entrypoints.
4. Operator docs say `STOP after inventory` before fingerprint-confirmed scan.
5. This brief and the implementation plan include valid YAML front matter and
   the six approved slices.
6. Focused entrypoint, documentation, architecture, static, and closeout guards
   pass offline, and `git diff --check` is clean.

## 12. Test plan

- Run the focused administrator module-entrypoint contract.
- Run rollout-closeout and documentation/front-matter guards.
- Run architecture, mailbox-transport, and static-linter guards.
- Run only offline tests; do not connect to IMAP, open a vault, read a private
  dataset, prompt for a real credential, or call a model provider.

## 13. Rollback

Revert the Slice 1 commit. No data migration, vault mutation, runtime
configuration change, credential cleanup, or provider rollback is required.

## 14. Human confirmation still required

After all six slices pass offline verification, a local operator must separately
authorize live readiness. The first allowed live action is inventory only. The
operator must then stop, review the content-free result, and explicitly approve
the unchanged fingerprint before any scan.
