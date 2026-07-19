---
last_update: 2026-07-19
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Linux CI Path Fixture Repair Task Brief

## 1. Task name

Make private-knowledge and mailbox-facade test paths portable across Windows and Linux.

## 2. Task type

`test`

## 3. Current status

`implemented`

## 4. Goal

Repair the GitHub Actions failures caused by Windows drive-letter test fixtures being
relative paths on Ubuntu. Preserve the production fail-closed path validation and
security behavior exactly as implemented.

## 5. Non-goals

- Do not change private-storage or snapshot path validation.
- Do not change runtime bootstrap fallback or key-wiping behavior.
- Do not change mailbox CLI event or error contracts.
- Do not access a mailbox, vault, provider, ignored SQLite database, or real data.
- Do not modify the user's unrelated deployment notes.

## 6. Background and evidence

GitHub Actions run `29691713931` failed ten tests on `ubuntu-latest`. The affected
fixtures use paths such as `C:/project` and `E:/vault`; `pathlib.Path` treats these as
absolute on Windows and relative on POSIX. The failures therefore occur before the
loader, mutable-key context, or authorization binding code under test is reached.

Relevant guidance:

- `AGENTS.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/ci_guardrails.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`

## 7. Scope

Expected changes:

- `tests/test_private_knowledge_runtime_bootstrap.py`
- `tests/test_private_knowledge_storage_policy.py`
- `tests/test_manage_mailbox_vault.py`
- `docs/operations/project_status_log.md`
- this task brief

## 8. Technical approach

1. Replace only the path fixtures that cross absolute-path validation with
   host-native absolute synthetic paths.
2. Keep the same logical separation between project, authority, snapshot, vault,
   and temporary roots.
3. Run focused tests, the complete suite, status generation, maintenance scanning,
   repository leakage checks, and `git diff --check`.

## 9. Data and interface changes

- Database: none.
- API: none.
- AI output JSON: none.
- Prompt: none.

## 10. Security and privacy checks

- [x] Uses synthetic test data only.
- [x] Does not read or mutate any mailbox.
- [x] Does not send, delete, move, or archive email.
- [x] Does not access API keys, credentials, vaults, or real attachments.
- [x] Does not weaken fail-closed production validation.
- [x] Does not persist sensitive content in logs or Git.

## 11. Prompt-injection protection

Not applicable. No email content or provider path is exercised.

## 12. Acceptance criteria

1. All previously failing focused tests pass with host-native absolute fixtures.
2. Production files remain unchanged.
3. The complete unit suite and required guardrails pass.
4. Maintenance and tracked-file leakage scans report no blocking findings.
5. A new push to `master` completes GitHub Actions successfully.

## 13. Test plan

- Focused private-knowledge bootstrap, storage-policy, and mailbox-facade tests.
- `python -m unittest discover -s tests`
- architecture, static-linter, mechanical-rule, maintenance, and status tests.
- `python scripts/generate_project_status.py --output docs/operations/project_status_log.md`
- `python scripts/maintenance_scan.py`
- repository leakage scan and `git diff --check`.

## 14. Rollback

Revert the single test-focused commit. No data migration or production state rollback
is required.

## 15. Human confirmation

The user approved this test-only repair and the follow-up push to `master`.

## 16. Pre-execution checks

- [x] Read `AGENTS.md` and the current project status.
- [x] Read the applicable tooling, architecture, linter, CI, and mechanical rules.
- [x] Confirmed the exact goal and non-goals.
- [x] Confirmed no real mailbox, secret, or customer data is in scope.
- [x] Confirmed the affected file set.

## 17. Remote provider private-context checklist

Not applicable. Provider behavior, input, budgets, and private knowledge loading are
unchanged.

## 18. Administrator stage-evaluation checklist

Not applicable. The administrator evaluation handoff is unchanged.

## 19. Final dataset build and interactive judge checklist

Not applicable. Private evaluation build and judge behavior are unchanged.

## 20. Post-execution record

Actual files changed:

- `tests/test_private_knowledge_runtime_bootstrap.py`
- `tests/test_private_knowledge_storage_policy.py`
- `tests/test_manage_mailbox_vault.py`
- `docs/operations/linux_ci_path_fixture_repair_task_brief.md`
- `docs/operations/project_status_log.md`

Verification results:

- Focused regression: 25 tests passed.
- Complete local suite: 1,459 tests passed with one documented skip.
- Independent specification/security review: no findings.
- Independent quality/portability review: no findings.

Incomplete item at recording time:

- Confirm the new `ubuntu-latest` GitHub Actions run after pushing `master`.

Follow-up recommendation:

- Treat GitHub Actions as the authoritative Python 3.12.13 and Linux portability
  check because the existing local project virtual environment uses Python 3.12.6.
