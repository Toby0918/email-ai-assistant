"""Closed content-free contracts for cross-stage recovery and final seal."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.cutover_composition_contracts.canonical import fingerprint, is_fingerprint
from backend.r2_independent_audits import (
    IndependentFinalRunningHealthReceiptV1,
    IndependentStoppedLayoutAuditReceiptV1,
    is_issued_audit_receipt,
)
from backend.r2_validation_lifecycle import (
    ValidationLifecycleResultV1,
    ValidationStatus,
    is_issued_validation_result,
)
from .receipt_links import ReceiptPredecessorLinkV1


class EffectObservation(str, Enum):
    ABSENT = "ABSENT"
    PRESENT = "PRESENT"
    AMBIGUOUS = "AMBIGUOUS"


class EffectClassification(str, Enum):
    EFFECT_ABSENT_EXACT = "EFFECT_ABSENT_EXACT"
    EFFECT_PRESENT_EXACT = "EFFECT_PRESENT_EXACT"
    EFFECT_AMBIGUOUS = "EFFECT_AMBIGUOUS"


class RecoveryBoundary(str, Enum):
    PRESERVE_FAILED_CONTAINER = "preserve_failed_container"
    RESTORE_REPOSITORY_ROOT = "restore_repository_root"
    RESTORE_GIT = "restore_git"
    RESTORE_ELEVEN_WORKTREES = "restore_eleven_worktrees"
    RESTORE_ACL = "restore_acl"
    RESTORE_DATABASE = "restore_database"
    RECOVER_LEGACY_SERVICE = "recover_legacy_service"


class RecoveryCrashGap(str, Enum):
    BEFORE_INTENT = "before_intent"
    AFTER_INTENT = "after_intent"
    AFTER_EFFECT = "after_effect"
    AFTER_STABLE_OBSERVATION = "after_stable_observation"
    AFTER_COMMIT = "after_commit"


class CrossStageStatus(str, Enum):
    INSPECTED = "RESTART_INSPECTED_READ_ONLY"
    RECOVERY_RESTART_REQUIRED = "RECOVERY_RESTART_REQUIRED"
    LEGACY_FLAT_LAYOUT_RESTORED = "LEGACY_FLAT_LAYOUT_RESTORED"
    INCIDENT_STOP = "INCIDENT_STOP"
    CUTOVER_SUCCESS = "CUTOVER_SUCCESS"


@dataclass(frozen=True, slots=True, repr=False, init=False)
class PendingIntentV1:
    direction: str
    boundary: RecoveryBoundary
    intent_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("PendingIntentV1 requires create()")

    @classmethod
    def create(cls, *, direction, boundary, intent_fingerprint):
        if direction not in {"forward", "reverse", "committed"} or type(boundary) is not RecoveryBoundary or not is_fingerprint(intent_fingerprint):
            raise ValueError("R2_PENDING_INTENT_INVALID")
        value = object.__new__(cls)
        for name, item in {"direction": direction, "boundary": boundary, "intent_fingerprint": intent_fingerprint}.items():
            object.__setattr__(value, name, item)
        return value


@dataclass(frozen=True, slots=True, repr=False, init=False)
class RestartSnapshotV1:
    current_journal_head: str
    receipt_links: tuple[ReceiptPredecessorLinkV1, ...]
    pending_intents: tuple[PendingIntentV1, ...]
    remaining_reverse_plan: tuple[RecoveryBoundary, ...]
    failed_container_preserved: bool
    retained_new_object_count: int
    approved_identities_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("RestartSnapshotV1 requires create()")

    @classmethod
    def create(cls, **values):
        if not _valid_snapshot(values):
            raise ValueError("R2_RESTART_SNAPSHOT_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, init=False)
class RecoveryFaultSelectorV1:
    kind: str
    boundary: RecoveryBoundary | None
    gap: RecoveryCrashGap | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("RecoveryFaultSelectorV1 requires a fixed factory")

    @classmethod
    def none(cls):
        return _fault(cls, "none", None, None)

    @classmethod
    def crash(cls, boundary, gap):
        if type(boundary) is not RecoveryBoundary or type(gap) is not RecoveryCrashGap:
            raise ValueError("R2_RECOVERY_FAULT_INVALID")
        return _fault(cls, "recovery_crash", boundary, gap)

    @classmethod
    def crash_after_effect(cls, boundary):
        return cls.crash(boundary, RecoveryCrashGap.AFTER_EFFECT)

    @classmethod
    def seal_crash(cls, gap):
        if type(gap) is not RecoveryCrashGap:
            raise ValueError("R2_RECOVERY_FAULT_INVALID")
        return _fault(cls, "seal_crash", None, gap)


@dataclass(frozen=True, slots=True, repr=False, init=False)
class ReverseBoundaryAuthorityV1:
    boundary: RecoveryBoundary
    journal_head_fingerprint: str
    remaining_plan_fingerprint: str
    crash_nonce: str
    issued_at_epoch: int
    expires_at_epoch: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ReverseBoundaryAuthorityV1 requires create()")

    @classmethod
    def create(cls, **values):
        expected = {"boundary", "journal_head_fingerprint", "remaining_plan_fingerprint", "crash_nonce", "issued_at_epoch", "expires_at_epoch"}
        if set(values) != expected or type(values["boundary"]) is not RecoveryBoundary or not all(is_fingerprint(values[name]) for name in ("journal_head_fingerprint", "remaining_plan_fingerprint", "crash_nonce")) or type(values["issued_at_epoch"]) is not int or type(values["expires_at_epoch"]) is not int:
            raise ValueError("R2_REVERSE_AUTHORITY_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False, init=False)
class ReverseEffectEvidenceV1:
    boundary: RecoveryBoundary
    prior_head_fingerprint: str
    journal_head_fingerprint: str
    effect_fingerprint: str
    retained_new_objects: int
    cleanup_operations: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ReverseEffectEvidenceV1 requires create()")

    @classmethod
    def create(cls, **values):
        expected = {"boundary", "prior_head_fingerprint", "journal_head_fingerprint", "effect_fingerprint", "retained_new_objects", "cleanup_operations"}
        if set(values) != expected or type(values["boundary"]) is not RecoveryBoundary or not all(is_fingerprint(values[name]) for name in ("prior_head_fingerprint", "journal_head_fingerprint", "effect_fingerprint")) or any(type(values[name]) is not int for name in ("retained_new_objects", "cleanup_operations")):
            raise ValueError("R2_REVERSE_EFFECT_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False, init=False)
class FinalFreshnessObservationV1:
    journal_head_fingerprint: str
    nonce_b: str
    approved_identities_fingerprint: str
    observed_at_epoch: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("FinalFreshnessObservationV1 requires create()")

    @classmethod
    def create(cls, **values):
        expected = {"journal_head_fingerprint", "nonce_b", "approved_identities_fingerprint", "observed_at_epoch"}
        if set(values) != expected or not is_fingerprint(values["journal_head_fingerprint"]) or not is_fingerprint(values["approved_identities_fingerprint"]) or type(values["nonce_b"]) is not str or type(values["observed_at_epoch"]) is not int:
            raise ValueError("R2_FINAL_FRESHNESS_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False, init=False)
class FinalSealRequestV1:
    validation: ValidationLifecycleResultV1
    current_journal_head: str
    nonce_b: str
    approved_identities_fingerprint: str
    stopped_identities_fingerprint: str
    final_identities_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("FinalSealRequestV1 requires create()")

    @classmethod
    def create(cls, **values):
        if not _valid_seal(values):
            raise ValueError("R2_FINAL_SEAL_REQUEST_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False, init=False)
class CutoverSuccessAppendV1:
    record_type: str
    prior_head_fingerprint: str
    journal_head_fingerprint: str
    material_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("CutoverSuccessAppendV1 requires create()")

    @classmethod
    def create(cls, **values):
        if set(values) != {"record_type", "prior_head_fingerprint", "journal_head_fingerprint", "material_fingerprint"} or values["record_type"] != "CUTOVER_SUCCESS" or not all(is_fingerprint(values[name]) for name in ("prior_head_fingerprint", "journal_head_fingerprint", "material_fingerprint")):
            raise ValueError("R2_CUTOVER_SUCCESS_APPEND_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False)
class CrossStageResultV1:
    status: CrossStageStatus
    classifications: tuple[EffectClassification, ...]
    completed_boundaries: int
    retained_new_objects: int
    cleanup_operations: int
    host_mutations: int
    journal_appends: int
    receipt_fingerprint: str


def plan_fingerprint(boundaries):
    return fingerprint("r2-remaining-reverse-plan-v1", [item.value for item in boundaries])


def _fault(cls, kind, boundary, gap):
    result = object.__new__(cls)
    object.__setattr__(result, "kind", kind)
    object.__setattr__(result, "boundary", boundary)
    object.__setattr__(result, "gap", gap)
    return result


def _valid_snapshot(values):
    expected = {"current_journal_head", "receipt_links", "pending_intents", "remaining_reverse_plan", "failed_container_preserved", "retained_new_object_count", "approved_identities_fingerprint"}
    plan = values.get("remaining_reverse_plan")
    pending = values.get("pending_intents")
    return set(values) == expected and is_fingerprint(values["current_journal_head"]) and type(values["receipt_links"]) is tuple and all(type(item) is ReceiptPredecessorLinkV1 for item in values["receipt_links"]) and type(pending) is tuple and all(type(item) is PendingIntentV1 for item in pending) and len({item.boundary for item in pending}) == len(pending) and len({item.intent_fingerprint for item in pending}) == len(pending) and type(plan) is tuple and all(type(item) is RecoveryBoundary for item in plan) and tuple(item for item in RecoveryBoundary if item in plan) == plan and type(values["failed_container_preserved"]) is bool and type(values["retained_new_object_count"]) is int and values["retained_new_object_count"] >= 0 and is_fingerprint(values["approved_identities_fingerprint"])


def _valid_seal(values):
    expected = {"validation", "current_journal_head", "nonce_b", "approved_identities_fingerprint", "stopped_identities_fingerprint", "final_identities_fingerprint"}
    validation = values.get("validation")
    return set(values) == expected and type(validation) is ValidationLifecycleResultV1 and is_issued_validation_result(validation) and validation.status is ValidationStatus.VALIDATED and type(validation.stopped_audit) is IndependentStoppedLayoutAuditReceiptV1 and type(validation.final_audit) is IndependentFinalRunningHealthReceiptV1 and is_issued_audit_receipt(validation.stopped_audit) and is_issued_audit_receipt(validation.final_audit) and validation.start_b_nonce == values["nonce_b"] and validation.approved_identities_fingerprint == values["approved_identities_fingerprint"] and type(values["nonce_b"]) is str and all(is_fingerprint(values[name]) for name in ("current_journal_head", "approved_identities_fingerprint", "stopped_identities_fingerprint", "final_identities_fingerprint"))
