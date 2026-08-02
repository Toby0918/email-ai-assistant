"""Closed Runtime prerequisite, fault, and receipt contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.cutover_managed_activation.runtime_policy import (
    PYTHON_VERSION,
    SQLITE_VERSION,
)

from .canonical import fingerprint, is_fingerprint


class RuntimeVerificationAuthority(str, Enum):
    CANONICAL_LOCK_SELF_VERIFICATION = (
        "CANONICAL_LOCK_SELF_VERIFICATION_V1"
    )


class RuntimeCrashGap(str, Enum):
    AFTER_INTENT = "after_intent"
    AFTER_EFFECT = "after_effect"
    AFTER_STABLE_VERIFY = "after_stable_verify"
    AFTER_COMMIT = "after_commit"


class RuntimePublicationStatus(str, Enum):
    PUBLISHED = "RUNTIME_PUBLISHED"
    RECOVERED = "RUNTIME_LOCAL_STATE_RECOVERED"
    INCIDENT_STOP = "INCIDENT_STOP"


class RuntimePendingClassification(str, Enum):
    EFFECT_ABSENT_EXACT = "EFFECT_ABSENT_EXACT"
    STAGING_EXACT = "STAGING_EXACT"
    STAGING_PARTIAL_RETAINED = "STAGING_PARTIAL_RETAINED"
    PUBLISHED_EXACT = "PUBLISHED_EXACT"
    EFFECT_AMBIGUOUS = "EFFECT_AMBIGUOUS"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RuntimePublicationPrerequisiteV1:
    quiescence_receipt_fingerprint: str = field(repr=False)
    contract_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("RuntimePublicationPrerequisiteV1 requires create()")

    @classmethod
    def create(cls, *, quiescence_receipt_fingerprint: object):
        if not is_fingerprint(quiescence_receipt_fingerprint):
            raise ValueError("runtime_prerequisite_invalid")
        value = object.__new__(cls)
        object.__setattr__(
            value,
            "quiescence_receipt_fingerprint",
            quiescence_receipt_fingerprint,
        )
        object.__setattr__(
            value,
            "contract_fingerprint",
            fingerprint(
                "runtime-publication-prerequisite-v1",
                quiescence_receipt_fingerprint,
            ),
        )
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RuntimeFaultSelectorV1:
    kind: str
    boundary: str
    gap: RuntimeCrashGap | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("RuntimeFaultSelectorV1 requires a fixed factory")

    @classmethod
    def none(cls):
        return _selector(cls, "none")

    @classmethod
    def crash(cls, boundary: str, gap: RuntimeCrashGap):
        if (
            boundary not in {"runtime_prepare", "runtime_publish"}
            or type(gap) is not RuntimeCrashGap
        ):
            raise ValueError("runtime_fault_selector_invalid")
        return _selector(cls, "crash", boundary=boundary, gap=gap)

    @classmethod
    def collision(cls):
        return _selector(cls, "collision")

    @classmethod
    def source_drift(cls):
        return _selector(cls, "source_drift")

    @classmethod
    def dependency_drift(cls):
        return _selector(cls, "dependency_drift")

    @classmethod
    def verification_failure(cls):
        return _selector(cls, "verification_failure")

    @classmethod
    def reparse(cls):
        return _selector(cls, "reparse")


@dataclass(frozen=True, slots=True, repr=False)
class RuntimePublicationReceiptV1:
    status: RuntimePublicationStatus
    python_version: str
    sqlite_version: str
    dependency_count: int
    verification_authority: RuntimeVerificationAuthority
    same_volume: bool
    complete: bool
    pending_classification: RuntimePendingClassification
    retained_artifact_count: int
    tree_fingerprint: str = field(repr=False)
    verification_fingerprint: str = field(repr=False)
    receipt_fingerprint: str = field(repr=False)


def build_receipt(
    *, status, dependency_count, retained, tree, verification, classification
):
    body = {
        "status": status.value,
        "python_version": PYTHON_VERSION,
        "sqlite_version": SQLITE_VERSION,
        "dependency_count": dependency_count,
        "verification_authority": (
            RuntimeVerificationAuthority.CANONICAL_LOCK_SELF_VERIFICATION.value
        ),
        "same_volume": True,
        "complete": status is RuntimePublicationStatus.PUBLISHED,
        "pending_classification": classification.value,
        "retained_artifact_count": retained,
        "tree_fingerprint": tree,
        "verification_fingerprint": verification,
    }
    return RuntimePublicationReceiptV1(
        status=status,
        python_version=PYTHON_VERSION,
        sqlite_version=SQLITE_VERSION,
        dependency_count=dependency_count,
        verification_authority=(
            RuntimeVerificationAuthority.CANONICAL_LOCK_SELF_VERIFICATION
        ),
        same_volume=True,
        complete=status is RuntimePublicationStatus.PUBLISHED,
        pending_classification=classification,
        retained_artifact_count=retained,
        tree_fingerprint=tree,
        verification_fingerprint=verification,
        receipt_fingerprint=fingerprint("runtime-publication-receipt-v1", body),
    )


def _selector(cls: type, kind: str, **values: object):
    result = object.__new__(cls)
    for name, value in {
        "kind": kind,
        "boundary": "",
        "gap": None,
        **values,
    }.items():
        object.__setattr__(result, name, value)
    return result
