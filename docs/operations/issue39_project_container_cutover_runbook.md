---
last_update: 2026-08-14
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Issue 39 Project Container cutover runbook

## Authority boundary

This runbook documents the fixed operator interface. It is not authority to run
the command. A merge, green CI, closed Issue 38, closure receipt, or prior
confirmation does not authorize the real incident disposition or cutover. Run
it only after a separate explicit authorization that names the real command.

The command never runs the Solo Maintainer closure `confirm` or the protected
closure verifier. Those are separate ceremonies and must already have produced
the exact currently eligible closure artifacts and closed Issue 38 state.

## Fixed command

Use a visible, real, directly connected Windows PowerShell console. Do not use
a captured shell, pipe, redirection, `Tee-Object`, scheduled task, IDE terminal
proxy, or stdin/stdout/stderr wrapper.

```powershell
Set-Location 'D:\Projects\email_ai_assistant'
& 'D:\Projects\email_ai_assistant\.venv\Scripts\python.exe' -I -B scripts\execute_project_container_cutover.py run
```

The script accepts only `run`. It accepts no path, source, target, force,
cleanup, credential, provider, mailbox, vault, or private-data option.

## What the command proves before mutation

Before it acquires a host mutation capability, the command performs only local
reads and fixed GitHub GET requests. It requires all of the following:

- the exact two Solo Maintainer closure artifacts and their current binding;
- the exact eligible master and closed Issue 38 state;
- the fixed Runtime, wheelhouse, lock, CRX, Config, database, and layout inputs;
- the complete bounded linked-worktree roster, including root/common/admin and
  per-worktree placement, Git, physical, branch, commit, and clean identities;
- either the exact reviewed incident source or its exact verified archive, with
  no conflicting source/destination state.

Any failure returns a fixed blocked status before incident disposition or
cutover mutation.

## Confirmation sequence

If the reviewed incident source still exists, the console prints one fresh
candidate fingerprint followed by:

```text
CONFIRM_ISSUE38_INCIDENT_STAGE_DISPOSITION_V1_NOT_CLOSURE_OR_CUTOVER
```

Enter the displayed fingerprint as the first line and the exact acknowledgement
as the second line within its fresh window. That ceremony authorizes only the
fixed same-volume no-replace incident-stage move.

After the incident state is archived or already verified, the command performs
a completely fresh prepare. Any roster, master, closure, issue, input,
placement, identity, or cleanliness drift stops before production binding.

Every subsequent catalog action prints its own fresh candidate fingerprint and
the following exact acknowledgement:

```text
CONFIRM_R2_ISSUE39_EXECUTION_V1_NOT_CLOSURE_ATTESTATION
```

Enter those two displayed lines only after checking the action and current
state shown by the visible console. Each confirmation is single-use, bound to
the exact action and durable journal head, and cannot authorize a later action.
Resume, rollback, terminal success, and legacy-restoration sealing also require
their own fresh confirmations.

## Fixed action order

For the current six-worktree roster, the catalog contains 27 actions and 24
host effects:

1. Quiesce the legacy service; retain the legacy anchor; publish the Container
   and `main`; apply the exact ACL tree; relocate the repository.
2. Reconstruct every freshly bound linked worktree in roster order.
3. Prepare and publish Runtime, LocalData database, CRX, and Config.
4. Start A, prove deterministic rule fallback, stop A, prove the database and
   stopped layout, start B, and perform the final running audit.
5. Reobserve the complete terminal state twice, confirm the terminal record,
   durably seal success, and only then print the public success token.

The number of worktree actions is derived from the fresh complete roster, not
from the historical eleven-worktree rehearsal constant.

## Expected public result

The only successful public output is:

```text
PROJECT_CONTAINER_CUTOVER_SUCCEEDED
```

Any JSON status, nonzero exit, console loss, collision, drift, ambiguous
observation, or missing success token means the cutover is not verified as
successful. Do not rerun blindly and do not delete, repair, replace, or clean
retained state. The only repair operation inside the orchestrator is its
catalog-owned, journaled, exact bound `git worktree repair`; operators must not
run a manual or caller-selected repair.

## Crash and restart handling

The evidence package is create-only under the fixed Issue 39 evidence archive
and contains `issue39-cutover-runner-v1.pyz`. After the first anchor transfer,
the process uses the fixed Runtime Python and that retained runner. A restart is
recognized only when launched from the exact retained anchor and reopens the
durable ledger fail-closed.

The ledger classifies a pending action from two stable reads. An already-present
effect is committed only after a fresh `resume` confirmation and is never
repeated. An exact absent effect may continue only through its prescribed
confirmation. Ambiguity returns `INCIDENT_STOP`. Rollback is LIFO over the
durably committed host-effect prefix, uses fresh confirmations, retains the
failed Container, and never performs cleanup.

Do not copy the runner, ledger, candidate fingerprint, or confirmation text to
a new location. Do not improvise a restart command. Preserve the console output
and all retained paths, then diagnose read-only before requesting recovery
authority.

## Post-result checks

After success, verify read-only that the durable success seal exists and that
the final audit's two observations bind the same final layout, roster, Git,
ACL, managed-unit, service, provider-disabled health, and database state. After
`LEGACY_RECOVERED`, verify the separate legacy terminal record and two-read
legacy topology/service/ACL/Git-worktree audit. Neither result permits cleanup
of evidence, the archived incident stage, failed containers, or journals.

## Prohibited operations

- No fetch, prune, cleanup, reset, stash, clone, delete, overwrite, or manual
  repair. Only the code-fixed journaled worktree repair may run.
- No Issue 38/39 or ruleset mutation from this command.
- No provider, mailbox, vault, credential, private-data, or recovery-media access.
- No use of green tests or CI as live execution authority.
- No real execution during implementation or synthetic verification.
