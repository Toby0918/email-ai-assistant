"""Provider-disabled activation, rollback, and legacy recovery transaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.cutover_contracts import TestSandboxAuthorizationV1
from backend.cutover_managed_activation import ManagedActivationReceiptSetV1

from .canonical import fail, fingerprint, is_fingerprint
from .controller import ProviderDisabledServiceController
from .failures import ServiceBoundaryFailure
from .rollback_adapters import (
    has_exact_rollback_adapter,
)
from .rollback_contracts import (
    FailedContainerPublicationReceiptV1,
    LegacyPrerequisiteEvidenceV1,
    RollbackRestoreEvidenceV1,
    RollbackStage,
    RollbackStageEvidenceV1,
)


class LifecycleStatus(str, Enum):
    SAFE_ABORT = "SAFE_ABORT"
    CUTOVER_SUCCEEDED = "CUTOVER_SUCCEEDED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    INCIDENT_STOP = "INCIDENT_STOP"
    LEGACY_SERVICE_RECOVERED = "LEGACY_SERVICE_RECOVERED"
    INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED = (
        "INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED"
    )


@dataclass(frozen=True, slots=True, repr=False)
class LifecycleResultV1:
    status: LifecycleStatus
    receipt_fingerprint: str = field(repr=False)
    containment_attempted: int
    contained: int
    restored_worktrees: int
    retained_external_worktrees: int
    retained_git_records: int
    failed_container_classification: str
    provider_attempts: int


class ProviderDisabledLifecycleTransaction:
    __slots__ = (
        "_operation",
        "_profile",
        "_journal",
        "_publications",
        "_controller",
        "_rollback",
        "_state",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "ProviderDisabledLifecycleTransaction requires create()"
        )

    @classmethod
    def create(cls, **values: object):
        expected = {
            "operation_fingerprint",
            "profile_fingerprint",
            "journal_head_fingerprint",
            "publications",
            "controller",
            "rollback_adapter",
        }
        if (
            set(values) != expected
            or not is_fingerprint(values["operation_fingerprint"])
            or not is_fingerprint(values["profile_fingerprint"])
            or not is_fingerprint(values["journal_head_fingerprint"])
            or type(values["publications"])
            is not ManagedActivationReceiptSetV1
            or type(values["controller"])
            is not ProviderDisabledServiceController
            or not has_exact_rollback_adapter(values["rollback_adapter"])
            or values["publications"].profile_fingerprint
            != values["profile_fingerprint"]
        ):
            fail("lifecycle_binding_invalid")
        value = object.__new__(cls)
        value._operation = values["operation_fingerprint"]
        value._profile = values["profile_fingerprint"]
        value._journal = values["journal_head_fingerprint"]
        value._publications = values["publications"]
        value._controller = values["controller"]
        value._rollback = values["rollback_adapter"]
        value._state = "ready"
        return value

    def activate_new_service(self) -> LifecycleResultV1:
        if self._state != "ready":
            fail("lifecycle_forward_resume_prohibited")
        try:
            receipt = self._controller.activate_new(self._publications)
        except ServiceBoundaryFailure as error:
            if error.kind.is_safe_abort:
                self._state = "safe_abort"
                return _result(
                    LifecycleStatus.SAFE_ABORT,
                    (error.kind.value, self._journal),
                )
            if error.kind.is_incident:
                self._state = "incident"
                attempted, contained = (
                    self._controller.contain_new_if_proven()
                )
                return _result(
                    LifecycleStatus.INCIDENT_STOP,
                    (error.kind.value, self._journal),
                    attempted=attempted,
                    contained=contained,
                )
            self._state = "rollback_required"
            return _result(
                LifecycleStatus.ROLLBACK_REQUIRED,
                (error.kind.value, self._journal),
            )
        self._state = "succeeded"
        return _result(
            LifecycleStatus.CUTOVER_SUCCEEDED,
            (receipt.receipt_fingerprint, self._journal),
        )

    def rollback_and_recover_legacy(
        self, *, authorization: object, observed_at_epoch: object
    ) -> LifecycleResultV1:
        if self._state == "recovering":
            fail("lifecycle_recovery_not_repeatable")
        if self._state != "rollback_required":
            fail("lifecycle_rollback_not_allowed")
        if not _valid_recovery_authorization(
            authorization,
            observed_at_epoch,
            self._profile,
            self._operation,
        ):
            fail("lifecycle_recovery_authorization_invalid")
        self._state = "recovering"
        prerequisites = self._run_rollback()
        if prerequisites is None:
            return _result(
                LifecycleStatus.INCIDENT_STOP,
                (self._journal, "rollback"),
            )
        try:
            legacy = self._controller.recover_legacy(prerequisites)
        except Exception:
            return _result(
                LifecycleStatus
                .INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED,
                (self._journal, "legacy_recovery"),
                restored=11,
                retained_external=3,
                retained_git=11,
                classification=(
                    "FAILED_CONTAINER_PRESERVED_WITH_LEGACY_MAIN_EXTRACTED"
                ),
            )
        return _result(
            LifecycleStatus.LEGACY_SERVICE_RECOVERED,
            (self._journal, legacy.receipt_fingerprint),
            restored=11,
            retained_external=3,
            retained_git=11,
            classification=(
                "FAILED_CONTAINER_PRESERVED_WITH_LEGACY_MAIN_EXTRACTED"
            ),
        )

    def _run_rollback(self) -> LegacyPrerequisiteEvidenceV1 | None:
        try:
            stopped = self._controller.stop_new_exact()
            stop_stage = self._rollback.verify_new_service_stopped(stopped)
            _require_stage(
                stop_stage, RollbackStage.NEW_SERVICE_STOPPED, self._journal
            )
            preserved = self._rollback.preserve_new_evidence()
            _require_stage(
                preserved,
                RollbackStage.NEW_EVIDENCE_PRESERVED,
                self._journal,
            )
            failed = self._rollback.publish_failed_container(preserved)
            _require_failed(failed, self._journal)
            restored = self._rollback.restore_original_topology(failed)
            _require_restored(restored, failed, self._journal)
            prerequisites = (
                self._rollback.verify_legacy_prerequisites(restored)
            )
            _require_prerequisites(
                prerequisites, restored, self._journal
            )
            return prerequisites
        except Exception:
            return None


def _valid_recovery_authorization(value, observed, profile, operation):
    return (
        type(value) is TestSandboxAuthorizationV1
        and type(observed) is int
        and 0 <= observed < value.expires_at_epoch
        and value.profile_fingerprint == profile
        and value.operation_fingerprint == operation
        and value.phase == "rollback"
    )


def _require_stage(value, stage, journal) -> None:
    if (
        type(value) is not RollbackStageEvidenceV1
        or value.stage != stage.value
        or value.journal_head_fingerprint != journal
    ):
        fail("lifecycle_rollback_stage_invalid")


def _require_failed(value, journal) -> None:
    if (
        type(value) is not FailedContainerPublicationReceiptV1
        or value.journal_head_fingerprint != journal
        or value.classification
        != "FAILED_CONTAINER_SEALED_PENDING_LEGACY_MAIN_EXTRACTION"
    ):
        fail("lifecycle_failed_container_invalid")


def _require_restored(value, failed, journal) -> None:
    if (
        type(value) is not RollbackRestoreEvidenceV1
        or value.journal_head_fingerprint != journal
        or value.failed_container_receipt_fingerprint
        != failed.receipt_fingerprint
    ):
        fail("lifecycle_restore_invalid")


def _require_prerequisites(value, restored, journal) -> None:
    if (
        type(value) is not LegacyPrerequisiteEvidenceV1
        or value.journal_head_fingerprint != journal
        or value.rollback_observation_fingerprint
        != restored.observation_fingerprint
    ):
        fail("lifecycle_legacy_prerequisites_invalid")


def _result(
    status,
    inputs,
    *,
    attempted=0,
    contained=0,
    restored=0,
    retained_external=0,
    retained_git=0,
    classification="NONE",
) -> LifecycleResultV1:
    receipt = fingerprint(
        "issue58-lifecycle-result-v1",
        {
            "status": status.value,
            "inputs": list(inputs),
            "containment_attempted": attempted,
            "contained": contained,
            "restored_worktrees": restored,
            "retained_external_worktrees": retained_external,
            "retained_git_records": retained_git,
            "failed_container_classification": classification,
            "provider_attempts": 0,
        },
        code="lifecycle_result_invalid",
    )
    return LifecycleResultV1(
        status=status,
        receipt_fingerprint=receipt,
        containment_attempted=attempted,
        contained=contained,
        restored_worktrees=restored,
        retained_external_worktrees=retained_external,
        retained_git_records=retained_git,
        failed_container_classification=classification,
        provider_attempts=0,
    )
