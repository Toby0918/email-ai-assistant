"""Closed journal-driven rollback evidence for Issue #58."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .canonical import fail, fingerprint, is_fingerprint

_ERROR = "service_rollback_evidence_invalid"


class RollbackStage(str, Enum):
    NEW_SERVICE_STOPPED = "new_service_stopped"
    NEW_EVIDENCE_PRESERVED = "new_evidence_preserved"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class CommittedRollbackPlanV1:
    journal_head_fingerprint: str = field(repr=False)
    committed_records_fingerprint: str = field(repr=False)
    original_topology_fingerprint: str = field(repr=False)
    parent_descriptor_fingerprint: str = field(repr=False)
    finance_descriptor_fingerprint: str = field(repr=False)
    original_database_fingerprint: str = field(repr=False)
    sidecar_state_fingerprint: str = field(repr=False)
    legacy_runtime_fingerprint: str = field(repr=False)
    repository_identity_fingerprint: str = field(repr=False)
    plan_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("CommittedRollbackPlanV1 requires create()")

    @classmethod
    def create(cls, **values: object):
        expected = {
            "journal_head_fingerprint",
            "committed_records_fingerprint",
            "original_topology_fingerprint",
            "parent_descriptor_fingerprint",
            "finance_descriptor_fingerprint",
            "original_database_fingerprint",
            "sidecar_state_fingerprint",
            "legacy_runtime_fingerprint",
            "repository_identity_fingerprint",
        }
        if set(values) != expected or not all(
            is_fingerprint(item) for item in values.values()
        ):
            fail(_ERROR)
        value = object.__new__(cls)
        for name, item in values.items():
            object.__setattr__(value, name, item)
        object.__setattr__(
            value,
            "plan_fingerprint",
            fingerprint("issue58-committed-rollback-plan-v1", values, code=_ERROR),
        )
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RollbackStageEvidenceV1:
    stage: str
    journal_head_fingerprint: str = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    rollback_plan_fingerprint: str = field(repr=False)
    previous_observation_fingerprint: str = field(repr=False)
    retained_external: int
    retained_git_records: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("RollbackStageEvidenceV1 requires create()")

    @classmethod
    def create(cls, **values: object) -> RollbackStageEvidenceV1:
        stage = values.get("stage")
        counts = {
            RollbackStage.NEW_SERVICE_STOPPED: (0, 0),
            RollbackStage.NEW_EVIDENCE_PRESERVED: (3, 11),
        }
        if (
            set(values)
            != {
                "stage",
                "journal_head_fingerprint",
                "observation_fingerprint",
                "rollback_plan_fingerprint",
                "previous_observation_fingerprint",
                "retained_external",
                "retained_git_records",
            }
            or type(stage) is not RollbackStage
            or not is_fingerprint(values["journal_head_fingerprint"])
            or not is_fingerprint(values["observation_fingerprint"])
            or not is_fingerprint(values["rollback_plan_fingerprint"])
            or not is_fingerprint(
                values["previous_observation_fingerprint"]
            )
            or (
                values["retained_external"],
                values["retained_git_records"],
            )
            != counts[stage]
        ):
            fail(_ERROR)
        value = object.__new__(cls)
        for name, item in values.items():
            object.__setattr__(
                value, name, item.value if name == "stage" else item
            )
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class FailedContainerPublicationReceiptV1:
    status: str
    classification: str
    journal_head_fingerprint: str = field(repr=False)
    failed_container_fingerprint: str = field(repr=False)
    rollback_plan_fingerprint: str = field(repr=False)
    preservation_observation_fingerprint: str = field(repr=False)
    retained_external: int
    retained_git_records: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "FailedContainerPublicationReceiptV1 requires create()"
        )

    @classmethod
    def create(cls, **values: object):
        if (
            set(values)
            != {
                "journal_head_fingerprint",
                "failed_container_fingerprint",
                "rollback_plan_fingerprint",
                "preservation_observation_fingerprint",
                "retained_external",
                "retained_git_records",
            }
            or not is_fingerprint(values["journal_head_fingerprint"])
            or not is_fingerprint(values["failed_container_fingerprint"])
            or not is_fingerprint(values["rollback_plan_fingerprint"])
            or not is_fingerprint(
                values["preservation_observation_fingerprint"]
            )
            or values["retained_external"] != 3
            or values["retained_git_records"] != 11
        ):
            fail(_ERROR)
        body = {
            "receipt_type": "FailedContainerPublicationReceiptV1",
            "status": "SEALED",
            "classification": (
                "FAILED_CONTAINER_SEALED_PENDING_LEGACY_MAIN_EXTRACTION"
            ),
            **values,
        }
        value = object.__new__(cls)
        for name, item in body.items():
            if name != "receipt_type":
                object.__setattr__(value, name, item)
        object.__setattr__(
            value,
            "receipt_fingerprint",
            fingerprint("issue58-failed-container-v1", body, code=_ERROR),
        )
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RollbackRestoreEvidenceV1:
    journal_head_fingerprint: str = field(repr=False)
    failed_container_receipt_fingerprint: str = field(repr=False)
    rollback_plan_fingerprint: str = field(repr=False)
    reverse_receipt_fingerprint: str = field(repr=False)
    original_topology_fingerprint: str = field(repr=False)
    main_restored: int
    git_records_restored: int
    embedded_worktrees_restored: int
    external_worktrees_restored: int
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("RollbackRestoreEvidenceV1 requires create()")

    @classmethod
    def create(cls, **values: object):
        if (
            set(values)
            != {
                "journal_head_fingerprint",
                "failed_container_receipt_fingerprint",
                "rollback_plan_fingerprint",
                "reverse_receipt_fingerprint",
                "original_topology_fingerprint",
                "main_restored",
                "git_records_restored",
                "embedded_worktrees_restored",
                "external_worktrees_restored",
            }
            or not is_fingerprint(values["journal_head_fingerprint"])
            or not is_fingerprint(
                values["failed_container_receipt_fingerprint"]
            )
            or not is_fingerprint(values["rollback_plan_fingerprint"])
            or not is_fingerprint(values["reverse_receipt_fingerprint"])
            or not is_fingerprint(
                values["original_topology_fingerprint"]
            )
            or (
                values["main_restored"],
                values["git_records_restored"],
                values["embedded_worktrees_restored"],
                values["external_worktrees_restored"],
            )
            != (1, 11, 8, 3)
        ):
            fail(_ERROR)
        value = object.__new__(cls)
        for name, item in values.items():
            object.__setattr__(value, name, item)
        object.__setattr__(
            value,
            "observation_fingerprint",
            fingerprint("issue58-rollback-restore-v1", values, code=_ERROR),
        )
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class LegacyPrerequisiteEvidenceV1:
    journal_head_fingerprint: str = field(repr=False)
    rollback_observation_fingerprint: str = field(repr=False)
    rollback_plan_fingerprint: str = field(repr=False)
    original_topology_fingerprint: str = field(repr=False)
    parent_descriptor_fingerprint: str = field(repr=False)
    finance_descriptor_fingerprint: str = field(repr=False)
    original_database_fingerprint: str = field(repr=False)
    sidecar_state_fingerprint: str = field(repr=False)
    legacy_runtime_fingerprint: str = field(repr=False)
    repository_identity_fingerprint: str = field(repr=False)
    git_records_verified: int
    worktrees_verified: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("LegacyPrerequisiteEvidenceV1 requires create()")

    @classmethod
    def create(cls, **values: object):
        fingerprints = (
            "journal_head_fingerprint",
            "rollback_observation_fingerprint",
            "rollback_plan_fingerprint",
            "original_topology_fingerprint",
            "parent_descriptor_fingerprint",
            "finance_descriptor_fingerprint",
            "original_database_fingerprint",
            "sidecar_state_fingerprint",
            "legacy_runtime_fingerprint",
            "repository_identity_fingerprint",
        )
        if (
            set(values)
            != set(fingerprints)
            | {"git_records_verified", "worktrees_verified"}
            or not all(is_fingerprint(values[name]) for name in fingerprints)
            or values["git_records_verified"] != 11
            or values["worktrees_verified"] != 11
        ):
            fail(_ERROR)
        value = object.__new__(cls)
        for name, item in values.items():
            object.__setattr__(value, name, item)
        return value
