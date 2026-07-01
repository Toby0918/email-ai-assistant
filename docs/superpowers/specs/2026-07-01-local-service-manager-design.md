---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: design_spec
---

# Local Service Manager Design

## Goal

Provide a repeatable local workflow for starting, stopping, restarting, and checking the first-version local debug server.

## Scope

The feature manages only the local debug server launched by `scripts/run_local_debug.py`.
It does not connect to a real mailbox, scan emails, send emails, delete emails, archive emails, or change the analysis API.

## Chosen Approach

Use a standard-library Python manager script:

```text
python scripts/manage_local_service.py start
python scripts/manage_local_service.py stop
python scripts/manage_local_service.py restart
python scripts/manage_local_service.py status
```

The manager stores a PID in `outputs/local_debug_service.pid`, checks service health with `GET /api/health`, and only stops the recorded PID.
This keeps behavior explicit and avoids killing unrelated processes by port.

Windows `.cmd` shortcuts call the Python manager from the project root:

```text
start_local_service.cmd
stop_local_service.cmd
restart_local_service.cmd
status_local_service.cmd
```

## Error Handling

- `start` returns success if the service is already healthy.
- `stop` removes a stale PID file when the recorded service is not healthy.
- `status` reports `running`, `stopped`, or `unknown`.
- The manager does not terminate processes unless their PID came from the managed PID file.

## Testing

Tests cover command-line help, status without a PID file, start command construction, stale PID cleanup, restart sequencing, and `.cmd` shortcut contents.
Full project tests and maintenance scan remain the final verification.
