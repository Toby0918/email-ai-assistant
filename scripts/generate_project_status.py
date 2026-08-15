"""Generate an Agent-readable project progress snapshot.

Run:
    python scripts/generate_project_status.py --output docs/operations/project_status_log.md
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

try:
    from scripts.repo_utils import parse_front_matter_field, read_text
except ModuleNotFoundError:
    from repo_utils import parse_front_matter_field, read_text


ROOT = Path(__file__).resolve().parents[1]

# Key files define the handoff surface for the next Agent.
KEY_FILES = [
    "AGENTS.md",
    "README.md",
    ".env.example",
    "requirements.txt",
    ".gitignore",
    ".github/workflows/agent_guardrails.yml",
    ".github/workflows/cleanup_agent.yml",
    "backend/current_evidence/__init__.py",
    "backend/current_evidence/artifact_policy.py",
    "backend/current_evidence/contract.py",
    "backend/current_evidence/handoff.py",
    "backend/r2_production_binding/_adapter_identity.py",
    "backend/r2_production_binding/__init__.py",
    "backend/r2_production_composition/__init__.py",
    "backend/r2_production_composition/adapter_binding.py",
    "backend/r2_production_composition/catalog.py",
    "backend/r2_production_composition/preflight.py",
    "backend/r2_production_composition/evidence.py",
    "backend/r2_production_composition/transaction.py",
    "backend/r2_production_composition/binding_candidate.py",
    "docs/operations/r2_production_adapter_binding_remediation_task_brief.md",
    "backend/r2_solo_maintainer_closure/__init__.py",
    "backend/r2_solo_maintainer_closure/_canonical.py",
    "backend/r2_solo_maintainer_closure/contracts.py",
    "backend/r2_solo_maintainer_closure/evidence.py",
    "backend/r2_solo_maintainer_closure/hosted_evidence.py",
    "backend/r2_solo_maintainer_closure/local_evidence.py",
    "backend/r2_solo_maintainer_closure/repository.py",
    "backend/r2_solo_maintainer_closure/github_guardrail.py",
    "backend/r2_solo_maintainer_closure/storage.py",
    "backend/r2_solo_maintainer_closure/closure.py",
    "backend/r2_production_binding/execution_confirmation.py",
    "scripts/close_r2_final_master.py",
    "scripts/verify_r2_final_master_closure.py",
    "tests/test_r2_solo_maintainer_closure.py",
    "tests/test_r2_solo_maintainer_github_guardrail.py",
    "tests/test_r2_solo_maintainer_closure_architecture.py",
    "tests/test_close_r2_final_master.py",
    "tests/test_r2_execution_confirmation.py",
    "tests/test_r2_execution_confirmation_architecture.py",
    "docs/operations/r2_solo_maintainer_closure_task_brief.md",
    "docs/operations/r2_github_guardrail_response_compatibility_task_brief.md",
    "docs/operations/r2_solo_maintainer_closure_runbook.md",
    "docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md",
    "docs/decisions/0011-authenticated-github-guardrail-observation.md",
    "backend/cutover_contracts/__init__.py",
    "backend/cutover_contracts/_canonical.py",
    "backend/cutover_contracts/authorization.py",
    "backend/cutover_contracts/authorization_schema.py",
    "backend/cutover_contracts/authorization_validation.py",
    "backend/cutover_contracts/errors.py",
    "backend/cutover_contracts/operator_entry.py",
    "backend/cutover_contracts/profile.py",
    "backend/cutover_contracts/profile_schema.py",
    "backend/cutover_contracts/receipt.py",
    "backend/cutover_contracts/receipt_matrix.py",
    "backend/cutover_contracts/receipt_schema.py",
    "backend/cutover_contracts/receipt_types.py",
    "backend/cutover_journal/__init__.py",
    "backend/cutover_journal/_canonical.py",
    "backend/cutover_journal/action_common.py",
    "backend/cutover_journal/chain_reducer.py",
    "backend/cutover_journal/closed_classifier.py",
    "backend/cutover_journal/contracts_bridge.py",
    "backend/cutover_journal/durability.py",
    "backend/cutover_journal/effect_permit.py",
    "backend/cutover_journal/effect_guard.py",
    "backend/cutover_journal/effect_state.py",
    "backend/cutover_journal/errors.py",
    "backend/cutover_journal/journal_chain.py",
    "backend/cutover_journal/journal_record.py",
    "backend/cutover_journal/journal_store.py",
    "backend/cutover_journal/journal_types.py",
    "backend/cutover_journal/operation_binding.py",
    "backend/cutover_journal/pending_classifier.py",
    "backend/cutover_journal/record_schema.py",
    "backend/cutover_journal/recovery.py",
    "backend/cutover_journal/recovery_classifier.py",
    "backend/cutover_journal/recovery_types.py",
    "backend/cutover_journal/resume_actions.py",
    "backend/cutover_journal/rollback_actions.py",
    "backend/cutover_journal/store_support.py",
    "backend/cutover_journal/transaction.py",
    "backend/real_host_preflight/__init__.py",
    "backend/real_host_preflight/audit_bridge.py",
    "backend/real_host_preflight/audit_types.py",
    "backend/real_host_preflight/authorization_gate.py",
    "backend/real_host_preflight/baseline.py",
    "backend/real_host_preflight/baseline_bridge.py",
    "backend/real_host_preflight/baseline_evidence.py",
    "backend/real_host_preflight/callbacks.py",
    "backend/real_host_preflight/canonical.py",
    "backend/real_host_preflight/collection.py",
    "backend/real_host_preflight/composition.py",
    "backend/real_host_preflight/contracts.py",
    "backend/real_host_preflight/contracts_bridge.py",
    "backend/real_host_preflight/errors.py",
    "backend/real_host_preflight/evidence.py",
    "backend/real_host_preflight/integrity.py",
    "backend/real_host_preflight/mutation_gate.py",
    "backend/real_host_preflight/operator_entry.py",
    "backend/real_host_preflight/profile_snapshot.py",
    "backend/real_host_preflight/receipts.py",
    "backend/real_host_preflight/sandbox_lease.py",
    "backend/real_host_preflight/sandbox_state.py",
    "backend/real_host_preflight/sandbox_validation.py",
    "backend/real_host_preflight/topology.py",
    "backend/real_host_preflight/topology_evidence.py",
    "backend/real_host_preflight/windows_api.py",
    "backend/real_host_preflight/windows_chain.py",
    "backend/real_host_preflight/windows_observation.py",
    "backend/real_host_preflight/windows_paths.py",
    "backend/real_host_preflight/windows_projection.py",
    "backend/migration_evidence/__init__.py",
    "backend/migration_evidence/archive_validation.py",
    "backend/migration_evidence/package.py",
    "backend/migration_evidence/results.py",
    "backend/migration_evidence/review.py",
    "backend/migration_evidence/verification.py",
    "backend/migration_evidence_publication/__init__.py",
    "backend/migration_evidence_publication/canonical.py",
    "backend/migration_evidence_publication/contracts_bridge.py",
    "backend/migration_evidence_publication/creator_bridge.py",
    "backend/migration_evidence_publication/errors.py",
    "backend/migration_evidence_publication/host_baseline_bridge.py",
    "backend/migration_evidence_publication/operator_entry.py",
    "backend/migration_evidence_publication/package_observation.py",
    "backend/migration_evidence_publication/profile_binding.py",
    "backend/migration_evidence_publication/profile_git_binding.py",
    "backend/migration_evidence_publication/publication.py",
    "backend/migration_evidence_publication/publication_receipts.py",
    "backend/migration_evidence_publication/published_scope.py",
    "backend/migration_evidence_publication/receipt_set.py",
    "backend/migration_evidence_publication/receipts.py",
    "backend/migration_evidence_publication/review.py",
    "backend/migration_evidence_publication/review_bridge.py",
    "backend/migration_evidence_publication/selection.py",
    "backend/migration_evidence_publication/selection_state.py",
    "backend/migration_evidence_publication/synthetic_scope.py",
    "backend/migration_evidence_publication/verification_composition.py",
    "backend/migration_evidence_verifier/__init__.py",
    "backend/migration_evidence_verifier/bridge.py",
    "backend/migration_evidence_verifier/canonical.py",
    "backend/migration_evidence_verifier/contracts.py",
    "backend/migration_evidence_verifier/package_read.py",
    "backend/migration_evidence_verifier/process.py",
    "backend/migration_evidence_verifier/process_tree.py",
    "backend/migration_evidence_verifier/worker.py",
    "backend/cutover_host_mutation/__init__.py",
    "backend/cutover_host_mutation/acl_contracts.py",
    "backend/cutover_host_mutation/acl_journal.py",
    "backend/cutover_host_mutation/acl_paths.py",
    "backend/cutover_host_mutation/acl_receipt_factory.py",
    "backend/cutover_host_mutation/acl_state.py",
    "backend/cutover_host_mutation/canonical.py",
    "backend/cutover_host_mutation/errors.py",
    "backend/cutover_host_mutation/filesystem_contracts.py",
    "backend/cutover_host_mutation/filesystem_state.py",
    "backend/cutover_host_mutation/journal_intent.py",
    "backend/cutover_host_mutation/operator_entry.py",
    "backend/cutover_host_mutation/receipts.py",
    "backend/cutover_host_mutation/roles.py",
    "backend/cutover_host_mutation/source_acl_compatibility.py",
    "backend/cutover_host_mutation/windows_acl.py",
    "backend/cutover_host_mutation/windows_acl_adapter.py",
    "backend/cutover_host_mutation/windows_acl_apply.py",
    "backend/cutover_host_mutation/windows_acl_apply_bindings.py",
    "backend/cutover_host_mutation/windows_acl_factory.py",
    "backend/cutover_host_mutation/windows_construction_acl.py",
    "backend/cutover_host_mutation/windows_directory.py",
    "backend/cutover_host_mutation/windows_directory_factory.py",
    "backend/cutover_host_mutation/windows_directory_native.py",
    "backend/cutover_host_mutation/windows_directory_resources.py",
    "backend/cutover_host_mutation/windows_filesystem.py",
    "backend/cutover_host_mutation/windows_filesystem_common.py",
    "backend/cutover_host_mutation/windows_handles.py",
    "backend/cutover_host_mutation/windows_native_bindings.py",
    "backend/cutover_host_mutation/windows_no_replace.py",
    "backend/cutover_host_mutation/windows_no_replace_factory.py",
    "backend/cutover_host_mutation/windows_security.py",
    "backend/cutover_host_mutation/windows_security_bindings.py",
    "backend/cutover_host_mutation/windows_security_projection.py",
    "backend/cutover_host_mutation/windows_sid.py",
    "backend/cutover_repository_transaction/__init__.py",
    "backend/cutover_repository_transaction/contracts.py",
    "backend/cutover_repository_transaction/container_audit_bridge.py",
    "backend/cutover_repository_transaction/durable_store.py",
    "backend/cutover_repository_transaction/errors.py",
    "backend/cutover_repository_transaction/failed_evidence.py",
    "backend/cutover_repository_transaction/forward.py",
    "backend/cutover_repository_transaction/forward_recovery.py",
    "backend/cutover_repository_transaction/git_inspection.py",
    "backend/cutover_repository_transaction/git_executable.py",
    "backend/cutover_repository_transaction/git_recreation.py",
    "backend/cutover_repository_transaction/git_runner.py",
    "backend/cutover_repository_transaction/issue52_bridge.py",
    "backend/cutover_repository_transaction/journal_record.py",
    "backend/cutover_repository_transaction/journal_chain.py",
    "backend/cutover_repository_transaction/journal_identity.py",
    "backend/cutover_repository_transaction/journal_types.py",
    "backend/cutover_repository_transaction/mutation_executor.py",
    "backend/cutover_repository_transaction/real_lock.py",
    "backend/cutover_repository_transaction/restart_classification.py",
    "backend/cutover_repository_transaction/reverse.py",
    "backend/cutover_repository_transaction/reverse_checkpoint.py",
    "backend/cutover_repository_transaction/reverse_plan.py",
    "backend/cutover_repository_transaction/reverse_resume.py",
    "backend/cutover_repository_transaction/scope_models.py",
    "backend/cutover_repository_transaction/scope_paths.py",
    "backend/cutover_repository_transaction/stable_observation.py",
    "backend/cutover_repository_transaction/synthetic_scope.py",
    "backend/cutover_repository_transaction/transaction.py",
    "backend/cutover_repository_transaction/transaction_types.py",
    "backend/cutover_repository_transaction/verification.py",
    "backend/cutover_repository_transaction/windows_identity.py",
    "backend/cutover_managed_activation/__init__.py",
    "backend/cutover_managed_activation/adapters.py",
    "backend/cutover_managed_activation/artifact_publisher.py",
    "backend/cutover_managed_activation/canonical.py",
    "backend/cutover_managed_activation/config_contract.py",
    "backend/cutover_managed_activation/config_publisher.py",
    "backend/cutover_managed_activation/database_copier.py",
    "backend/cutover_managed_activation/errors.py",
    "backend/cutover_managed_activation/phase.py",
    "backend/cutover_managed_activation/publication_scope.py",
    "backend/cutover_managed_activation/real_lock.py",
    "backend/cutover_managed_activation/receipts.py",
    "backend/cutover_managed_activation/runtime_archive.py",
    "backend/cutover_managed_activation/runtime_builder.py",
    "backend/cutover_managed_activation/runtime_capture.py",
    "backend/cutover_managed_activation/runtime_execution.py",
    "backend/cutover_managed_activation/runtime_limits.py",
    "backend/cutover_managed_activation/runtime_policy.py",
    "backend/cutover_managed_activation/runtime_source_tree.py",
    "backend/cutover_managed_activation/runtime_tree.py",
    "backend/cutover_managed_activation/runtime_verification.py",
    "backend/cutover_managed_activation/scope_models.py",
    "backend/cutover_managed_activation/scope_paths.py",
    "backend/cutover_managed_activation/scope_profile.py",
    "backend/cutover_managed_activation/stopped_service.py",
    "backend/cutover_managed_activation/synthetic_scope.py",
    "backend/cutover_managed_activation/windows_file_handles.py",
    "backend/cutover_managed_activation/windows_directory_monitor.py",
    "backend/cutover_managed_activation/windows_publication_io.py",
    "backend/cutover_managed_activation/windows_streams.py",
    "backend/cutover_service_lifecycle/__init__.py",
    "backend/cutover_service_lifecycle/activation_contracts.py",
    "backend/cutover_service_lifecycle/activation_validation.py",
    "backend/cutover_service_lifecycle/adapters.py",
    "backend/cutover_service_lifecycle/canonical.py",
    "backend/cutover_service_lifecycle/contracts.py",
    "backend/cutover_service_lifecycle/controller.py",
    "backend/cutover_service_lifecycle/errors.py",
    "backend/cutover_service_lifecycle/failures.py",
    "backend/cutover_service_lifecycle/legacy_contracts.py",
    "backend/cutover_service_lifecycle/legacy_recovery.py",
    "backend/cutover_service_lifecycle/lifecycle.py",
    "backend/cutover_service_lifecycle/lifecycle_binding.py",
    "backend/cutover_service_lifecycle/real_lock.py",
    "backend/cutover_service_lifecycle/rollback_adapters.py",
    "backend/cutover_service_lifecycle/rollback_contracts.py",
    "backend/cutover_service_lifecycle/rollback_validation.py",
    "backend/cutover_composition_contracts/__init__.py",
    "backend/cutover_composition_contracts/authorization_sequence.py",
    "backend/cutover_composition_contracts/binding.py",
    "backend/cutover_composition_contracts/canonical.py",
    "backend/cutover_composition_contracts/chain.py",
    "backend/cutover_composition_contracts/errors.py",
    "backend/cutover_composition_contracts/receipts.py",
    "backend/real_host_preflight_composition/__init__.py",
    "backend/real_host_preflight_composition/composition.py",
    "backend/real_host_preflight_composition/contracts_bridge.py",
    "backend/real_host_preflight_composition/operator_entry.py",
    "backend/real_host_preflight_composition/roles.py",
    "backend/migration_evidence_publication_composition/__init__.py",
    "backend/migration_evidence_publication_composition/composition.py",
    "backend/migration_evidence_publication_composition/contracts_bridge.py",
    "backend/migration_evidence_publication_composition/operator_entry.py",
    "backend/migration_evidence_publication_composition/roles.py",
    "backend/cutover_transaction_composition/__init__.py",
    "backend/cutover_transaction_composition/composition.py",
    "backend/cutover_transaction_composition/contracts_bridge.py",
    "backend/cutover_transaction_composition/operator_entry.py",
    "backend/cutover_transaction_composition/roles.py",
    "backend/cutover_transaction_composition/state.py",
    "backend/reparenting_rehearsal/__init__.py",
    "backend/reparenting_rehearsal/rehearsal.py",
    "backend/runtime_activation_rehearsal/__init__.py",
    "backend/runtime_activation_rehearsal/rehearsal.py",
    "backend/runtime_activation_rehearsal/service_checks.py",
    "backend/mailbox" + "_ingest/governed_scan.py",
    "backend/mailbox" + "_ingest/sales_corpus_index.py",
    "backend/mailbox" + "_ingest/sales_message_policy.py",
    "backend/mailbox" + "_ingest/sales_policy_file.py",
    "backend/email_agent/__init__.py",
    "backend/email_agent/analysis_schema.py",
    "backend/email_agent/analysis_budget.py",
    "backend/email_agent/analysis_diagnostics.py",
    "backend/email_agent/analysis_model_routes.py",
    "backend/email_agent/analysis_provider_policy.py",
    "backend/email_agent/analysis_route_support.py",
    "backend/email_agent/attachment_media_context.py",
    "backend/email_agent/attachment_parser.py",
    "backend/email_agent/attachment_safety.py",
    "backend/email_agent/attachment_storage.py",
    "backend/email_agent/config.py",
    "backend/email_agent/managed_runtime.py",
    "backend/email_agent/managed_runtime_errors.py",
    "backend/email_agent/managed_runtime_validation.py",
    "backend/email_agent/logging_config.py",
    "backend/email_agent/email_cleaner.py",
    "backend/email_agent/analyzer.py",
    "backend/email_agent/rule_analyzer.py",
    "backend/email_agent/llm_client.py",
    "backend/email_agent/database.py",
    "backend/email_agent/exporter.py",
    "backend/email_agent/api.py",
    "backend/email_agent/server.py",
    "backend/email_agent/frontend_assets.py",
    "backend/email_agent/image_media_safety.py",
    "backend/email_agent/llm_errors.py",
    "backend/email_agent/model_context_selection.py",
    "backend/email_agent/model_cross_language_grounding.py",
    "backend/email_agent/model_grounding.py",
    "backend/email_agent/model_multimodal_claim_safety.py",
    "backend/email_agent/model_request.py",
    "backend/email_agent/model_result_safety.py",
    "backend/email_agent/model_source_grounding.py",
    "backend/email_agent/model_visual_grounding.py",
    "backend/email_agent/multimodal_media.py",
    "backend/email_agent/office_embedded_media.py",
    "backend/email_agent/openai_multimodal_client.py",
    "backend/email_agent/participant_identity_aliases.py",
    "backend/email_agent/pdf_media_safety.py",
    "backend/email_agent/private_context_gate.py",
    "backend/email_agent/private_provider_output_gate.py",
    "backend/email_agent/prompt_context.py",
    "backend/email_agent/thread_prompt_projection.py",
    "frontend/local_debug_page/index.html",
    "frontend/local_debug_page/app.js",
    "frontend/local_debug_page/styles.css",
    "frontend/browser_extension/manifest.json",
    "frontend/browser_extension/popup.html",
    "frontend/browser_extension/popup.css",
    "frontend/browser_extension/popup.js",
    "frontend/browser_extension/content/current_message_collector.js",
    "frontend/browser_extension/content/exmail_adapter.js",
    "frontend/browser_extension/content/exmail_visible_context.js",
    "frontend/browser_extension/content/exmail_visible_resource_classifier.js",
    "frontend/browser_extension/shared/api_client.js",
    "frontend/browser_extension/shared/manual_attachment_files.js",
    "frontend/browser_extension/shared/render_analysis.js",
    "frontend/browser_extension/shared/analysis_components.css",
    "docs/constraints/tooling_constraints.md",
    "docs/constraints/architecture_constraints.md",
    "docs/constraints/linter_constraints.md",
    "docs/constraints/mechanical_rule_translation.md",
    "docs/security/project_container_cutover_contracts.md",
    "docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md",
    "docs/decisions/0007-multimodal-current-email-analysis.md",
    "docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md",
    "docs/decisions/0009-project-container-and-repository-boundaries.md",
    "docs/operations/authorized_mailbox_ingest_task_brief.md",
    "docs/operations/bounded_corpus_runtime_handoffs_task_brief.md",
    "docs/operations/issue11_governed_sales_corpus_task_brief.md",
    "docs/operations/deepseek_analysis_contract_alignment_task_brief.md",
    "docs/operations/private_deepseek_evaluation_task_brief.md",
    "docs/operations/private_mailbox_rollout_closeout_task_brief.md",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "docs/operations/current_email_grounding_and_attachment_repair_task_brief.md",
    "docs/operations/issue32_managed_container_mode_task_brief.md",
    "docs/operations/issue35_migration_evidence_package_task_brief.md",
    "docs/operations/issue36_reparenting_rehearsal_task_brief.md",
    "docs/operations/issue37_managed_runtime_localdata_rehearsal_task_brief.md",
    "docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md",
    "docs/operations/issue52_crash_safe_journal_recovery_task_brief.md",
    "docs/operations/issue53_windows_real_host_preflight_task_brief.md",
    "docs/operations/issue54_migration_evidence_publication_task_brief.md",
    "docs/operations/issue55_windows_acl_filesystem_primitives_task_brief.md",
    "docs/operations/issue56_repository_worktree_transaction_task_brief.md",
    "docs/operations/issue57_managed_activation_publication_task_brief.md",
    "docs/operations/issue58_provider_disabled_activation_recovery_task_brief.md",
    "docs/operations/issue59_project_container_composition_task_brief.md",
    "docs/operations/issues70_83_r2_cutover_remediation_task_brief.md",
    "docs/operations/r2_synthetic_verification_criteria.md",
    "docs/operations/r2_synthetic_verification_evidence.md",
    "docs/operations/project_status_log.md",
    "docs/operations/project_status_log_guide.md",
    "docs/operations/agents_project_status_snippet.md",
    "docs/operations/cleanup_agent.md",
    "docs/operations/cleanup_agent_codex.md",
    "docs/operations/codex_cleanup_task.md",
    "docs/operations/documentation_rules.md",
    "docs/operations/first_version_task_brief.md",
    "docs/operations/tencent_exmail_browser_extension_task_brief.md",
    "docs/templates/agent_task_brief_template.md",
    "docs/templates/cleanup_task_template.md",
    "scripts/repo_utils.py",
    "scripts/maintenance_scan.py",
    "scripts/repository_leakage_scan.py",
    "scripts/generate_project_status.py",
    "scripts/verify_r2_synthetic_topology.py",
    "scripts/run_local_debug.py",
    "scripts/manage_local_service.py",
    "scripts/manage_mailbox_vault.py",
    "scripts/manage_private" + "_knowledge.py",
    "scripts/evaluate_private_deepseek.py",
    "start_local_service.cmd",
    "stop_local_service.cmd",
    "restart_local_service.cmd",
    "status_local_service.cmd",
    "tests/fixtures/sample_emails.json",
    "tests/test_analysis_schema.py",
    "tests/test_analysis_model_routes.py",
    "tests/test_golden_email_analysis.py",
    "tests/test_rule_analyzer.py",
    "tests/test_database.py",
    "tests/test_server.py",
    "tests/test_frontend_local_debug.py",
    "tests/test_repo_utils.py",
    "tests/test_config.py",
    "tests/test_run_local_debug.py",
    "tests/test_manage_local_service.py",
    "tests/test_managed_container_mode.py",
    "tests/test_migration_evidence_no_clobber.py",
    "tests/migration_evidence_publication_fixtures.py",
    "tests/test_migration_evidence_publication_architecture.py",
    "tests/test_migration_evidence_publication_commit_binding.py",
    "tests/test_migration_evidence_publication_create_verify.py",
    "tests/test_migration_evidence_publication_operator.py",
    "tests/test_migration_evidence_publication_package_observation.py",
    "tests/test_migration_evidence_publication_receipts.py",
    "tests/test_migration_evidence_publication_review.py",
    "tests/cutover_host_mutation_fixtures.py",
    "tests/test_cutover_host_mutation_architecture.py",
    "tests/test_cutover_host_mutation_contracts.py",
    "tests/test_cutover_host_mutation_operator.py",
    "tests/test_cutover_host_mutation_portable.py",
    "tests/test_cutover_host_mutation_windows_acl.py",
    "tests/test_cutover_host_mutation_windows_filesystem.py",
    "tests/cutover_repository_transaction_fixtures.py",
    "tests/test_cutover_repository_transaction_architecture.py",
    "tests/test_cutover_repository_transaction_contracts.py",
    "tests/test_cutover_repository_transaction_crash_gaps.py",
    "tests/test_cutover_repository_transaction_durable_store.py",
    "tests/test_cutover_repository_transaction_fail_closed.py",
    "tests/test_cutover_repository_transaction_journal.py",
    "tests/test_cutover_repository_transaction_real_lock.py",
    "tests/test_cutover_repository_transaction_windows_round_trip.py",
    "tests/test_cutover_repository_transaction_windows_boundary_reverse.py",
    "tests/test_cutover_repository_transaction_windows_scope.py",
    "tests/cutover_managed_activation_fixtures.py",
    "tests/test_cutover_managed_activation_architecture.py",
    "tests/test_cutover_managed_activation_contracts.py",
    "tests/test_cutover_managed_activation_fail_closed.py",
    "tests/test_cutover_managed_activation_real_lock.py",
    "tests/test_cutover_managed_activation_windows_edges.py",
    "tests/test_cutover_service_lifecycle_activation.py",
    "tests/test_cutover_service_lifecycle_architecture.py",
    "tests/test_cutover_service_lifecycle_contracts.py",
    "tests/test_cutover_service_lifecycle_leakage.py",
    "tests/test_cutover_service_lifecycle_real_lock.py",
    "tests/test_cutover_service_lifecycle_rollback.py",
    "tests/test_cutover_service_lifecycle_windows_sandbox.py",
    "tests/cutover_composition_fixtures.py",
    "tests/cutover_composition_binders.py",
    "tests/project_container_composition_windows_fixtures.py",
    "tests/test_cutover_composition_architecture.py",
    "tests/test_cutover_composition_operator_lock.py",
    "tests/test_cutover_composition_receipt_chain.py",
    "tests/test_cutover_composition_coverage_contract.py",
    "tests/test_cutover_composition_leakage.py",
    "tests/test_real_host_preflight_composition_root.py",
    "tests/test_migration_evidence_publication_composition_root.py",
    "tests/test_cutover_transaction_composition_root.py",
    "tests/test_project_container_composition_windows_end_to_end.py",
    "tests/windows_reparse_fixtures.py",
    "tests/test_migration_evidence_restore.py",
    "tests/test_migration_evidence_verification.py",
    "tests/test_migration_evidence_verifier_architecture.py",
    "tests/test_migration_evidence_verifier_process.py",
    "tests/test_reparenting_rehearsal_rollback.py",
    "tests/test_reparenting_rehearsal_safety.py",
    "tests/test_reparenting_rehearsal_success.py",
    "tests/test_runtime_activation_rehearsal_architecture.py",
    "tests/test_runtime_activation_rehearsal_integration.py",
    "tests/test_runtime_activation_rehearsal_service.py",
    "tests/cutover_contract_fixtures.py",
    "tests/test_cutover_authorization_contract.py",
    "tests/test_cutover_contract_architecture.py",
    "tests/test_cutover_profile_contract.py",
    "tests/test_cutover_receipt_contract.py",
    "tests/cutover_journal_fixtures.py",
    "tests/test_cutover_journal_architecture.py",
    "tests/test_cutover_journal_chain.py",
    "tests/test_cutover_journal_crash_matrix.py",
    "tests/test_cutover_journal_durability.py",
    "tests/test_cutover_journal_record_contract.py",
    "tests/test_cutover_journal_recovery.py",
    "tests/real_host_preflight_fixtures.py",
    "tests/test_real_host_preflight_architecture.py",
    "tests/test_real_host_preflight_baseline.py",
    "tests/test_real_host_preflight_composition.py",
    "tests/test_real_host_preflight_gate.py",
    "tests/test_real_host_preflight_leakage.py",
    "tests/test_real_host_preflight_portable.py",
    "tests/test_real_host_preflight_topology.py",
    "tests/test_real_host_preflight_windows.py",
    "tests/test_real_host_preflight_windows_composition.py",
    "tests/support.py",
    "tests/test_architecture_constraints.py",
    "tests/test_current_evidence_handoff.py",
    "tests/test_static_linter_constraints.py",
    "tests/test_mechanical_rule_constraints.py",
    "tests/test_mailbox_transport_constraints.py",
    "tests/test_mailbox_governed_scan.py",
    "tests/test_mailbox_sales_corpus_index.py",
    "tests/test_maintenance_scan.py",
    "tests/test_generate_project_status.py",
    "tests/test_repository_leakage_scan.py",
    "tests/test_rollout_closeout_contracts.py",
    "tests/test_r2_full_topology_windows.py",
    "tests/test_r2_semantic_gap_matrix.py",
    "tests/test_r2_verification_architecture.py",
    "tests/test_r2_verification_evidence_contracts.py",
    "tests/test_r2_production_adapter_binding_v1.py",
    "tests/test_r2_production_composition_v1.py",
    "tests/test_r2_production_composition_v1_architecture.py",
    "tests/test_r2_production_binding_candidate_v1.py",
    "tests/test_email_cleaner.py",
    "tests/test_analyzer.py",
    "tests/test_api.py",
    "tests/test_browser_extension_manifest.py",
    "tests/test_browser_extension_static.py",
    "tests/test_browser_extension_behavior.py",
    "tests/test_browser_extension_renderer_behavior.py",
    "tests/test_browser_extension_manual_attachment_files.py",
    "tests/test_browser_extension_task_focused_ui.py",
    "tests/test_browser_extension_visible_resource_classifier.py",
    "tests/test_model_grounding.py",
    "tests/test_model_result_safety.py",
    "tests/test_multimodal_documentation_contracts.py",
    "tests/test_multimodal_media.py",
    "tests/test_office_embedded_media.py",
    "tests/test_openai_multimodal_client.py",
]

DOC_DIRS = [
    "docs/product",
    "docs/knowledge_base",
    "docs/prompts",
    "docs/data",
    "docs/api",
    "docs/security",
    "docs/constraints",
    "docs/conventions",
    "docs/decisions",
    "docs/operations",
    "docs/templates",
]

GUARDRAILS = [
    ("Project entry rules", "AGENTS.md"),
    ("Tooling constraints", "docs/constraints/tooling_constraints.md"),
    ("Architecture constraints", "docs/constraints/architecture_constraints.md"),
    ("Static linter constraints", "docs/constraints/linter_constraints.md"),
    ("Mechanical rule translation", "docs/constraints/mechanical_rule_translation.md"),
    ("CI guardrails", ".github/workflows/agent_guardrails.yml"),
    ("Cleanup automation", "docs/operations/cleanup_agent_codex.md"),
    ("Maintenance scan", "scripts/maintenance_scan.py"),
    ("Repository leakage scan", "scripts/repository_leakage_scan.py"),
    ("Agent task brief", "docs/templates/agent_task_brief_template.md"),
    (
        "Authorized mailbox ingest boundary",
        "docs/operations/authorized_mailbox_ingest_task_brief.md",
    ),
    (
        "Bounded corpus-to-runtime handoffs",
        "docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md",
    ),
    (
        "Governed sales corpus bootstrap",
        "docs/operations/issue11_governed_sales_corpus_task_brief.md",
    ),
    (
        "No-clobber migration evidence package",
        "docs/operations/issue35_migration_evidence_package_task_brief.md",
    ),
    (
        "Synthetic repository reparenting rehearsal",
        "docs/operations/issue36_reparenting_rehearsal_task_brief.md",
    ),
    (
        "Synthetic Managed runtime activation rehearsal",
        "docs/operations/issue37_managed_runtime_localdata_rehearsal_task_brief.md",
    ),
    (
        "Locked cutover contracts",
        "docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md",
    ),
    (
        "Synthetic crash-safe journal and recovery classification",
        "docs/operations/issue52_crash_safe_journal_recovery_task_brief.md",
    ),
    (
        "Content-free Windows real-host preflight composition",
        "docs/operations/issue53_windows_real_host_preflight_task_brief.md",
    ),
    (
        "Reviewed Migration Evidence publication and verification",
        "docs/operations/issue54_migration_evidence_publication_task_brief.md",
    ),
    (
        "Fixed-role Windows ACL and no-clobber primitives",
        "docs/operations/issue55_windows_acl_filesystem_primitives_task_brief.md",
    ),
    (
        "Reversible mixed-topology repository transaction",
        "docs/operations/issue56_repository_worktree_transaction_task_brief.md",
    ),
    (
        "Create-only managed activation publication",
        "docs/operations/issue57_managed_activation_publication_task_brief.md",
    ),
    (
        "Provider-disabled activation and legacy recovery transaction",
        "docs/operations/issue58_provider_disabled_activation_recovery_task_brief.md",
    ),
    (
        "Project Container cutover contract security boundary",
        "docs/security/project_container_cutover_contracts.md",
    ),
    (
        "R2 production Adapter binding remediation",
        "docs/operations/r2_production_adapter_binding_remediation_task_brief.md",
    ),
    (
        "R2 Solo Maintainer Closure boundary",
        "docs/operations/r2_solo_maintainer_closure_task_brief.md",
    ),
    (
        "R2 Solo Maintainer Closure operator sequence",
        "docs/operations/r2_solo_maintainer_closure_runbook.md",
    ),
    (
        "Solo Maintainer Closure and execution-confirmation decision",
        "docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md",
    ),
]

AUTHORIZED_PRIVATE_INGEST_FILES = {
    "docs/constraints/architecture_constraints.md",
    "docs/operations/authorized_mailbox_ingest_task_brief.md",
    "docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md",
}

AUTHORIZED_PRIVATE_READY_FILES = {
    "backend/email_agent/private_context_gate.py",
    "scripts/manage_mailbox_vault.py",
    "scripts/evaluate_private_deepseek.py",
    "scripts/repository_leakage_scan.py",
    "docs/operations/private_deepseek_evaluation_task_brief.md",
    "docs/operations/private_mailbox_rollout_closeout_task_brief.md",
}

MULTIMODAL_CURRENT_EMAIL_READY_FILES = {
    "frontend/browser_extension/content/exmail_visible_context.js",
    "frontend/browser_extension/content/exmail_visible_resource_classifier.js",
    "frontend/browser_extension/shared/render_analysis.js",
    "backend/email_agent/multimodal_media.py",
    "backend/email_agent/openai_multimodal_client.py",
    "backend/email_agent/analysis_model_routes.py",
    "backend/email_agent/model_grounding.py",
    "backend/email_agent/model_visual_grounding.py",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "tests/test_openai_multimodal_client.py",
    "tests/test_analysis_model_routes.py",
    "tests/test_browser_extension_task_focused_ui.py",
}

HARD_BOUNDARIES = [
    "浏览器扩展和正常运行时不接入真实邮箱账号；唯一例外是管理员手动运行的单账户只读导入 CLI。",
    "浏览器扩展和正常运行时不读取真实邮箱数据；管理员 CLI 只处理授权范围并先确认 inventory fingerprint。",
    "不自动发送邮件。",
    "不自动删除邮件。",
    "不自动归档邮件。",
    "浏览器扩展和正常运行时不自动扫描所有邮件；管理员 CLI 没有 schedule、后台轮询或自动模型推理。",
    "不把 OpenAI API key 放入前端。",
    "不新增依赖，除非先更新约束文档并获得确认。",
    "不放宽任何测试、linter 或架构约束。",
    "真实 migration evidence package 必须先展示 exact target、content-free inclusion/exclusion manifest、reviewed local refs 和 worktree selection，并在单独确认前停止。",
    "Issue #36 只证明 temporary synthetic rehearsal；不得把它当作真实 migration、audit、worktree repair 或 cutover 授权。",
    "Issue #37 只证明 injected-adapter temporary synthetic activation rehearsal；不得把它当作真实 runtime、SQLite、artifact activation 或 cutover 授权。",
    "Issue #51 只建立 pure content-free contracts；四种 real-host authorization 只能验证外部 canonical values，不能 create、issue 或 mint，且默认 operator entry 保持 BLOCKED。",
    "Issue #52 只建立 pathless synthetic journal/recovery proof；pending/unbarriered record 不授权 effect，每次 owner claim 与 durable-intent permit 都是 exact synthetic capability，observed/pending/profile/identity/mapping fail closed，restart inspection 只读，且不得触碰真实 host 或 private capability。",
    "Issue #53 只建立 test-sandbox-owned Windows read-only observation 与窄 callback composition；真实 operator entry 继续 BLOCKED，不得把 receipt、test authorization 或 readiness 当作 mutation/cutover authority。",
    "Issue #54 只建立 profile-bound synthetic review、separately authorized create-only publication 与 separate read-only verifier；真实 entries 在 Issue #39 前继续 BLOCKED，receipts/Set 只是 content-free evidence，package 不是 backup、Runtime artifact、private-data container 或 migration authorization。",
    "Issue #55 只建立 test-owned NTFS sandbox 内的 fixed-role ACL 与 handle-relative no-clobber primitives；每个 effect 必须先消费 durable INTENT，真实 constructor 在 Issue #39 前继续 BLOCKED，不得把 test authorization、receipt 或 observation 当作 real-host authority。",
    "Issue #56 只证明 caller-owned synthetic Windows sandbox 内 exact 8 embedded + 3 external mixed-topology forward/reverse transaction；不得把 journal、receipt、crash classification 或测试结果当作真实 repository/worktree cutover、Issues #57-#59、#38/#39、merge 或父 Spec closure 授权。",
    "Issue #57 only proves create-only managed Runtime, LocalData, CRX, and Config publication inside caller-owned synthetic Windows sandboxes; receipts and tests do not authorize real activation, Issues #58/#59, Issues #38/#39, merge, or parent Spec closure.",
    "Issue #58 only proves provider-disabled activation, committed-journal-driven rollback, and dedicated legacy recovery inside caller-owned synthetic sandboxes; receipts and tests do not authorize a real service probe or operation, Issue #59, Issues #38/#39, merge, or parent Spec closure.",
    "Issue #59 only assembles three default-locked operator roots and a content-free receipt chain. Backend packages expose no executable test binder; test-only assembly owns every component TemporaryDirectory through one internal scope and rechecks it before every role or journal callback. Windows execution remains confined to caller-owned test sandboxes; no real command or authorization exists before #39. After merge, the final master invalidates R1 and requires all fourteen #38 approval items plus a new R2 before #39.",
    "Issues #70-#83 only implement dormant R2 contracts and fresh synthetic Windows proof. The fixed verifier owns its NTFS sandbox and emits aggregate fingerprints/counts; it does not authorize Issue #39, a real command, any host operation, merge, or approval/closure of #38 or #50. The accepted prototype fingerprint remains non-authorizing prior art.",
    "Issue #104 retains three exact stateful Adapter slots and owning-module source identity, but Issue #110 keeps every production Adapter path dormant before lookup. Neither issue authorizes a host operation, production artifact, Issue #38 approval, Issue #39, or closure.",
    "Issue #110 replaces the legacy V1 external-signature path with two strict Solo Maintainer Closure files and a dormant V3 execution-confirmation seam. Ruleset 20601214 exists for master; compatibility work is limited to authenticated fixed GET-only keyring observation, Python never reads the token, and only an exact empty required_reviewers beta field may be normalized. No live prepare, confirm, or protected verifier was run or authorized; #38/#39 remain unchanged, and no closure evidence authorizes host/provider/mailbox/vault/private-data access, cleanup, push, or merge.",
]


@dataclass(frozen=True)
class FileStatus:
    path: str
    exists: bool


@dataclass(frozen=True)
class GitStatus:
    branch: str


def run_git_command(args: Sequence[str]) -> str:
    command = ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "not available"
    if result.returncode != 0:
        return "not available"
    return result.stdout.strip() or "not available"


def get_git_status() -> GitStatus:
    branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    return GitStatus(branch=branch)


def collect_file_status(paths: Sequence[str]) -> list[FileStatus]:
    return [FileStatus(path=item, exists=(ROOT / item).exists()) for item in paths]


def count_docs_by_status() -> dict[str, int]:
    counts = {"active": 0, "draft": 0, "deprecated": 0, "missing_front_matter": 0}
    docs = ROOT / "docs"
    if not docs.exists():
        return counts
    for path in docs.rglob("*.md"):
        status = parse_front_matter_field(read_text(path), "status")
        if status in counts:
            counts[status] += 1
        else:
            counts["missing_front_matter"] += 1
    return counts


def infer_stage(files: Sequence[FileStatus]) -> str:
    existing = {item.path for item in files if item.exists}
    if MULTIMODAL_CURRENT_EMAIL_READY_FILES.issubset(existing):
        return "multimodal_current_email_offline_ready_live_pending"
    if AUTHORIZED_PRIVATE_READY_FILES.issubset(existing):
        return "authorized_private_analysis_offline_ready"
    if AUTHORIZED_PRIVATE_INGEST_FILES.issubset(existing):
        return "authorized_private_ingest_build"
    local_eval_files = {
        "tests/fixtures/sample_emails.json",
        "tests/test_golden_email_analysis.py",
    }
    if local_eval_files.issubset(existing):
        return "local_eval_mvp"
    first_version_files = {
        "backend/email_agent/api.py",
        "backend/email_agent/server.py",
        "frontend/local_debug_page/index.html",
        "frontend/local_debug_page/app.js",
        "scripts/run_local_debug.py",
        "tests/test_server.py",
        "tests/test_frontend_local_debug.py",
    }
    if first_version_files.issubset(existing):
        return "first_version_local_debug"
    if "backend/email_agent/api.py" in existing:
        return "backend_mvp"
    if "tests/test_generate_project_status.py" in existing and "scripts/maintenance_scan.py" in existing:
        return "agent_handoff_guardrails"
    if "docs/constraints/architecture_constraints.md" in existing:
        return "guardrails_setup"
    if "AGENTS.md" in existing:
        return "project_planning"
    return "not_initialized"


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def render_file_table(files: Sequence[FileStatus]) -> str:
    lines = ["| File | Exists |", "|---|---|"]
    lines.extend(f"| `{item.path}` | {format_bool(item.exists)} |" for item in files)
    return "\n".join(lines)


def render_doc_status(counts: dict[str, int]) -> str:
    lines = ["| Status | Count |", "|---|---:|"]
    for key in ("active", "draft", "deprecated", "missing_front_matter"):
        lines.append(f"| {key} | {counts.get(key, 0)} |")
    return "\n".join(lines)


def render_guardrails() -> str:
    rows = [FileStatus(path=f"{name}: {path}", exists=(ROOT / path).exists()) for name, path in GUARDRAILS]
    return render_file_table(rows)


def render_boundaries() -> str:
    return "\n".join(f"- {item}" for item in HARD_BOUNDARIES)


def render_next_steps(stage: str) -> str:
    if stage == "multimodal_current_email_offline_ready_live_pending":
        steps = [
            "Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled` outside a separately authorized, bounded live test process; all providers remain disabled by default, and offline completion does not authorize live operation.",
            "Task 9 synthetic provider and current-clicked Tencent smokes are complete. Task 9 forced OpenAI-to-DeepSeek synthetic fallback is complete: one OpenAI attempt was intercepted before network access, exactly one DeepSeek text-only request was made, DeepSeek SDK retries were zero, and no SQLite write occurred. The root `.env` was unchanged.",
            "Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. The evidence-reconciliation and private human gold-standard gates pass offline and the reviewed repair is integrated into the current release line.",
            "Any new live operation still requires fresh explicit authorization.",
            "Keep the administrator-only mailbox CLI and click-only current-message runtime as separate authorization surfaces.",
            "Run the content-free repository leakage scan and complete final verification before release; preserve unrelated working-copy changes and keep any remote push separate.",
        ]
    elif stage == "authorized_private_analysis_offline_ready":
        steps = [
            "Keep `EMAIL_AGENT_LLM_PROVIDER=disabled`; offline completion does not authorize live operation.",
            "Do not connect to a mailbox or run DeepSeek without a separate operator authorization after offline gates pass.",
            "Keep private evaluation blocked by default with `human_judge_unavailable`; the evaluator does not switch production models.",
            "If the signed private-knowledge snapshot is missing or invalid, preserve generic rule fallback.",
            "Run the content-free repository leakage scan and complete local human review before any release.",
        ]
    elif stage == "authorized_private_ingest_build":
        steps = [
            "Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` during implementation and automated verification.",
            "Implement later plan tasks with synthetic fakes and injected probes only.",
            "Do not connect to a mailbox or run DeepSeek without a separate operator authorization after offline gates pass.",
            "Preserve the click-only current-message Tencent Exmail Chrome / Edge 浏览器扩展 and normal runtime boundary.",
        ]
    elif stage in {"agent_handoff_guardrails", "guardrails_setup"}:
        steps = [
            "创建 `backend/email_agent/` 最小骨架。",
            "先实现邮件清洗、AI JSON 校验和本地 API 的测试。",
            "用脱敏样例验证“点击按钮分析当前邮件”流程。",
        ]
    elif stage == "local_eval_mvp":
        steps = [
            "运行完整测试和维护扫描。",
            "用虚构样例手动试用本地调试页面。",
            "提供 GitHub 远程地址后推送第一阶段项目。",
            "继续验证 Tencent Exmail Chrome / Edge 浏览器扩展原型；Outlook Add-in 和 Google Workspace Add-on 保持后续单独确认。",
        ]
    elif stage == "first_version_local_debug":
        steps = [
            "运行完整测试和维护扫描。",
            "用虚构样例手动试用本地调试页面。",
            "后续单独确认正式前端路线：Outlook Add-in、Google Workspace Add-on 或浏览器扩展。",
        ]
    elif stage == "backend_mvp":
        steps = ["运行完整测试。", "补充前端本地调试页面。", "更新 API 和数据 schema 文档。"]
    else:
        steps = ["创建 AGENTS.md。", "创建 docs/ 目录。", "写入项目边界和技术栈约束。"]
    return "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))


def _normalize_status_snapshot(value: str) -> bytes:
    """Canonicalize only the three environment-dependent snapshot fields."""
    if type(value) is not str or not value.endswith("\n"):
        raise ValueError("invalid status snapshot")
    if "\r" in value:
        if value.count("\r\n") != value.count("\n"):
            raise ValueError("invalid status line endings")
        value = value.replace("\r\n", "\n")
    lines = value.splitlines()

    def field(prefix: str, suffix: str = "") -> tuple[int, str]:
        matches = [(index, line) for index, line in enumerate(lines)
                   if line.startswith(prefix) and (not suffix or line.endswith(suffix))]
        if len(matches) != 1:
            raise ValueError("invalid status field")
        index, line = matches[0]
        end = len(line) - len(suffix) if suffix else len(line)
        return index, line[len(prefix):end]

    update_index, updated = field("last_update: ")
    generated_index, generated = field("| Generated on | ", " |")
    branch_index, branch = field("| Git branch | ", " |")
    if (date.fromisoformat(updated).isoformat() != updated or updated != generated
            or not 0 < len(branch) <= 128 or branch != branch.strip()
            or any(not 32 <= ord(character) <= 126 or character == "|"
                   for character in branch)):
        raise ValueError("invalid status dynamic value")
    lines[update_index] = "last_update: <snapshot-date>"
    lines[generated_index] = "| Generated on | <snapshot-date> |"
    lines[branch_index] = "| Git branch | <snapshot-branch> |"
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_project_status() -> str:
    git = get_git_status()
    files = collect_file_status(KEY_FILES)
    doc_dirs = collect_file_status(DOC_DIRS)
    doc_counts = count_docs_by_status()
    stage = infer_stage(files)
    today = date.today().isoformat()

    return f"""---
last_update: {today}
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
| Generated on | {today} |
| Current stage | {stage} |
| Git branch | {git.branch} |
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

Issue #32 Managed launcher is implemented for the exact `email_ai_assistant\\main` placement. It routes provider-disabled SQLite, attachment temp, logs, PID, runtime, artifact, worktree, and bounded non-secret Config paths to their approved zones while source and repository tooling remain at `main`. Synthetic loopback lifecycle verification passes, but no real Project Container migration or operational cutover has occurred.

Issue #34 manual content-free Container Audit is offline implemented behind seven injected read-only metadata adapters. Its exact nine-entry, ACL, volume, Git/worktree, runtime, SQLite, Config, Logs/Artifacts, and disabled-private-state contract fails closed and exposes only fixed status/counts. No real Container audit or host-security probe was run.

Issue #35 no-clobber migration evidence package is offline implemented as a manual internal Python contract. It binds exact reviewed local refs, branch-attached worktree identities, an allowlisted two-layer dirty-source snapshot, content-free Git/ACL/volume baselines, and every payload file with canonical SHA-256 evidence. Publication is external-target, create-only and fail-closed; verification restores Git objects, refs, dirty state and worktree identity in synthetic repositories. No real evidence package was created.

Issue #36 repository/worktree reparenting rehearsal is offline implemented as one pathless synthetic-only Python seam. It builds a temporary repository with a bound marker filesystem identity and a non-trivial Git baseline, creates and verifies one synthetic Issue #35 package, no-clobber moves the existing Git common directory and reviewed source into a synthetic `main`, applies injected repair/recreate worktree choices, verifies exact post-state and passes a synthetic ContainerAudit. All six publication-boundary failures verify rollback preservation; post-main failures preserve the complete Container at the single sibling rollback path. The public operation leaves the synthetic topology intact for independent caller observation. No real workspace, worktree, branch, directory, ACL, runtime, database or private data was touched; Issues #38 through #40 remain separate.

Issue #37 managed runtime and LocalData activation rehearsal is offline implemented behind exact five injected adapters and one pathless synthetic-only seam. Temporary synthetic sources prove a create-only pinned runtime, a Windows venv rebuilt from the exact dependency lock, `pre_publication` stopped-service create-only SQLite publication with identity/SHA-256/integrity/sidecar/count checks, reviewed-hash browser-extension publication, exact Managed writable roles, and one strict activation token across provider-disabled start, literal-loopback health, one persisted rule-fallback analysis and the same-service `post_activation` fresh-stop proof. Stale evidence and equality spoofing fail closed. The source database remains unchanged after success and every simulated race, reparse, existing-target, dependency, integrity or health failure. No real runtime, SQLite database, browser-extension artifact or migration evidence package was activated; Issues #38 through #40 remain separate.

Issue #51 locked Cutover Profile, authorization, and receipt contracts are offline implemented as a pure content-free Python contract layer. Immutable `CutoverProfileV1` values bind the reviewed cutover inputs without paths or host readers. The four distinct real-host authorization value types validate externally supplied canonical values and cannot create, issue, or mint authority. The strict canonical `ReceiptEnvelopeV1` values are duplicate/unknown rejecting, fingerprint-bound, and never accepted as authorization. `default_operator_entry()` remains fixed at `BLOCKED_NO_APPROVED_COMMAND`. Its approved consumers are the exact Issue #52 journal bridge, exact Issue #53 preflight contract bridge, exact Issue #54 evidence-publication contract bridge, exact Issue #55 mutation contract consumers, exact Issue #56 synthetic transaction scope consumers, exact Issue #57 synthetic managed-publication contract consumers, and exact Issue #58 synthetic lifecycle/real-lock consumers.

Issue #52 crash-safe journal and recovery classification are offline implemented in the pathless synthetic-only `backend.cutover_journal` package. Strict canonical create-only records bind sequence, previous/record hashes, fixed synthetic step/event/direction, operation/profile/authorization/owner fingerprints, and opaque observations. Every forward and reverse action uses durable `INTENT`, exact observed effect, and `COMMITTED`; each owner claim gets a distinct lease and each effect consumes a non-copyable, non-serializable single-use store permit bound to the exact active durable intent and durable journal head. The shared store-private issuance is atomically claimed; one synthetic medium operation gate serializes append, restart, permit mint/claim, and effect mutation; every namespace-published current head completes stable reread and full snapshot reverification before a successor append or permit. Stable-reread evidence is hash-bound, and head advance, pending state, or an observed fact invalidates stale permits. Pending or unbarriered records never authorize an effect; verified pending direction/event/outcome controls event-aware exact pending publication without effect replay or an extra action; durable observed facts are authoritative across fresh `RESUME_BOUND` renewal. Reverse steps are derived LIFO only from verified `COMMITTED/APPLIED` history. Exact Profile/master/operator, identity mapping, synthetic transition mapping, and post-effect observation all fail closed. Exact in-memory Windows/Linux traces prove file/namespace/stable-reread ordering without claiming real filesystem durability. Restart inspection is read-only, exact expected-post is never blindly repeated, and explicit resume/rollback fresh-validate phase-specific authorization including the pre-bound recovery fingerprint. Public results expose only fixed status, phase, receipt fingerprint, and allowlisted counts distinguishing `SAFE_ABORT`, `ROLLBACK_REQUIRED`, `INCIDENT_STOP`, and `CUTOVER_SUCCEEDED`. No real filesystem target, service, ACL, Git repository/worktree, Runtime, SQLite, provider, mailbox, vault, private data, preflight, migration, cutover, resume, or rollback was accessed or run; Issues #57 through #59 remain separate.

Issue #53 content-free Windows real-host preflight composition is offline implemented in `backend.real_host_preflight`. The package-private Windows observer opens every controlled path component without following reparse points and binds fixed-volume identity, 128-bit file identity, object type, parent identity, normalized-name fingerprint, attributes, reparse metadata, and exactly-one-link file alias evidence. Only exact, unexpired `TestSandboxAuthorizationV1` values plus a root/marker identity-bound atomically single-use permit can create test-owned temporary scopes; every observer operation reopens and validates the exact root and marker and holds both handle chains through the target observation, and no real project path was observed. `CurrentTopologyPreflight` captures an independent canonical Profile snapshot before any host callback, factory-reconstructs every callback value, binds source/parent/finance/target names to exact snapshot role selections, and requires two complete identical seven-reader observations. `PreMutationGate` is short-lived, UUIDv4 nonce-bound, single-operation and single-use; each topology receipt can be atomically claimed by at most one gate, and trusted receipt/gate state is module-owned with an exact nominal-class-to-observation-kind binding. `RealHostBaselineCollector` keeps source, parent, finance, volume, operator-SID, and three ACL roles separate while projecting the existing canonical `HostBaseline`. The unchanged nine-zone `ContainerAudit` receives exactly seven revalidated callbacks through a narrow bridge; final-audit readiness validates the identical bound readers without running or claiming a final-layout audit, and each execution uses a detached canonical policy plus freshly rebuilt adapters so callback-time mutation cannot relax policy or retarget readers. The zero-argument operator entry remains fixed at `BLOCKED_NO_APPROVED_COMMAND` and cannot accept test authorization. Production code has no service-control, ACL-apply, rename, worktree mutation, Runtime build, database copy, artifact, Config, provider, mailbox, vault, private-data, or content-reading capability. Windows behavior was exercised only in test-owned temporary sandboxes, and portable tests make no NTFS or Windows ACL claim. Issues #56 through #59, Issues #38/#39, and parent Spec #50 remain separate and unchanged.

Issue #54 reviewed Migration Evidence publication and verification is present for synthetic-only use in `backend.migration_evidence_publication` and `backend.migration_evidence_verifier`. Profile-bound review keeps the complete `MigrationEvidenceReview` in memory and exposes only `MigrationEvidenceReviewReceiptV1`; its test-only target-parent marker hard-link anchor rejects same-path replacement even when POSIX recycles directory identity. Create requires the exact `EvidencePublicationAuthorizationV1` and confirmed review fingerprint, then performs complete rediscovery and fresh HostBaseline collection before the existing create-only no-clobber commit; creator-owned source-snapshot, package, manifest, and published-identity bindings reject post-review or post-commit replacement. The creator cannot call the independent verifier. Verification runs in a separate read-only process, reads the package once through a bounded descriptor, verifies those exact bytes through the independent payload verifier, requires an identical target reread, and independently recomputes package/manifest hashes and counts without publication or mutation capability. `MigrationEvidenceReviewReceiptV1`, `MigrationEvidenceCreatedReceiptV1`, and `MigrationEvidenceVerifiedReceiptV1` must agree exactly before `MigrationEvidenceReceiptSetV1` can exist; receipts and the Set remain content-free evidence rather than authority. All real entries remain locked before Issue #39 and reject missing, wrong-phase, and test authorization. No real evidence package was created, and no host preflight, service, repository/worktree move, ACL, Runtime, database, provider, mailbox, vault, private-store, or private-data operation was run. The package is evidence, not a backup, Runtime artifact, private-data container, or migration authorization. Focused, affected, constraint, full-suite, maintenance, Standards, and Spec verification passed locally. Ready-for-review PR #63 already exists; the Linux inode-reuse repair still requires explicit allowlist stage, commit, and push before remote CI reruns, and merge remains unauthorized.

Issue #55 fixed-role Windows ACL and no-clobber filesystem primitives are offline implemented in `backend.cutover_host_mutation`. The public surface contains only closed portable ACL/filesystem observations and four content-free receipt types. The internal `WindowsAclAdapter` performs complete read-only source compatibility without reparse traversal, exact parent/finance capture-and-compare, and exact inheritance verification across eight fixed direct zones. The newly created empty Container is published by parent-handle-relative `NtCreateFile` with `FILE_CREATE` and a protected operator-only construction DACL that grants no child-creation right; root, marker, parent, and target handles remain held until the journaled final DACL linearization point. The final DACL grants inheritable Full Control only to the current token SID, SYSTEM, and built-in Administrators; owner/group are compared unchanged and the exact `SetSecurityInfo` call omits all owner/group/SACL flags and pointers. Create-only directory, file publication, and same-identity move effects require a durable Issue #52 INTENT, bind opened scope/source/parent handles, fixed NTFS volume, 128-bit file ID, parent identity and reparse-free state, set no-replace, and prove identical target identity. Native tests ran only in caller-owned temporary NTFS sandboxes; portable Linux tests claim no Windows ACL or NTFS behavior. The real constructor rejects test authorization and remains locked at `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. No real ACL, repository/worktree, service, Runtime, SQLite, provider, mailbox, vault, private store, or private data was accessed or changed. Issues #56 through #59, Issues #38/#39, and parent Spec #50 remain separate.

Issue #56 reversible mixed-topology repository/worktree transaction is offline implemented in `backend.cutover_repository_transaction`. A caller-owned temporary Windows sandbox binds the original Repository Root plus exactly eight embedded and three external clean reviewed worktrees, their refs/commits/common-directory identity, opened Git executable identity/version/content, physical identities, and opaque administrative entries. The fixed scope-bound Git runner denies executable write/delete sharing, revalidates executable content/identity in the same handle window before and after every allowlisted process, rejects unsafe local config at scope bind/rebind and unexpected administrative namespaces, suppresses repository hooks, bounds process-tree lifetime and output, and exposes no arbitrary command seam. Forward durably journals INTENT before each #55 no-replace or fixed Git effect, preserves every original physical/admin object before counterpart creation, relocates the original Repository Root identity to `main`, publishes the exact non-main zones create-only, recreates all eleven reviewed counterparts, and records the actual #55 object identity or Git observation in OBSERVED. COMMITTED requires an independent exact reread: filesystem targets are held against write/delete sharing, administrative values also bind opaque content, and Git values repeat relationship/ref/commit/clean-state verification. The journaled Container-create identity is the unchanged ContainerAudit trusted policy selection and must equal the freshly observed Container object; the three external worktrees remain under separate exact Git verification, and final Git verification rejects non-intentional local-ref or remote-configuration drift. Reverse accepts every complete forward boundary and safely classified forward crash gap; exact before-effect state appends `ABORTED/NOT_APPLIED`, exact after-effect state appends only missing facts without replay, and any published new state is retained before the original Repository Root, all eleven original administrative identities, and all eleven original physical identities are restored. Crash-gap classification remains exact `SAFE_ABORT`, `SAFE_COMMIT_FACTS`, or `INCIDENT_STOP`. An explicitly repeated reverse call derives the exact committed-stage plan, classifies and reconciles each safe reverse INTENT/effect/OBSERVED/COMMITTED crash gap, validates complete journal-bound failed evidence before any resumed mutation, validates the exact checkpoint, and continues only the remaining fixed mutations; the failed Container must retain the journaled Container identity. Ambiguity remains `INCIDENT_STOP`, and there is no background or implicit resume. Collision, after-INTENT target race, OBSERVED-to-COMMITTED drift, reparse, volume/scope, ref, remote, dirty, executable content/identity, physical, same-name admin reuse, unsafe Git config/hook, observation, zone-inventory, administrative-namespace, and topology drift fail closed. Journal, receipts, repr, stdout, and stderr are content-free. The real constructor remains `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. No real repository/worktree, service, ACL, Runtime, SQLite, provider, mailbox, vault, private store, or private data was accessed or changed. Issues #57 through #59, Issues #38/#39, and parent Spec #50 remain separate.

Issue #57 managed Runtime, LocalData, CRX, and Config publication is offline implemented in `backend.cutover_managed_activation`. `ManagedActivationPhase` composes exactly four narrow adapters, validates each receipt before the next callback, and returns one fingerprinted set that independently rebuilds all four complete typed receipt mappings and their common operation/Profile/master/authorization chain. Immutable scope snapshots bind every target name and hold root, marker, and target-parent handles; target creation is parent-handle-relative `NtCreateFile(FILE_CREATE)`, unsafe Windows components including ADS and superscript reserved-device syntax are rejected, and held file targets deny concurrent writers through final verification. The test harness materializes the approved Python distribution inside each caller-owned sandbox, and external source paths fail. A canonical manifest binds the complete CPython source tree, entry count, total bytes, executable hash, and tree fingerprint. Before target execution, every source entry is resource/reparse/ADS checked, held against write/delete sharing, and recursively monitored through verification. The approved distribution is streamed from held handles into an empty create-only Runtime root, so post-authorization additions to the mutable source namespace, including `_pth` startup paths, are never executed. The complete approved `Lib/encodings` package is streamed from held source handles into bounded deterministic ZIP_STORED `managed-startup.zip`; code-fixed create-only `python312._pth` and `python._pth` sentinels put that immutable archive before `Lib`/`DLLs`, omit `import site`, and remain held before target execution, preventing both pre-script encoding-package injection and later startup hooks. `LockedRuntimeBuilder` creates a fresh Runtime from that exact approved Python 3.12.13 source, a canonical lock enumerating the complete installed closure, and captured bytes from a hash-locked offline wheelhouse. It copies no prior venv, rejects `.pth`/`sitecustomize.py`/`usercustomize.py`, and has no PATH lookup, pip/index/network access, user-site, user cache, or live dependency resolution. Held-handle and remaining-aggregate gates precede source/wheel/lock allocation. Fixed wheel/archive/Runtime resource ceilings, pre-`ZipFile` central-directory bounds, expected-count wheelhouse and pre-sort tree enumeration bounds, and bounded streaming extraction, hashing, and subprocess stdout prevent unbounded allocation, buffering, or disk growth; stdout overflow terminates the child. A held exact Runtime tree binds the streamed CPython baseline plus every child-handle-relative wheel/lock addition and rejects junction/reparse, ADS, extra, missing, or changed entries. A recursive directory-change guard on the Runtime parent spans sealing, self-verification, and receipt construction; transient child or Runtime-root stream mutation yields no receipt. Under fixed `-X frozen_modules=on -I -B -S`, the new Runtime verifier imports only built-in `sys`, `nt`, `_sha2`, and `_imp`, proves `_imp.is_frozen("codecs")`, and rejects every later import; transient `Lib/codecs/__init__.py` cannot execute before the hook. It proves Python, SQLite, startup-ZIP, dependency-lock, exact installed-set, and import fingerprints from exact target bytes and bounded metadata; SQLite binary hashes are compared with the held approved source entries, so transient target packages cannot execute. `StoppedDatabaseCopier` requires an exact stopped-service receipt, holds a write-blocking source handle through copy and verification, rejects any WAL, SHM, or rollback journal before copy and again after final target verification, uses read-only/query-only integrity verification without application-row inspection, durably flushes a create-only destination, and requires an unchanged source identity and stable hash. The artifact publisher holds the source and target through receipt construction and a final exact reread, copies only one profile-bound reviewed CRX after exact format/size/hash validation, and cannot build, sign, install, load, or inspect a browser profile. The Config publisher emits deterministic non-secret Config canonical bytes from a closed allowlisted schema without environment, registry, credential-store, clipboard, hidden-input, mailbox, vault, or provider readers. Every collision, drift, or failure fails closed, and any partial or failed publication remains in place. Receipts, stdout, stderr, and errors are content-free. Each real constructor rejects missing or test authorization and remains `BLOCKED_NO_APPROVED_COMMAND` even after exact `CutoverExecutionAuthorizationV1` validation before Issue #39. No real Runtime, SQLite, CRX, Config, service, browser, repository/worktree, ACL, provider, mailbox, credential, vault, private store, or private data was accessed or changed. Issues #58/#59, Issues #38/#39, and parent Spec #50 remain separate.

Issue #58 provider-disabled activation and legacy recovery is offline implemented in `backend.cutover_service_lifecycle`. `ProviderDisabledServiceController` accepts only exact injected new-service and legacy-service role adapters. New activation validates the complete Issue #57 operation/Profile/master/authorization receipt chain, uses the reviewed managed Runtime and deterministic Config, forbids legacy-environment inheritance, keeps both providers disabled, and binds every start to a fresh UUIDv4 nonce. Health must match PID, start time, executable, port ownership, Profile, `LocalData` role, nonce, and provider-disabled state. The only activation input is one code-fixed synthetic request; acceptance requires a deterministic-rules result, exactly zero provider attempts, and exactly one matching synthetic row in the new `LocalData`. Known pre-mutation start rejection becomes `SAFE_ABORT` without containment or rollback. Known post-mutation validation failures become `ROLLBACK_REQUIRED`, while identity, journal, reparse, provider-boundary, safety, or unexpected post-start ambiguity becomes `INCIDENT_STOP` after exact containment. Rollback requires explicit synthetic authorization and an immutable plan binding the complete committed journal entries, original topology, ACL descriptors, database/sidecar state, legacy Runtime, and repository identity. Every fixed reverse stage chains the previous observation or receipt, restoration binds the actual #56 reverse receipt, and the transaction retains the failed Container, new external worktrees, and Git administrative evidence while proving restoration of the original main plus all eleven worktrees. Windows synthetic proof resumes every committed reverse boundary and rejects a pre-existing failed-Container collision. Legacy recovery uses a dedicated injected provider-disabled Config, a distinct fresh recovery nonce, no environment reader, and no synthetic analysis; failure is fixed as `INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED` with no retry, alternate launcher, or Config. Public receipts, journal bindings, stdout, stderr, and errors remain content-free. Real construction requires exact external cutover and recovery authorizations and still returns `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. No real service, repository/worktree, ACL, Runtime, SQLite, browser, mailbox, provider, credential, vault, private data, or host state was accessed or changed. Issue #59, Issues #38/#39, merge, and parent Spec #50 remain separate.

Issue #59 final Project Container composition is offline implemented across `backend.real_host_preflight_composition`, `backend.migration_evidence_publication_composition`, `backend.cutover_transaction_composition`, and the pure `backend.cutover_composition_contracts`. The three operator roots are physically separate, mutually non-importing, and accept only exact binding-bound nominal role bundles. Mechanical guards keep them out of normal runtime, browser, scripts, cleanup, scheduler, and workflows and reject arbitrary source, target, worktree, Runtime, database, artifact, Config, ACL, rollback, shell, PowerShell, or Git command inputs. Backend packages expose no executable test binder; test-only assembly requires an internally created temporary scope with no root-selection input, owns every component `TemporaryDirectory`, and rechecks it before every role or journal callback. Every real constructor and entry validates its exact phase authorization, rejects synthetic/test authorization, and still returns `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. `ProjectContainerReceiptChainV1` binds one operation, Profile, governing master, operator, authorization sequence, review, package verification, ACL baseline, fresh pre-mutation gate, one journal owner, linked prior/current journal heads, terminal receipt, activation, final audit, failed-Container preservation, rollback restoration, legacy health, and terminal recovery state. Every partial chain is an approved prefix, and its fingerprint commits its ordered recursively linked terminal receipt. Execute, resume, and rollback are single-action; the owner atomically claims the gate across composition objects, supplies the per-boundary authorization clock, and fail-closes receipt, predecessor, binding, freshness, journal, or state drift. Windows end-to-end proof composes the existing #53-#58 seams only in caller-owned temporary sandboxes, routes the forward ACL-through-activation path through transaction `execute()`, binds the #55 ACL policy receipt into the #56 Profile, uses the actual #56 journal, passes the exact #57 receipt set into #58, and reaches exact legacy recovery after failed activation with zero provider attempts; no substitute publication receipts are created. Portable/Linux tests make no NTFS or Windows ACL claim. No real preflight, evidence package, ACL, repository/worktree, Runtime, SQLite, CRX/Config, service, activation, rollback, provider, mailbox, vault, private store, or private-data operation occurred. Issue #38 remains open/ready-for-human, R1 remains `NOT EXECUTABLE`, and Issue #39 remains unstarted. Merging #59 changes the governing master, invalidates old R1, and requires all fourteen #38 approval items plus a new R2 against the exact final master before #39 can be considered.

Issues #70-#83 dormant R2 cutover remediation are offline implemented across the additive R2 contract, fixed preflight/evidence/transaction process, main/manifest/database/Runtime/CRX/Config publication, independent-audit, validation-lifecycle, cross-stage recovery, and verification-evidence packages. The fixed no-argument `scripts/verify_r2_synthetic_topology.py` owns one fresh physical NTFS sandbox and composes preflight, evidence, quiescence, legacy anchor, nine-zone Container/main/whole-tree ACL, one repository, all eleven reviewed worktrees, four managed units, Start A with one `rule_fallback` result and one row, stop, independent stopped audit, Start B without analysis/write, independent final-running audit, and one terminal `CUTOVER_SUCCESS`. Preflight, evidence, and transaction use distinct real local TTY processes; execution and recovery remain distinct fixed verbs and all four authorization domains are nominally separate. The exact seven-semantics, two-directions, five-gaps matrix covers 70 fresh scopes. Obsolete batched managed publication, stale R1 verification, in-process operator substitution, self-certified audit, and legacy R2 success are mechanically unreachable. Fresh criteria, matrix, script, bundle, complete R2 surface, and package fingerprints are recorded as six deterministic evidence fingerprints; the accepted prototype fingerprint remains non-authorizing prior art. Portable tests make no NTFS, ACL, TTY, process-isolation, or native-durability claim. Every real entry remains `BLOCKED_NO_APPROVED_COMMAND`; no real host, provider, mailbox, vault, private data, or Issue #39 operation was accessed or run, and #38/#50/#39 remain unchanged.

Issue #104 three-stateful-Adapter seam remains implemented offline in `backend.r2_production_composition`. The catalog retains three exact stateful Adapter slots covering six preflight commands, one evidence command, and three transaction commands. Binding captures and immediately reverifies command/domain, nominal type, complete owning-module source, class surface, registry and target identity; mutable instance state remains excluded. Underlying receipt/outcome validation still precedes completion. Issue #110 replaces candidate key/signature/envelope inputs with the exact Solo Maintainer final-master binding and closed `ApprovedCutoverBindingV3` structural facts. Synthetic Adapters remain testing-only, while every production root stops at `DORMANT_NO_ISSUE39_APPROVAL` before Adapter lookup. No real Adapter or host operation is created, and #38/#39 remain unchanged.

Issue #110 Solo Maintainer Closure is implemented in `backend.r2_solo_maintainer_closure`, `backend.r2_production_binding`, and `scripts/close_r2_final_master.py`. The strict two-file trust model binds one frozen clean master, the five exact GitHub Actions hosted checks, fourteen evidence records, eight ordered gap proofs, one exact active master-ruleset snapshot, one canonical manifest, and one Solo Maintainer Attestation with assurance counts one operator and zero independent/external/hosted-human reviewers. Private typed local proofs bind canonical values, relevant frozen blobs, same-SHA hosted records/job steps, and fresh status/maintenance/leakage observations without claiming durable runtime receipt instances. `ApprovedCutoverBindingV3` removes V2 public keys, signatures, envelopes, and issuers; execution confirmation binds closure, attestation, exact action/journal/plan/TTY/time facts and a create-only durable claim, but remains unreachable from production. The legacy final-master/global-gate/external-artifact/signature paths are removed rather than retained as aliases. GitHub ruleset `20601214` exists for `master`, and the private guardrail reader observes it through authenticated fixed GET-only GitHub CLI calls backed by the active keyring login; Python neither reads nor prints the token. The compatibility layer accepts only the additive beta `required_reviewers=[]` response shape and removes that exact empty field before canonical comparison; missing or non-empty bypass actors and every other drift fail closed. No live `prepare`, `confirm`, or protected verifier was run or authorized by this local compatibility work, and #38/#39 remain unchanged. Closure and CI evidence do not approve Issue #38, create or approve a ruleset, authorize or execute Issue #39, mutate a real host, access provider/mailbox/vault/private data, clean retained stages, push, or merge.

Issue #39 one-command Project Container orchestration is implemented on the current feature branch in `backend.r2_issue39_orchestrator` and `scripts/execute_project_container_cutover.py`. Its production order is zero-mutation closure/Issue #38/input/complete dynamic-roster readiness, fixed real-console confirmation, exact incident-stage disposition, fresh complete prepare, create-only evidence plus retained-anchor transfer, and a closed 27-action catalog with 24 host effects. Every host effect uses a fresh action-bound durable claim and journaled intent; restart classifies two stable observations without replaying an already-present effect, while rollback retains failed state. Terminal success requires a journal-reconstructed ordered validation receipt and two fresh full audits of layout, roster, Git, ACL, managed units, provider-disabled service identity, and the single deterministic rule-fallback row. This is implementation-only status: synthetic/test-owned Windows execution is permitted, but no real incident disposition, closure confirmation, protected verifier, or cutover has been run, and real execution still requires separate final authorization.

The selected daily frontend remains the Tencent Exmail Chrome / Edge 浏览器扩展, with current-message collection only after an explicit user click.

## Guardrails Established

{render_guardrails()}

## Key File Status

{render_file_table(files)}

## docs Directory Status

{render_file_table(doc_dirs)}

## docs Metadata Summary

{render_doc_status(doc_counts)}

## Recommended Next Steps

{render_next_steps(stage)}

## Do Not Touch Boundaries

{render_boundaries()}

## Notes for Agent

- 先读 `AGENTS.md`，再读本文件。
- 涉及工具、架构、linter、机械规则、安全边界时，继续读 `docs/constraints/`。
- 涉及任务执行前规划时，填写 `docs/templates/agent_task_brief_template.md`。
- 不要把项目进度流水账写入 `AGENTS.md`。
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "operations" / "project_status_log.md")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_project_status(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
