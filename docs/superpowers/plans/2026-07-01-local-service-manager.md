---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: implementation_plan
---

# Local Service Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local debug service manager with Python CLI commands and Windows `.cmd` shortcuts.

**Architecture:** Keep process management in `scripts/manage_local_service.py`, outside backend business modules. Use `outputs/local_debug_service.pid` as local runtime state and `/api/health` as readiness signal.

**Tech Stack:** Python 3.12 standard library, Windows batch files, unittest.

---

### Task 1: Test the Manager Contract

**Files:**
- Create: `tests/test_manage_local_service.py`

- [ ] **Step 1: Write failing tests**

Create tests that import `scripts.manage_local_service` and verify:
- `build_parser()` exposes `start`, `stop`, `restart`, and `status`.
- `status_service()` returns stopped when there is no PID and health check fails.
- `start_service()` launches `scripts/run_local_debug.py` and writes the PID.
- `stop_service()` removes a stale PID file when health is down.
- `restart_service()` calls stop then start.
- Batch files contain `scripts\manage_local_service.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_manage_local_service`

Expected: failure because `scripts.manage_local_service` and batch files do not exist yet.

### Task 2: Implement the Python Manager

**Files:**
- Create: `scripts/manage_local_service.py`

- [ ] **Step 1: Add standard-library service helpers**

Implement:
- `build_parser()`
- `check_health(host, port, timeout)`
- `status_service(config)`
- `start_service(config)`
- `stop_service(config)`
- `restart_service(config)`
- `main(argv=None)`

- [ ] **Step 2: Run targeted tests**

Run: `python -m unittest tests.test_manage_local_service`

Expected: only batch-file tests fail until Task 3.

### Task 3: Add Windows Shortcuts

**Files:**
- Create: `start_local_service.cmd`
- Create: `stop_local_service.cmd`
- Create: `restart_local_service.cmd`
- Create: `status_local_service.cmd`

- [ ] **Step 1: Add batch wrappers**

Each wrapper resolves `.venv\Scripts\python.exe` first, falls back to `python`, calls `scripts\manage_local_service.py`, and pauses so double-click users can read the result.

- [ ] **Step 2: Run targeted tests**

Run: `python -m unittest tests.test_manage_local_service`

Expected: all service manager tests pass.

### Task 4: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/operations/setup_checklist.md`
- Modify: `docs/operations/troubleshooting.md`
- Modify: `docs/operations/local_service_manager_task_brief.md`

- [ ] **Step 1: Document commands**

Add start, stop, restart, and status examples.

- [ ] **Step 2: Record final task results**

Update the task brief post-execution record.

### Task 5: Final Verification

**Files:**
- Modify: `docs/operations/project_status_log.md`

- [ ] **Step 1: Regenerate project status**

Run: `python scripts/generate_project_status.py --output docs/operations/project_status_log.md`

- [ ] **Step 2: Run full verification**

Run:
- `python -m unittest discover -s tests`
- `python scripts/maintenance_scan.py`

Expected: full tests pass and maintenance scan reports no findings.
