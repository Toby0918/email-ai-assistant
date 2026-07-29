"""Chain validation for committed-journal rollback evidence."""

from __future__ import annotations

from backend.cutover_contracts import TestSandboxAuthorizationV1

from .canonical import fail
from .rollback_contracts import (
    FailedContainerPublicationReceiptV1,
    LegacyPrerequisiteEvidenceV1,
    RollbackRestoreEvidenceV1,
    RollbackStageEvidenceV1,
)


def valid_recovery_authorization(value, observed, profile, operation):
    return (
        type(value) is TestSandboxAuthorizationV1
        and type(observed) is int
        and 0 <= observed < value.expires_at_epoch
        and value.profile_fingerprint == profile
        and value.operation_fingerprint == operation
        and value.phase == "rollback"
    )


def require_stage(value, stage, plan, previous) -> None:
    if (
        type(value) is not RollbackStageEvidenceV1
        or value.stage != stage.value
        or value.journal_head_fingerprint
        != plan.journal_head_fingerprint
        or value.rollback_plan_fingerprint != plan.plan_fingerprint
        or value.previous_observation_fingerprint != previous
    ):
        fail("lifecycle_rollback_stage_invalid")


def require_failed(value, plan, preserved) -> None:
    if (
        type(value) is not FailedContainerPublicationReceiptV1
        or value.journal_head_fingerprint
        != plan.journal_head_fingerprint
        or value.rollback_plan_fingerprint != plan.plan_fingerprint
        or value.preservation_observation_fingerprint
        != preserved.observation_fingerprint
        or value.classification
        != "FAILED_CONTAINER_SEALED_PENDING_LEGACY_MAIN_EXTRACTION"
    ):
        fail("lifecycle_failed_container_invalid")


def require_restored(value, failed, plan) -> None:
    if (
        type(value) is not RollbackRestoreEvidenceV1
        or value.journal_head_fingerprint
        != plan.journal_head_fingerprint
        or value.rollback_plan_fingerprint != plan.plan_fingerprint
        or value.original_topology_fingerprint
        != plan.original_topology_fingerprint
        or value.failed_container_receipt_fingerprint
        != failed.receipt_fingerprint
    ):
        fail("lifecycle_restore_invalid")


def require_prerequisites(value, restored, plan) -> None:
    if (
        type(value) is not LegacyPrerequisiteEvidenceV1
        or value.journal_head_fingerprint
        != plan.journal_head_fingerprint
        or value.rollback_plan_fingerprint != plan.plan_fingerprint
        or value.original_topology_fingerprint
        != plan.original_topology_fingerprint
        or value.rollback_observation_fingerprint
        != restored.observation_fingerprint
        or _prerequisite_values(value) != _prerequisite_values(plan)
    ):
        fail("lifecycle_legacy_prerequisites_invalid")


def _prerequisite_values(value):
    return (
        value.parent_descriptor_fingerprint,
        value.finance_descriptor_fingerprint,
        value.original_database_fingerprint,
        value.sidecar_state_fingerprint,
        value.legacy_runtime_fingerprint,
        value.repository_identity_fingerprint,
    )
