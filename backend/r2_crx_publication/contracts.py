"""Closed reviewed-CRX contracts, faults, and receipts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .canonical import fingerprint, is_fingerprint


class CrxCrashGap(str, Enum):
    AFTER_INTENT = "after_intent"
    AFTER_EFFECT = "after_effect"
    AFTER_STABLE_VERIFY = "after_stable_verify"
    AFTER_COMMIT = "after_commit"


class CrxPendingState(str, Enum):
    EFFECT_ABSENT_EXACT = "EFFECT_ABSENT_EXACT"
    EFFECT_PRESENT_EXACT = "EFFECT_PRESENT_EXACT"
    EFFECT_AMBIGUOUS = "EFFECT_AMBIGUOUS"


class CrxPublicationStatus(str, Enum):
    PUBLISHED = "CRX_PUBLISHED"
    RECOVERED = "CRX_LOCAL_STATE_RECOVERED"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class CrxPublicationPrerequisiteV1:
    quiescence_receipt_fingerprint: str = field(repr=False)
    contract_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("CrxPublicationPrerequisiteV1 requires create()")

    @classmethod
    def create(cls, *, quiescence_receipt_fingerprint: object):
        if not is_fingerprint(quiescence_receipt_fingerprint):
            raise ValueError("crx_prerequisite_invalid")
        value = object.__new__(cls)
        object.__setattr__(
            value,
            "quiescence_receipt_fingerprint",
            quiescence_receipt_fingerprint,
        )
        object.__setattr__(
            value,
            "contract_fingerprint",
            fingerprint("crx-prerequisite-v1", quiescence_receipt_fingerprint),
        )
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class CrxFaultSelectorV1:
    kind: str
    boundary: str
    gap: CrxCrashGap | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("CrxFaultSelectorV1 requires a fixed factory")

    @classmethod
    def none(cls):
        return _selector(cls, "none")

    @classmethod
    def crash(cls, boundary: str, gap: CrxCrashGap):
        if (
            boundary not in {"crx_prepare", "crx_publish"}
            or type(gap) is not CrxCrashGap
        ):
            raise ValueError("crx_fault_selector_invalid")
        return _selector(cls, "crash", boundary=boundary, gap=gap)

    @classmethod
    def collision(cls):
        return _selector(cls, "collision")

    @classmethod
    def target_race(cls):
        return _selector(cls, "target_race")

    @classmethod
    def source_replacement(cls):
        return _selector(cls, "source_replacement")

    @classmethod
    def reparse(cls):
        return _selector(cls, "reparse")

    @classmethod
    def hash_drift(cls):
        return _selector(cls, "hash_drift")

    @classmethod
    def size_drift(cls):
        return _selector(cls, "size_drift")

    @classmethod
    def partial_staging(cls):
        return _selector(cls, "partial_staging")

    @classmethod
    def verification_failure(cls):
        return _selector(cls, "verification_failure")


@dataclass(frozen=True, slots=True, repr=False)
class CrxPublicationReceiptV1:
    status: CrxPublicationStatus
    pending_state: CrxPendingState
    format_version: int
    size_bytes: int
    source_held_through_final_verify: bool
    target_held_through_final_verify: bool
    retained_artifact_count: int
    source_identity_fingerprint: str = field(repr=False)
    artifact_hash: str = field(repr=False)
    target_identity_fingerprint: str = field(repr=False)
    receipt_fingerprint: str = field(repr=False)


def build_receipt(*, status, state, review, target_identity, retained):
    body = {
        "status": status.value,
        "pending_state": state.value,
        "format_version": review.format_version,
        "size_bytes": review.size_bytes,
        "source_held_through_final_verify": status is CrxPublicationStatus.PUBLISHED,
        "target_held_through_final_verify": status is CrxPublicationStatus.PUBLISHED,
        "retained_artifact_count": retained,
        "source_identity_fingerprint": review.source_identity_fingerprint,
        "artifact_hash": review.artifact_hash,
        "target_identity_fingerprint": target_identity,
    }
    return CrxPublicationReceiptV1(
        status=status,
        pending_state=state,
        format_version=review.format_version,
        size_bytes=review.size_bytes,
        source_held_through_final_verify=(
            status is CrxPublicationStatus.PUBLISHED
        ),
        target_held_through_final_verify=(
            status is CrxPublicationStatus.PUBLISHED
        ),
        retained_artifact_count=retained,
        source_identity_fingerprint=review.source_identity_fingerprint,
        artifact_hash=review.artifact_hash,
        target_identity_fingerprint=target_identity,
        receipt_fingerprint=fingerprint("crx-publication-receipt-v1", body),
    )


def _selector(cls: type, kind: str, **values: object):
    value = object.__new__(cls)
    for name, item in {
        "kind": kind,
        "boundary": "",
        "gap": None,
        **values,
    }.items():
        object.__setattr__(value, name, item)
    return value
