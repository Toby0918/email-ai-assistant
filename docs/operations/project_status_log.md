---
last_update: 2026-07-26
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Project Status Log

> Agent-readable project progress snapshot. This is not a normal development log.
> Agent should read `AGENTS.md` and this file before starting non-trivial work.

## Snapshot

| Field | Value |
|---|---|
| Generated on | 2026-07-26 |
| Current stage | multimodal_current_email_offline_ready_live_pending |
| Git branch | codex/issue-53-real-host-preflight |
| Git HEAD reference | Run `git rev-parse --short HEAD` in this workspace |
| Working tree status | Run `git status --short --ignored` in this workspace |

## Project Summary

本项目是企业邮箱中的 AI 辅助窗口。正常产品只做“用户点击按钮后分析当前打开邮件”，不做全邮箱扫描、不自动发送邮件、不删除邮件或归档邮件。

Separately authorized exception: the `administrator-only CLI remains default-off` and may import one authorized account within a rolling 24-month window only after explicit inventory fingerprint confirmation. The browser extension and normal runtime remain click-only and cannot scan a mailbox. The exception has no schedule, browser hook, normal-backend route, or automatic model call.

Issue #11 governed sales-corpus bootstrap is offline implemented. `scan` requires a separately stored strict private sales policy, binds only keyed metadata to a fresh corpus index, deduplicates cross-folder messages and attachment blobs, and exposes only fixed aggregate counts. Only an exact external-customer request to a strictly later allowlisted reply becomes a governed pair; unpaired records are rejected before downstream staging or reviewed attachment acquisition. No live mailbox, provider, or real private vault was used for this implementation.

ADR 0008 ratifies a future manual incremental-sync boundary and a contract-only, write-only deidentified current-click evidence seam. Issue #10 adds no sync command or evidence inbox; those implementations remain in future issues #17 and #18. Normal runtime receives no mailbox, historical-store, authority-store, reader, search, path, key, repository, polling, or hot-reload capability.

The private-knowledge snapshot is verified and read-only; an invalid or missing private-knowledge snapshot returns generic rule fallback. Tasks 1-7 of the multimodal current-email route are offline implemented and review-clean. The route is one OpenAI multimodal primary call, at most one eligible DeepSeek text-only fallback, and deterministic rules last; all providers remain disabled by default. Its budget tuple is `60/55/35/10/12/8/5` seconds: 60-second POST wait, 55-second backend target, 35-second OpenAI cap, 10-second DeepSeek cap, 12-second fallback minimum, 8-second parser cap, and 5-second reserve. Browser media discovery remains a separate 20-second resource collection phase. Private evaluation is blocked by `human_judge_unavailable` by default and does not switch production models.

Current-message attachment acquisition recognizes only a verified legacy current-message control after Analyze and keeps automatic bytes in browser memory. The manual picker selection is inert until Analyze. Both paths share 5 files, 10 MiB per file, and 25 MiB total, add no download/storage/filesystem permission, and expose no local path. Backend request-local files are removed from request `finally`; the 24-hour mtime cleanup is crash recovery only, not normal retention or a scheduled job. Only `attachment_insights[].status=parsed` proves content parsing.

Prior Task 9 synthetic and current-clicked smokes remain valid acquisition, routing, status, and cleanup evidence only. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. Current/history evidence alignment, provider-visible attachment coverage, deterministic reconciliation safeguards, and the documented private human gold-standard method now pass the offline gate; the reviewed repair is integrated into the current release line. Any new live operation still requires fresh explicit authorization. All providers remain disabled by default.

Issue #32 Managed launcher is implemented for the exact `email_ai_assistant\main` placement. It routes provider-disabled SQLite, attachment temp, logs, PID, runtime, artifact, worktree, and bounded non-secret Config paths to their approved zones while source and repository tooling remain at `main`. Synthetic loopback lifecycle verification passes, but no real Project Container migration or operational cutover has occurred.

Issue #34 manual content-free Container Audit is offline implemented behind seven injected read-only metadata adapters. Its exact nine-entry, ACL, volume, Git/worktree, runtime, SQLite, Config, Logs/Artifacts, and disabled-private-state contract fails closed and exposes only fixed status/counts. No real Container audit or host-security probe was run.

Issue #35 no-clobber migration evidence package is offline implemented as a manual internal Python contract. It binds exact reviewed local refs, branch-attached worktree identities, an allowlisted two-layer dirty-source snapshot, content-free Git/ACL/volume baselines, and every payload file with canonical SHA-256 evidence. Publication is external-target, create-only and fail-closed; verification restores Git objects, refs, dirty state and worktree identity in synthetic repositories. No real evidence package was created.

Issue #36 repository/worktree reparenting rehearsal is offline implemented as one pathless synthetic-only Python seam. It builds a temporary repository with a bound marker filesystem identity and a non-trivial Git baseline, creates and verifies one synthetic Issue #35 package, no-clobber moves the existing Git common directory and reviewed source into a synthetic `main`, applies injected repair/recreate worktree choices, verifies exact post-state and passes a synthetic ContainerAudit. All six publication-boundary failures verify rollback preservation; post-main failures preserve the complete Container at the single sibling rollback path. The public operation leaves the synthetic topology intact for independent caller observation. No real workspace, worktree, branch, directory, ACL, runtime, database or private data was touched; Issues #38 through #40 remain separate.

Issue #37 managed runtime and LocalData activation rehearsal is offline implemented behind exact five injected adapters and one pathless synthetic-only seam. Temporary synthetic sources prove a create-only pinned runtime, a Windows venv rebuilt from the exact dependency lock, `pre_publication` stopped-service create-only SQLite publication with identity/SHA-256/integrity/sidecar/count checks, reviewed-hash browser-extension publication, exact Managed writable roles, and one strict activation token across provider-disabled start, literal-loopback health, one persisted rule-fallback analysis and the same-service `post_activation` fresh-stop proof. Stale evidence and equality spoofing fail closed. The source database remains unchanged after success and every simulated race, reparse, existing-target, dependency, integrity or health failure. No real runtime, SQLite database, browser-extension artifact or migration evidence package was activated; Issues #38 through #40 remain separate.

Issue #51 locked Cutover Profile, authorization, and receipt contracts are offline implemented as a pure content-free Python contract layer. Immutable `CutoverProfileV1` values bind the reviewed cutover inputs without paths or host readers. The four distinct real-host authorization value types validate externally supplied canonical values and cannot create, issue, or mint authority. The strict canonical `ReceiptEnvelopeV1` values are duplicate/unknown rejecting, fingerprint-bound, and never accepted as authorization. `default_operator_entry()` remains fixed at `BLOCKED_NO_APPROVED_COMMAND`. Its approved consumers are the exact Issue #52 journal bridge and exact Issue #53 preflight contract bridges.

Issue #52 crash-safe journal and recovery classification are offline implemented in the pathless synthetic-only `backend.cutover_journal` package. Strict canonical create-only records bind sequence, previous/record hashes, fixed synthetic step/event/direction, operation/profile/authorization/owner fingerprints, and opaque observations. Every forward and reverse action uses durable `INTENT`, exact observed effect, and `COMMITTED`; each owner claim gets a distinct lease and each effect consumes a non-copyable, non-serializable single-use store permit bound to the exact active durable intent and durable journal head. The shared store-private issuance is atomically claimed; one synthetic medium operation gate serializes append, restart, permit mint/claim, and effect mutation; every namespace-published current head completes stable reread and full snapshot reverification before a successor append or permit. Stable-reread evidence is hash-bound, and head advance, pending state, or an observed fact invalidates stale permits. Pending or unbarriered records never authorize an effect; verified pending direction/event/outcome controls event-aware exact pending publication without effect replay or an extra action; durable observed facts are authoritative across fresh `RESUME_BOUND` renewal. Reverse steps are derived LIFO only from verified `COMMITTED/APPLIED` history. Exact Profile/master/operator, identity mapping, synthetic transition mapping, and post-effect observation all fail closed. Exact in-memory Windows/Linux traces prove file/namespace/stable-reread ordering without claiming real filesystem durability. Restart inspection is read-only, exact expected-post is never blindly repeated, and explicit resume/rollback fresh-validate phase-specific authorization including the pre-bound recovery fingerprint. Public results expose only fixed status, phase, receipt fingerprint, and allowlisted counts distinguishing `SAFE_ABORT`, `ROLLBACK_REQUIRED`, `INCIDENT_STOP`, and `CUTOVER_SUCCEEDED`. No real filesystem target, service, ACL, Git repository/worktree, Runtime, SQLite, provider, mailbox, vault, private data, preflight, migration, cutover, resume, or rollback was accessed or run; Issues #54 through #59 remain separate.

Issue #53 content-free Windows real-host preflight composition is offline implemented in `backend.real_host_preflight`. The Windows observer opens every controlled path component without following reparse points and binds fixed-volume identity, 128-bit file identity, object type, parent identity, normalized-name fingerprint, attributes, and reparse metadata. Only exact, unexpired `TestSandboxAuthorizationV1` values can create test-owned temporary scopes; no real project path was observed. `CurrentTopologyPreflight` requires two complete identical seven-reader observations. `PreMutationGate` is short-lived, UUIDv4 nonce-bound, single-operation, single-use, and repeats the exact topology before producing canonical content-free receipts. `RealHostBaselineCollector` keeps source, parent, finance, volume, operator-SID, and three ACL roles separate while projecting the existing canonical `HostBaseline`. The unchanged nine-zone `ContainerAudit` receives exactly seven callbacks through a narrow bridge; final-audit readiness validates composition without running or claiming a final-layout audit. The zero-argument operator entry remains fixed at `BLOCKED_NO_APPROVED_COMMAND` and cannot accept test authorization. Production code has no service-control, ACL-apply, rename, worktree mutation, Runtime build, database copy, artifact, Config, provider, mailbox, vault, private-data, or content-reading capability. Windows behavior was exercised only in test-owned temporary sandboxes, and portable tests make no NTFS or Windows ACL claim. Issues #54 through #59, Issues #38/#39, and parent Spec #50 remain separate and unchanged.

The selected daily frontend remains the Tencent Exmail Chrome / Edge 浏览器扩展, with current-message collection only after an explicit user click.

## Guardrails Established

| File | Exists |
|---|---|
| `Project entry rules: AGENTS.md` | yes |
| `Tooling constraints: docs/constraints/tooling_constraints.md` | yes |
| `Architecture constraints: docs/constraints/architecture_constraints.md` | yes |
| `Static linter constraints: docs/constraints/linter_constraints.md` | yes |
| `Mechanical rule translation: docs/constraints/mechanical_rule_translation.md` | yes |
| `CI guardrails: .github/workflows/agent_guardrails.yml` | yes |
| `Cleanup automation: docs/operations/cleanup_agent_codex.md` | yes |
| `Maintenance scan: scripts/maintenance_scan.py` | yes |
| `Repository leakage scan: scripts/repository_leakage_scan.py` | yes |
| `Agent task brief: docs/templates/agent_task_brief_template.md` | yes |
| `Authorized mailbox ingest boundary: docs/operations/authorized_mailbox_ingest_task_brief.md` | yes |
| `Bounded corpus-to-runtime handoffs: docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md` | yes |
| `Governed sales corpus bootstrap: docs/operations/issue11_governed_sales_corpus_task_brief.md` | yes |
| `No-clobber migration evidence package: docs/operations/issue35_migration_evidence_package_task_brief.md` | yes |
| `Synthetic repository reparenting rehearsal: docs/operations/issue36_reparenting_rehearsal_task_brief.md` | yes |
| `Synthetic Managed runtime activation rehearsal: docs/operations/issue37_managed_runtime_localdata_rehearsal_task_brief.md` | yes |
| `Locked cutover contracts: docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md` | yes |
| `Synthetic crash-safe journal and recovery classification: docs/operations/issue52_crash_safe_journal_recovery_task_brief.md` | yes |
| `Content-free Windows real-host preflight composition: docs/operations/issue53_windows_real_host_preflight_task_brief.md` | yes |
| `Project Container cutover contract security boundary: docs/security/project_container_cutover_contracts.md` | yes |

## Key File Status

| File | Exists |
|---|---|
| `AGENTS.md` | yes |
| `README.md` | yes |
| `.env.example` | yes |
| `requirements.txt` | yes |
| `.gitignore` | yes |
| `.github/workflows/agent_guardrails.yml` | yes |
| `.github/workflows/cleanup_agent.yml` | yes |
| `backend/current_evidence/__init__.py` | yes |
| `backend/current_evidence/artifact_policy.py` | yes |
| `backend/current_evidence/contract.py` | yes |
| `backend/current_evidence/handoff.py` | yes |
| `backend/cutover_contracts/__init__.py` | yes |
| `backend/cutover_contracts/_canonical.py` | yes |
| `backend/cutover_contracts/authorization.py` | yes |
| `backend/cutover_contracts/authorization_schema.py` | yes |
| `backend/cutover_contracts/authorization_validation.py` | yes |
| `backend/cutover_contracts/errors.py` | yes |
| `backend/cutover_contracts/operator_entry.py` | yes |
| `backend/cutover_contracts/profile.py` | yes |
| `backend/cutover_contracts/profile_schema.py` | yes |
| `backend/cutover_contracts/receipt.py` | yes |
| `backend/cutover_contracts/receipt_matrix.py` | yes |
| `backend/cutover_contracts/receipt_schema.py` | yes |
| `backend/cutover_contracts/receipt_types.py` | yes |
| `backend/cutover_journal/__init__.py` | yes |
| `backend/cutover_journal/_canonical.py` | yes |
| `backend/cutover_journal/action_common.py` | yes |
| `backend/cutover_journal/chain_reducer.py` | yes |
| `backend/cutover_journal/closed_classifier.py` | yes |
| `backend/cutover_journal/contracts_bridge.py` | yes |
| `backend/cutover_journal/durability.py` | yes |
| `backend/cutover_journal/effect_permit.py` | yes |
| `backend/cutover_journal/effect_guard.py` | yes |
| `backend/cutover_journal/effect_state.py` | yes |
| `backend/cutover_journal/errors.py` | yes |
| `backend/cutover_journal/journal_chain.py` | yes |
| `backend/cutover_journal/journal_record.py` | yes |
| `backend/cutover_journal/journal_store.py` | yes |
| `backend/cutover_journal/journal_types.py` | yes |
| `backend/cutover_journal/operation_binding.py` | yes |
| `backend/cutover_journal/pending_classifier.py` | yes |
| `backend/cutover_journal/record_schema.py` | yes |
| `backend/cutover_journal/recovery.py` | yes |
| `backend/cutover_journal/recovery_classifier.py` | yes |
| `backend/cutover_journal/recovery_types.py` | yes |
| `backend/cutover_journal/resume_actions.py` | yes |
| `backend/cutover_journal/rollback_actions.py` | yes |
| `backend/cutover_journal/store_support.py` | yes |
| `backend/cutover_journal/transaction.py` | yes |
| `backend/real_host_preflight/__init__.py` | yes |
| `backend/real_host_preflight/audit_bridge.py` | yes |
| `backend/real_host_preflight/audit_types.py` | yes |
| `backend/real_host_preflight/authorization_gate.py` | yes |
| `backend/real_host_preflight/baseline.py` | yes |
| `backend/real_host_preflight/baseline_bridge.py` | yes |
| `backend/real_host_preflight/baseline_evidence.py` | yes |
| `backend/real_host_preflight/callbacks.py` | yes |
| `backend/real_host_preflight/canonical.py` | yes |
| `backend/real_host_preflight/collection.py` | yes |
| `backend/real_host_preflight/composition.py` | yes |
| `backend/real_host_preflight/contracts.py` | yes |
| `backend/real_host_preflight/contracts_bridge.py` | yes |
| `backend/real_host_preflight/errors.py` | yes |
| `backend/real_host_preflight/evidence.py` | yes |
| `backend/real_host_preflight/mutation_gate.py` | yes |
| `backend/real_host_preflight/operator_entry.py` | yes |
| `backend/real_host_preflight/receipts.py` | yes |
| `backend/real_host_preflight/sandbox_validation.py` | yes |
| `backend/real_host_preflight/topology.py` | yes |
| `backend/real_host_preflight/topology_evidence.py` | yes |
| `backend/real_host_preflight/windows_api.py` | yes |
| `backend/real_host_preflight/windows_chain.py` | yes |
| `backend/real_host_preflight/windows_observation.py` | yes |
| `backend/real_host_preflight/windows_paths.py` | yes |
| `backend/real_host_preflight/windows_projection.py` | yes |
| `backend/migration_evidence/__init__.py` | yes |
| `backend/migration_evidence/package.py` | yes |
| `backend/migration_evidence/review.py` | yes |
| `backend/migration_evidence/verification.py` | yes |
| `backend/reparenting_rehearsal/__init__.py` | yes |
| `backend/reparenting_rehearsal/rehearsal.py` | yes |
| `backend/runtime_activation_rehearsal/__init__.py` | yes |
| `backend/runtime_activation_rehearsal/rehearsal.py` | yes |
| `backend/runtime_activation_rehearsal/service_checks.py` | yes |
| `backend/mailbox_ingest/governed_scan.py` | yes |
| `backend/mailbox_ingest/sales_corpus_index.py` | yes |
| `backend/mailbox_ingest/sales_message_policy.py` | yes |
| `backend/mailbox_ingest/sales_policy_file.py` | yes |
| `backend/email_agent/__init__.py` | yes |
| `backend/email_agent/analysis_schema.py` | yes |
| `backend/email_agent/analysis_budget.py` | yes |
| `backend/email_agent/analysis_diagnostics.py` | yes |
| `backend/email_agent/analysis_model_routes.py` | yes |
| `backend/email_agent/analysis_provider_policy.py` | yes |
| `backend/email_agent/analysis_route_support.py` | yes |
| `backend/email_agent/attachment_media_context.py` | yes |
| `backend/email_agent/attachment_parser.py` | yes |
| `backend/email_agent/attachment_safety.py` | yes |
| `backend/email_agent/attachment_storage.py` | yes |
| `backend/email_agent/config.py` | yes |
| `backend/email_agent/managed_runtime.py` | yes |
| `backend/email_agent/managed_runtime_errors.py` | yes |
| `backend/email_agent/managed_runtime_validation.py` | yes |
| `backend/email_agent/logging_config.py` | yes |
| `backend/email_agent/email_cleaner.py` | yes |
| `backend/email_agent/analyzer.py` | yes |
| `backend/email_agent/rule_analyzer.py` | yes |
| `backend/email_agent/llm_client.py` | yes |
| `backend/email_agent/database.py` | yes |
| `backend/email_agent/exporter.py` | yes |
| `backend/email_agent/api.py` | yes |
| `backend/email_agent/server.py` | yes |
| `backend/email_agent/frontend_assets.py` | yes |
| `backend/email_agent/image_media_safety.py` | yes |
| `backend/email_agent/llm_errors.py` | yes |
| `backend/email_agent/model_context_selection.py` | yes |
| `backend/email_agent/model_cross_language_grounding.py` | yes |
| `backend/email_agent/model_grounding.py` | yes |
| `backend/email_agent/model_multimodal_claim_safety.py` | yes |
| `backend/email_agent/model_request.py` | yes |
| `backend/email_agent/model_result_safety.py` | yes |
| `backend/email_agent/model_source_grounding.py` | yes |
| `backend/email_agent/model_visual_grounding.py` | yes |
| `backend/email_agent/multimodal_media.py` | yes |
| `backend/email_agent/office_embedded_media.py` | yes |
| `backend/email_agent/openai_multimodal_client.py` | yes |
| `backend/email_agent/participant_identity_aliases.py` | yes |
| `backend/email_agent/pdf_media_safety.py` | yes |
| `backend/email_agent/private_context_gate.py` | yes |
| `backend/email_agent/private_provider_output_gate.py` | yes |
| `backend/email_agent/prompt_context.py` | yes |
| `backend/email_agent/thread_prompt_projection.py` | yes |
| `frontend/local_debug_page/index.html` | yes |
| `frontend/local_debug_page/app.js` | yes |
| `frontend/local_debug_page/styles.css` | yes |
| `frontend/browser_extension/manifest.json` | yes |
| `frontend/browser_extension/popup.html` | yes |
| `frontend/browser_extension/popup.css` | yes |
| `frontend/browser_extension/popup.js` | yes |
| `frontend/browser_extension/content/current_message_collector.js` | yes |
| `frontend/browser_extension/content/exmail_adapter.js` | yes |
| `frontend/browser_extension/content/exmail_visible_context.js` | yes |
| `frontend/browser_extension/content/exmail_visible_resource_classifier.js` | yes |
| `frontend/browser_extension/shared/api_client.js` | yes |
| `frontend/browser_extension/shared/manual_attachment_files.js` | yes |
| `frontend/browser_extension/shared/render_analysis.js` | yes |
| `frontend/browser_extension/shared/analysis_components.css` | yes |
| `docs/constraints/tooling_constraints.md` | yes |
| `docs/constraints/architecture_constraints.md` | yes |
| `docs/constraints/linter_constraints.md` | yes |
| `docs/constraints/mechanical_rule_translation.md` | yes |
| `docs/security/project_container_cutover_contracts.md` | yes |
| `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md` | yes |
| `docs/decisions/0007-multimodal-current-email-analysis.md` | yes |
| `docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md` | yes |
| `docs/decisions/0009-project-container-and-repository-boundaries.md` | yes |
| `docs/operations/authorized_mailbox_ingest_task_brief.md` | yes |
| `docs/operations/bounded_corpus_runtime_handoffs_task_brief.md` | yes |
| `docs/operations/issue11_governed_sales_corpus_task_brief.md` | yes |
| `docs/operations/deepseek_analysis_contract_alignment_task_brief.md` | yes |
| `docs/operations/private_deepseek_evaluation_task_brief.md` | yes |
| `docs/operations/private_mailbox_rollout_closeout_task_brief.md` | yes |
| `docs/operations/multimodal_current_email_analysis_task_brief.md` | yes |
| `docs/operations/current_email_grounding_and_attachment_repair_task_brief.md` | yes |
| `docs/operations/issue32_managed_container_mode_task_brief.md` | yes |
| `docs/operations/issue35_migration_evidence_package_task_brief.md` | yes |
| `docs/operations/issue36_reparenting_rehearsal_task_brief.md` | yes |
| `docs/operations/issue37_managed_runtime_localdata_rehearsal_task_brief.md` | yes |
| `docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md` | yes |
| `docs/operations/issue52_crash_safe_journal_recovery_task_brief.md` | yes |
| `docs/operations/issue53_windows_real_host_preflight_task_brief.md` | yes |
| `docs/operations/project_status_log.md` | yes |
| `docs/operations/project_status_log_guide.md` | yes |
| `docs/operations/agents_project_status_snippet.md` | yes |
| `docs/operations/cleanup_agent.md` | yes |
| `docs/operations/cleanup_agent_codex.md` | yes |
| `docs/operations/codex_cleanup_task.md` | yes |
| `docs/operations/documentation_rules.md` | yes |
| `docs/operations/first_version_task_brief.md` | yes |
| `docs/operations/tencent_exmail_browser_extension_task_brief.md` | yes |
| `docs/templates/agent_task_brief_template.md` | yes |
| `docs/templates/cleanup_task_template.md` | yes |
| `scripts/repo_utils.py` | yes |
| `scripts/maintenance_scan.py` | yes |
| `scripts/repository_leakage_scan.py` | yes |
| `scripts/generate_project_status.py` | yes |
| `scripts/run_local_debug.py` | yes |
| `scripts/manage_local_service.py` | yes |
| `scripts/manage_mailbox_vault.py` | yes |
| `scripts/manage_private_knowledge.py` | yes |
| `scripts/evaluate_private_deepseek.py` | yes |
| `start_local_service.cmd` | yes |
| `stop_local_service.cmd` | yes |
| `restart_local_service.cmd` | yes |
| `status_local_service.cmd` | yes |
| `tests/fixtures/sample_emails.json` | yes |
| `tests/test_analysis_schema.py` | yes |
| `tests/test_analysis_model_routes.py` | yes |
| `tests/test_golden_email_analysis.py` | yes |
| `tests/test_rule_analyzer.py` | yes |
| `tests/test_database.py` | yes |
| `tests/test_server.py` | yes |
| `tests/test_frontend_local_debug.py` | yes |
| `tests/test_repo_utils.py` | yes |
| `tests/test_config.py` | yes |
| `tests/test_run_local_debug.py` | yes |
| `tests/test_manage_local_service.py` | yes |
| `tests/test_managed_container_mode.py` | yes |
| `tests/test_migration_evidence_no_clobber.py` | yes |
| `tests/test_migration_evidence_restore.py` | yes |
| `tests/test_migration_evidence_verification.py` | yes |
| `tests/test_reparenting_rehearsal_rollback.py` | yes |
| `tests/test_reparenting_rehearsal_safety.py` | yes |
| `tests/test_reparenting_rehearsal_success.py` | yes |
| `tests/test_runtime_activation_rehearsal_architecture.py` | yes |
| `tests/test_runtime_activation_rehearsal_integration.py` | yes |
| `tests/test_runtime_activation_rehearsal_service.py` | yes |
| `tests/cutover_contract_fixtures.py` | yes |
| `tests/test_cutover_authorization_contract.py` | yes |
| `tests/test_cutover_contract_architecture.py` | yes |
| `tests/test_cutover_profile_contract.py` | yes |
| `tests/test_cutover_receipt_contract.py` | yes |
| `tests/cutover_journal_fixtures.py` | yes |
| `tests/test_cutover_journal_architecture.py` | yes |
| `tests/test_cutover_journal_chain.py` | yes |
| `tests/test_cutover_journal_crash_matrix.py` | yes |
| `tests/test_cutover_journal_durability.py` | yes |
| `tests/test_cutover_journal_record_contract.py` | yes |
| `tests/test_cutover_journal_recovery.py` | yes |
| `tests/real_host_preflight_fixtures.py` | yes |
| `tests/test_real_host_preflight_architecture.py` | yes |
| `tests/test_real_host_preflight_baseline.py` | yes |
| `tests/test_real_host_preflight_composition.py` | yes |
| `tests/test_real_host_preflight_gate.py` | yes |
| `tests/test_real_host_preflight_leakage.py` | yes |
| `tests/test_real_host_preflight_portable.py` | yes |
| `tests/test_real_host_preflight_topology.py` | yes |
| `tests/test_real_host_preflight_windows.py` | yes |
| `tests/test_real_host_preflight_windows_composition.py` | yes |
| `tests/support.py` | yes |
| `tests/test_architecture_constraints.py` | yes |
| `tests/test_current_evidence_handoff.py` | yes |
| `tests/test_static_linter_constraints.py` | yes |
| `tests/test_mechanical_rule_constraints.py` | yes |
| `tests/test_mailbox_transport_constraints.py` | yes |
| `tests/test_mailbox_governed_scan.py` | yes |
| `tests/test_mailbox_sales_corpus_index.py` | yes |
| `tests/test_maintenance_scan.py` | yes |
| `tests/test_generate_project_status.py` | yes |
| `tests/test_repository_leakage_scan.py` | yes |
| `tests/test_rollout_closeout_contracts.py` | yes |
| `tests/test_email_cleaner.py` | yes |
| `tests/test_analyzer.py` | yes |
| `tests/test_api.py` | yes |
| `tests/test_browser_extension_manifest.py` | yes |
| `tests/test_browser_extension_static.py` | yes |
| `tests/test_browser_extension_behavior.py` | yes |
| `tests/test_browser_extension_renderer_behavior.py` | yes |
| `tests/test_browser_extension_manual_attachment_files.py` | yes |
| `tests/test_browser_extension_task_focused_ui.py` | yes |
| `tests/test_browser_extension_visible_resource_classifier.py` | yes |
| `tests/test_model_grounding.py` | yes |
| `tests/test_model_result_safety.py` | yes |
| `tests/test_multimodal_documentation_contracts.py` | yes |
| `tests/test_multimodal_media.py` | yes |
| `tests/test_office_embedded_media.py` | yes |
| `tests/test_openai_multimodal_client.py` | yes |

## docs Directory Status

| File | Exists |
|---|---|
| `docs/product` | yes |
| `docs/knowledge_base` | yes |
| `docs/prompts` | yes |
| `docs/data` | yes |
| `docs/api` | yes |
| `docs/security` | yes |
| `docs/constraints` | yes |
| `docs/conventions` | yes |
| `docs/decisions` | yes |
| `docs/operations` | yes |
| `docs/templates` | yes |

## docs Metadata Summary

| Status | Count |
|---|---:|
| active | 96 |
| draft | 25 |
| deprecated | 4 |
| missing_front_matter | 0 |

## Recommended Next Steps

1. Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled` outside a separately authorized, bounded live test process; all providers remain disabled by default, and offline completion does not authorize live operation.
2. Task 9 synthetic provider and current-clicked Tencent smokes are complete. Task 9 forced OpenAI-to-DeepSeek synthetic fallback is complete: one OpenAI attempt was intercepted before network access, exactly one DeepSeek text-only request was made, DeepSeek SDK retries were zero, and no SQLite write occurred. The root `.env` was unchanged.
3. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. The evidence-reconciliation and private human gold-standard gates pass offline and the reviewed repair is integrated into the current release line.
4. Any new live operation still requires fresh explicit authorization.
5. Keep the administrator-only mailbox CLI and click-only current-message runtime as separate authorization surfaces.
6. Run the content-free repository leakage scan and complete final verification before release; preserve unrelated working-copy changes and keep any remote push separate.

## Do Not Touch Boundaries

- 浏览器扩展和正常运行时不接入真实邮箱账号；唯一例外是管理员手动运行的单账户只读导入 CLI。
- 浏览器扩展和正常运行时不读取真实邮箱数据；管理员 CLI 只处理授权范围并先确认 inventory fingerprint。
- 不自动发送邮件。
- 不自动删除邮件。
- 不自动归档邮件。
- 浏览器扩展和正常运行时不自动扫描所有邮件；管理员 CLI 没有 schedule、后台轮询或自动模型推理。
- 不把 OpenAI API key 放入前端。
- 不新增依赖，除非先更新约束文档并获得确认。
- 不放宽任何测试、linter 或架构约束。
- 真实 migration evidence package 必须先展示 exact target、content-free inclusion/exclusion manifest、reviewed local refs 和 worktree selection，并在单独确认前停止。
- Issue #36 只证明 temporary synthetic rehearsal；不得把它当作真实 migration、audit、worktree repair 或 cutover 授权。
- Issue #37 只证明 injected-adapter temporary synthetic activation rehearsal；不得把它当作真实 runtime、SQLite、artifact activation 或 cutover 授权。
- Issue #51 只建立 pure content-free contracts；四种 real-host authorization 只能验证外部 canonical values，不能 create、issue 或 mint，且默认 operator entry 保持 BLOCKED。
- Issue #52 只建立 pathless synthetic journal/recovery proof；pending/unbarriered record 不授权 effect，每次 owner claim 与 durable-intent permit 都是 exact synthetic capability，observed/pending/profile/identity/mapping fail closed，restart inspection 只读，且不得触碰真实 host 或 private capability。
- Issue #53 只建立 test-sandbox-owned Windows read-only observation 与窄 callback composition；真实 operator entry 继续 BLOCKED，不得把 receipt、test authorization 或 readiness 当作 mutation/cutover authority。

## Notes for Agent

- 先读 `AGENTS.md`，再读本文件。
- 涉及工具、架构、linter、机械规则、安全边界时，继续读 `docs/constraints/`。
- 涉及任务执行前规划时，填写 `docs/templates/agent_task_brief_template.md`。
- 不要把项目进度流水账写入 `AGENTS.md`。
