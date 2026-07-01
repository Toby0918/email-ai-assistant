---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Local Service Manager Task Brief

## 1. Task Name

local debug service start-stop manager

## 2. Task Type

feature

## 3. Current Status

implemented

## 4. Goal

Add a local service management entry point for the first-version debug server.
The primary interface is `python scripts/manage_local_service.py start|stop|restart|status`, with Windows `.cmd` shortcuts for double-click use.

## 5. Non-goals

- Do not connect to real mailbox accounts.
- Do not send, delete, archive, or scan emails.
- Do not expose OpenAI API keys in the frontend.
- Do not add dependencies.
- Do not change the analysis API schema.

## 6. Background and References

The current local debug service starts with `python scripts/run_local_debug.py` and must be manually stopped from its terminal.
Users need a safer and repeatable local workflow for restarting the backend after code changes.

Related files:
- AGENTS.md
- docs/operations/project_status_log.md
- docs/constraints/tooling_constraints.md
- docs/constraints/architecture_constraints.md
- docs/constraints/linter_constraints.md
- scripts/run_local_debug.py
- tests/test_run_local_debug.py

## 7. Scope

Planned additions or updates:
- scripts/manage_local_service.py
- start_local_service.cmd
- stop_local_service.cmd
- restart_local_service.cmd
- status_local_service.cmd
- tests/test_manage_local_service.py
- README.md
- docs/operations/setup_checklist.md
- docs/operations/troubleshooting.md
- docs/operations/project_status_log.md

## 8. Technical Approach

1. Implement a standard-library-only Python manager script with `start`, `stop`, `restart`, and `status`.
2. Store the managed process id in `outputs/local_debug_service.pid`.
3. Check service health via `GET /api/health` on the configured loopback host and port.
4. Stop only the PID recorded by the manager; do not kill arbitrary processes by port.
5. Add Windows `.cmd` wrappers that call the Python manager from the project root.

## 9. Data Structure or Interface Changes

Database changes: none.

API changes: none.

AI output JSON changes: none.

Prompt changes: none.

## 10. Security and Privacy Check

- [x] Does not read real mailbox data.
- [x] Does not send, delete, archive, or scan emails.
- [x] Does not store or expose OpenAI API keys in the frontend.
- [x] Does not log real email bodies.
- [x] Uses only local loopback service health checks.
- [x] Uses no new dependencies.

## 11. Prompt Injection Protection

This task does not process email content or prompt text.
It only manages the local debug server process.

## 12. Acceptance Criteria

1. `python scripts/manage_local_service.py --help` documents `start`, `stop`, `restart`, and `status`.
2. `status` can report stopped state without an existing PID file.
3. `start` launches `scripts/run_local_debug.py` in the background, writes a PID file, and waits for health.
4. `stop` only stops the PID recorded by the PID file and removes stale PID files.
5. `restart` performs stop then start.
6. Windows `.cmd` shortcuts exist for start, stop, restart, and status.
7. Full tests and maintenance scan pass.

## 13. Test Plan

- Add unit tests for argument parsing, status, start command construction, stale PID cleanup, and command wrapper contents.
- Run targeted tests for the service manager.
- Run full `python -m unittest discover -s tests`.
- Run `python scripts/maintenance_scan.py`.

## 14. Rollback Plan

Remove the manager script, `.cmd` shortcuts, related tests, and documentation updates.

## 15. Open Questions

None. The user selected option A and requested option B shortcuts too.

## 16. Pre-execution Checklist

- [x] Read AGENTS.md.
- [x] Read project status log.
- [x] Read tooling, architecture, and linter constraints.
- [x] Confirmed no real mailbox or automatic email action is involved.
- [x] Confirmed no dependencies are added.

## 17. Post-execution Record

Actual changed files:
- scripts/manage_local_service.py
- start_local_service.cmd
- stop_local_service.cmd
- restart_local_service.cmd
- status_local_service.cmd
- tests/test_manage_local_service.py
- README.md
- docs/operations/setup_checklist.md
- docs/operations/troubleshooting.md
- docs/operations/local_service_manager_task_brief.md
- docs/superpowers/specs/2026-07-01-local-service-manager-design.md
- docs/superpowers/plans/2026-07-01-local-service-manager.md

Test results:
- `python scripts/manage_local_service.py --help`: passed.
- Real start/status/stop smoke test on `127.0.0.1:8878`: passed.
- `python -m unittest tests.test_manage_local_service`: 6 tests passed.
- `python -m unittest discover -s tests`: 85 tests passed.
- `python scripts/maintenance_scan.py`: no findings.

Incomplete items:
- None.

Follow-up suggestions:
- Use `python scripts/manage_local_service.py restart` after backend code changes.
