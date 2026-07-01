---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# File Inventory And Cleanup Record

## Cleanup Goal

Align the repository with the current product goal: an enterprise mailbox AI assistant window that analyzes the currently opened email after a user click. Remove legacy batch mailbox reader, task board, reports, local caches, and generated artifacts.

## Keep

| Path | Decision | Reason |
| --- | --- | --- |
| `.git/` | keep | Repository metadata. |
| `.github/workflows/agent_guardrails.yml` | keep | CI guardrails for executable constraints. |
| `AGENTS.md` | keep | Project entry rules and navigation. |
| `README.md` | rewrite | Project entry README now matches the assistant-window target. |
| `.env.example` | rewrite | Backend-only local config sample; no real mailbox account. |
| `.gitignore` | rewrite | Ignores local secrets, databases, caches, old outputs, and generated artifacts. |
| `requirements.txt` | rewrite | Keeps pinned backend dependency versions. |
| `docs/` | keep | Product rules, constraints, schemas, prompts, operations, and review process. |
| `tests/` | keep | Executable architecture, linter, and mechanical rule constraints. |

## Delete

| Path | Decision | Reason |
| --- | --- | --- |
| `.env` | delete | Local secret/config file; not part of repository baseline. |
| `.idea/` | delete | IDE metadata, not project source. |
| `.venv/` | delete | Local virtual environment. |
| `__pycache__/` | delete | Generated Python bytecode cache. |
| `actions/` | delete | Legacy batch mail-reader action module. |
| `analyzers/` | delete | Legacy batch analyzer modules not aligned with new backend architecture. |
| `exporters/` | delete | Legacy CSV/Excel/HTML report exporters. |
| `attachments/` | delete | Local mailbox attachment cache and potentially sensitive data. |
| `config.py` | delete | Legacy IMAP/batch-reader configuration. |
| `email_reader.py` | delete | Legacy real mailbox IMAP reader; first phase must not connect real mailbox accounts. |
| `mail_agent_mvp.py` | delete | Legacy batch mailbox reader and report entrypoint. |
| `mark_done.py` | delete | Legacy local task-board state command. |
| `storage.py` | delete | Legacy database schema and report storage. |
| `task_board.py` | delete | Legacy local batch email workbench. |
| `utils.py` | delete | Legacy utilities tied to IMAP/batch reader. |
| `run_mail_reader.ps1` | delete | Legacy mail reader launcher. |
| `运行邮件读取.cmd` | delete | Legacy mail reader launcher. |
| `启动邮件工作台.cmd` | delete | Legacy task board launcher. |
| `停止邮件工作台.cmd` | delete | Legacy task board stop script. |
| `emails.db` | delete | Local SQLite data from old mailbox reader. |
| `mail_tasks.csv` | delete | Generated legacy report. |
| `mail_tasks.xlsx` | delete | Generated legacy report. |
| `mail_tasks_report.html` | delete | Generated legacy report. |
| `mail_reader_last_run.log` | delete | Generated legacy runtime log. |
| `task_board.err.log` | delete | Generated legacy runtime log. |
| `task_board.out.log` | delete | Generated legacy runtime log. |

## Notes

This cleanup intentionally leaves the repository without implementation code until the new `backend/email_agent/` and selected `frontend/` route are implemented under the documented architecture constraints.
