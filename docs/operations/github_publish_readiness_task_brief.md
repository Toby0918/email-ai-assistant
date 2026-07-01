---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# GitHub Publish Readiness Task Brief

## 1. Task Name

prepare repository for GitHub publishing

## 2. Task Type

docs

## 3. Current Status

completed

## 4. Goal

Prepare the first-phase project for a clean initial GitHub upload.
The public README and generated project status log should be readable, and IDE or local-only files should not be staged for upload.

## 5. Non-goals

- Do not push to GitHub without a remote repository URL and explicit confirmation.
- Do not connect to real mailbox accounts.
- Do not send, delete, archive, or scan emails.
- Do not add dependencies.
- Do not change the backend API, database schema, AI output JSON schema, or prompt behavior.

## 6. Background and References

The first-phase local MVP is complete and the user wants to upload it to GitHub as a project.
Repository status shows no commits yet, a missing remote, tracked IDE files in the index, and unreadable text in the public README/status log output.

Related files:
- AGENTS.md
- README.md
- .gitignore
- scripts/generate_project_status.py
- tests/test_generate_project_status.py
- tests/test_frontend_local_debug.py
- docs/operations/project_status_log.md

## 7. Scope

Planned changes:
- README.md
- scripts/generate_project_status.py
- tests/test_generate_project_status.py
- tests/test_frontend_local_debug.py
- docs/operations/project_status_log.md
- docs/operations/github_publish_readiness_task_brief.md
- Git index cleanup for `.idea/` and legacy `mail_agent_mvp.py`

## 8. Technical Approach

1. Add failing tests that require readable README and project status text.
2. Replace mojibake text in the status generator with readable Chinese.
3. Rewrite README as a concise first-phase project entry document.
4. Regenerate the project status log.
5. Remove IDE and legacy files from the Git index while keeping local files untouched.

## 9. Data Structure or Interface Changes

Database changes: none.

API changes: none.

AI output JSON changes: none.

Prompt changes: none.

## 10. Security and Privacy Check

- [x] Does not read real mailbox data.
- [x] Does not send, delete, archive, or scan emails.
- [x] Does not store or expose OpenAI API keys in frontend code.
- [x] Keeps `.env`, SQLite databases, outputs, logs, and IDE files out of the upload.
- [x] Uses no new dependencies.

## 11. Prompt Injection Protection

This task does not change email content analysis or prompt construction.

## 12. Acceptance Criteria

1. README contains readable project purpose, boundaries, setup, run, test, and GitHub upload notes.
2. Generated project status contains readable Chinese summary, next steps, boundaries, and notes.
3. Tests protect the README and project status from the observed mojibake regression.
4. `.idea/` and legacy local files are not staged for GitHub upload.
5. Full tests and maintenance scan pass.

## 13. Test Plan

- Run `python -m unittest tests.test_generate_project_status tests.test_frontend_local_debug`.
- Run `python -m unittest discover -s tests`.
- Run `python scripts/maintenance_scan.py`.
- Run `git status --short --ignored` and inspect staged/untracked/ignored files.

## 14. Rollback Plan

Revert README, generator, test, status-log, and task-brief changes; re-add any intentionally unstaged index entries only if the user requests IDE files in Git.

## 15. Open Questions

Need the user's GitHub repository URL before pushing.

## 16. Pre-execution Checklist

- [x] Read AGENTS.md.
- [x] Read project status log.
- [x] Read tooling, architecture, and linter constraints.
- [x] Confirmed no real mailbox or automatic email action is involved.
- [x] Confirmed no remote push will happen without user-provided URL.

## 17. Post-execution Record

Actual changed files:
- README.md
- tests/test_generate_project_status.py
- tests/test_frontend_local_debug.py
- docs/operations/project_status_log.md
- docs/operations/github_publish_readiness_task_brief.md
- Git index cleanup for `.idea/` and `mail_agent_mvp.py`

Test results:
- `python -m unittest tests.test_generate_project_status tests.test_frontend_local_debug`: 17 tests passed.
- `python -m unittest discover -s tests`: 93 tests passed.
- `python scripts/maintenance_scan.py`: no cleanup findings detected.

Incomplete items:
- GitHub remote URL is not configured yet, so push is intentionally not performed.

Follow-up suggestions:
- After the initial local commit, create an empty GitHub repository, provide its remote URL, then add `origin` and push.
