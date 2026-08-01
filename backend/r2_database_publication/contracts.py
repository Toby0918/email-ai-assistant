"""Closed contracts for quiescence, database faults, and outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .canonical import fingerprint, is_fingerprint


@dataclass(frozen=True, slots=True, init=False, repr=False)
class QuiescencePrerequisitesV1:
    preflight_fingerprint: str = field(repr=False)
    evidence_fingerprint: str = field(repr=False)
    fresh_gate_fingerprint: str = field(repr=False)
    contract_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("QuiescencePrerequisitesV1 requires create()")

    @classmethod
    def create(cls, **values: object) -> QuiescencePrerequisitesV1:
        names = (
            "preflight_fingerprint",
            "evidence_fingerprint",
            "fresh_gate_fingerprint",
        )
        if (
            set(values) != set(names)
            or any(not is_fingerprint(values[name]) for name in names)
            or len(set(values.values())) != 3
        ):
            raise ValueError("quiescence_prerequisites_invalid")
        result = object.__new__(cls)
        for name in names:
            object.__setattr__(result, name, values[name])
        object.__setattr__(
            result,
            "contract_fingerprint",
            fingerprint("quiescence-prerequisites-v1", values),
        )
        return result

    @property
    def fingerprints(self) -> tuple[str, str, str]:
        return (
            self.preflight_fingerprint,
            self.evidence_fingerprint,
            self.fresh_gate_fingerprint,
        )


class DatabaseCheckpoint(str, Enum):
    POST_STOP_BASELINE = "POST_STOP_BASELINE"
    PRE_COPY_LEASE = "PRE_COPY_LEASE"
    COPY_POSTVERIFY = "COPY_POSTVERIFY"
    FINAL_OR_RECOVERY_VERIFY = "FINAL_OR_RECOVERY_VERIFY"


class DatabaseCrashGap(str, Enum):
    AFTER_INTENT = "after_intent"
    AFTER_EFFECT = "after_effect"
    AFTER_STABLE_VERIFY = "after_stable_verify"
    AFTER_COMMIT = "after_commit"


class DatabaseTransactionStatus(str, Enum):
    PUBLISHED = "DATABASE_PUBLISHED"
    RECOVERED = "DATABASE_LOCAL_STATE_RECOVERED"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class DatabaseFaultSelectorV1:
    kind: str
    boundary: str = ""
    gap: DatabaseCrashGap | None = None
    checkpoint: DatabaseCheckpoint | None = None
    sidecar_suffix: str = ""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("DatabaseFaultSelectorV1 requires a fixed factory")

    @classmethod
    def none(cls) -> DatabaseFaultSelectorV1:
        return _selector(cls, "none")

    @classmethod
    def crash(cls, boundary: str, gap: DatabaseCrashGap):
        if boundary not in {"database_prepare", "database_publish"} or type(gap) is not DatabaseCrashGap:
            raise ValueError("database_fault_selector_invalid")
        return _selector(cls, "crash", boundary=boundary, gap=gap)

    @classmethod
    def sidecar(cls, checkpoint: DatabaseCheckpoint, suffix: str):
        if type(checkpoint) is not DatabaseCheckpoint or suffix not in {"-wal", "-shm", "-journal"}:
            raise ValueError("database_fault_selector_invalid")
        return _selector(
            cls,
            "sidecar",
            checkpoint=checkpoint,
            sidecar_suffix=suffix,
        )

    @classmethod
    def collision(cls):
        return _selector(cls, "collision")

    @classmethod
    def source_drift(cls):
        return _selector(cls, "source_drift")

    @classmethod
    def partial_staging(cls):
        return _selector(cls, "partial_staging")


@dataclass(frozen=True, slots=True, repr=False)
class DatabaseTransactionResultV1:
    status: DatabaseTransactionStatus
    receipt_fingerprint: str = field(repr=False)
    lease_read_passes: int
    retained_artifact_count: int
    source_mutations: int


def _selector(cls: type, kind: str, **values: object):
    result = object.__new__(cls)
    defaults = {
        "boundary": "",
        "gap": None,
        "checkpoint": None,
        "sidecar_suffix": "",
    }
    for name, value in {"kind": kind, **defaults, **values}.items():
        object.__setattr__(result, name, value)
    return result
