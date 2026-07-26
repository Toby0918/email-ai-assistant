"""Exact receipt type-to-schema compatibility matrix."""

from __future__ import annotations

from dataclasses import dataclass

from .receipt_types import (
    ReceiptOperation,
    ReceiptProducer,
    ReceiptStatus,
    ReceiptSubjectRole,
    ReceiptType,
)


@dataclass(frozen=True, slots=True)
class ReceiptSchema:
    operation: str
    producer: str
    subject_role: str
    statuses: tuple[str, ...]
    input_roles: tuple[str, ...]
    count_keys: tuple[str, ...]
    detail_values: tuple[tuple[str, tuple[str, ...]], ...]
    maximum_validity_seconds: int = 86_400


RECEIPT_SCHEMAS = {
    ReceiptType.PREFLIGHT.value: ReceiptSchema(
        operation=ReceiptOperation.REAL_PREFLIGHT.value,
        producer=ReceiptProducer.REAL_PREFLIGHT.value,
        subject_role=ReceiptSubjectRole.OPERATION.value,
        statuses=(
            ReceiptStatus.PREFLIGHT_ACCEPTED.value,
            ReceiptStatus.PREFLIGHT_REJECTED.value,
            ReceiptStatus.SAFE_ABORT.value,
        ),
        input_roles=("profile", "authorization", "policy"),
        count_keys=("accepted", "rejected"),
        detail_values=(
            (
                "observation_kind",
                (
                    "current_topology",
                    "repeated_current_topology",
                    "pre_mutation_gate",
                    "final_audit_readiness",
                    "recovery_inspection",
                ),
            ),
        ),
        maximum_validity_seconds=900,
    ),
    ReceiptType.EVIDENCE.value: ReceiptSchema(
        operation=ReceiptOperation.EVIDENCE_PUBLICATION.value,
        producer=ReceiptProducer.EVIDENCE_PUBLICATION.value,
        subject_role=ReceiptSubjectRole.EVIDENCE_PACKAGE.value,
        statuses=(
            ReceiptStatus.EVIDENCE_ACCEPTED.value,
            ReceiptStatus.EVIDENCE_REJECTED.value,
        ),
        input_roles=("profile", "authorization", "review"),
        count_keys=("packages", "verified", "rejected"),
        detail_values=(
            ("evidence_stage", ("review", "publication", "verification")),
        ),
    ),
    ReceiptType.ACL.value: ReceiptSchema(
        operation=ReceiptOperation.CUTOVER_EXECUTION.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.ACL_POLICY.value,
        statuses=(
            ReceiptStatus.ACL_ACCEPTED.value,
            ReceiptStatus.ACL_REJECTED.value,
        ),
        input_roles=(
            "profile",
            "authorization",
            "policy",
            "source_observation",
        ),
        count_keys=("accepted", "rejected"),
        detail_values=(
            (
                "acl_scope",
                ("container", "parent", "finance", "source_compatibility"),
            ),
        ),
    ),
    ReceiptType.REPOSITORY.value: ReceiptSchema(
        operation=ReceiptOperation.CUTOVER_EXECUTION.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.REPOSITORY_ROOT.value,
        statuses=(
            ReceiptStatus.REPOSITORY_ACCEPTED.value,
            ReceiptStatus.REPOSITORY_REJECTED.value,
        ),
        input_roles=(
            "profile",
            "authorization",
            "prior_receipt",
            "source_observation",
        ),
        count_keys=("accepted", "rejected"),
        detail_values=(
            (
                "repository_stage",
                (
                    "source_frozen",
                    "legacy_renamed",
                    "container_published",
                    "main_published",
                    "final_verified",
                ),
            ),
        ),
    ),
    ReceiptType.WORKTREE.value: ReceiptSchema(
        operation=ReceiptOperation.CUTOVER_EXECUTION.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.WORKTREE_ROSTER.value,
        statuses=(
            ReceiptStatus.WORKTREE_ACCEPTED.value,
            ReceiptStatus.WORKTREE_REJECTED.value,
        ),
        input_roles=(
            "profile",
            "authorization",
            "prior_receipt",
            "source_observation",
        ),
        count_keys=("worktrees", "rejected"),
        detail_values=(
            (
                "worktree_stage",
                ("preserved", "recreated", "final_verified"),
            ),
        ),
    ),
    ReceiptType.RUNTIME.value: ReceiptSchema(
        operation=ReceiptOperation.CUTOVER_EXECUTION.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.RUNTIME.value,
        statuses=(
            ReceiptStatus.RUNTIME_ACCEPTED.value,
            ReceiptStatus.RUNTIME_REJECTED.value,
        ),
        input_roles=("profile", "authorization", "artifact", "policy"),
        count_keys=("components", "rejected"),
        detail_values=(
            ("runtime_stage", ("inputs_verified", "built", "published")),
        ),
    ),
    ReceiptType.DATABASE.value: ReceiptSchema(
        operation=ReceiptOperation.CUTOVER_EXECUTION.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.DATABASE.value,
        statuses=(
            ReceiptStatus.DATABASE_ACCEPTED.value,
            ReceiptStatus.DATABASE_REJECTED.value,
        ),
        input_roles=(
            "profile",
            "authorization",
            "source_observation",
            "policy",
        ),
        count_keys=("databases", "rejected"),
        detail_values=(
            ("database_stage", ("source_locked", "published", "verified")),
        ),
    ),
    ReceiptType.ARTIFACT.value: ReceiptSchema(
        operation=ReceiptOperation.CUTOVER_EXECUTION.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.BROWSER_EXTENSION.value,
        statuses=(
            ReceiptStatus.ARTIFACT_ACCEPTED.value,
            ReceiptStatus.ARTIFACT_REJECTED.value,
        ),
        input_roles=("profile", "authorization", "artifact", "review"),
        count_keys=("artifacts", "rejected"),
        detail_values=(
            ("artifact_kind", ("browser_extension",)),
            ("artifact_stage", ("reviewed", "published", "verified")),
        ),
    ),
    ReceiptType.CONFIG.value: ReceiptSchema(
        operation=ReceiptOperation.CUTOVER_EXECUTION.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.CONFIG.value,
        statuses=(
            ReceiptStatus.CONFIG_ACCEPTED.value,
            ReceiptStatus.CONFIG_REJECTED.value,
        ),
        input_roles=("profile", "authorization", "config", "policy"),
        count_keys=("configurations", "rejected"),
        detail_values=(
            ("config_stage", ("generated", "published", "verified")),
        ),
    ),
    ReceiptType.ACTIVATION.value: ReceiptSchema(
        operation=ReceiptOperation.CUTOVER_EXECUTION.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.SERVICE.value,
        statuses=(
            ReceiptStatus.ACTIVATION_ACCEPTED.value,
            ReceiptStatus.ACTIVATION_REJECTED.value,
            ReceiptStatus.ROLLBACK_REQUIRED.value,
            ReceiptStatus.CUTOVER_SUCCEEDED.value,
        ),
        input_roles=("profile", "authorization", "prior_receipt", "config"),
        count_keys=("completed", "failed", "provider_attempts"),
        detail_values=(
            (
                "activation_stage",
                ("started", "health_verified", "rules_verified", "stopped"),
            ),
        ),
    ),
    ReceiptType.ROLLBACK.value: ReceiptSchema(
        operation=ReceiptOperation.RECOVERY.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.ROLLBACK.value,
        statuses=(
            ReceiptStatus.ROLLBACK_ACCEPTED.value,
            ReceiptStatus.ROLLBACK_REJECTED.value,
        ),
        input_roles=("profile", "authorization", "journal", "prior_receipt"),
        count_keys=("completed", "failed"),
        detail_values=(
            (
                "rollback_stage",
                (
                    "failed_container_preserved",
                    "main_restored",
                    "worktrees_restored",
                    "legacy_health_verified",
                ),
            ),
        ),
    ),
    ReceiptType.INCIDENT_STOP.value: ReceiptSchema(
        operation=ReceiptOperation.RECOVERY.value,
        producer=ReceiptProducer.CUTOVER_TRANSACTION.value,
        subject_role=ReceiptSubjectRole.OPERATION.value,
        statuses=(ReceiptStatus.INCIDENT_STOP.value,),
        input_roles=(
            "profile",
            "authorization",
            "journal",
            "source_observation",
        ),
        count_keys=("incidents",),
        detail_values=(
            (
                "incident_class",
                (
                    "identity_ambiguous",
                    "journal_ambiguous",
                    "safety_ambiguous",
                    "legacy_service_recovery_failed",
                ),
            ),
        ),
    ),
}
