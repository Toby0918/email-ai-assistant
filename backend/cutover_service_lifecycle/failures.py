"""Closed activation failure classes for rollback and incident routing."""

from __future__ import annotations

from enum import Enum

from .errors import ServiceLifecycleError


class ActivationFailureKind(str, Enum):
    START_REJECTED = "START_REJECTED"
    HEALTH_REJECTED = "HEALTH_REJECTED"
    DETERMINISTIC_RESULT_REJECTED = "DETERMINISTIC_RESULT_REJECTED"
    PERSISTENCE_REJECTED = "PERSISTENCE_REJECTED"
    IDENTITY_AMBIGUITY = "IDENTITY_AMBIGUITY"
    JOURNAL_AMBIGUITY = "JOURNAL_AMBIGUITY"
    REPARSE_AMBIGUITY = "REPARSE_AMBIGUITY"
    PROVIDER_BOUNDARY_AMBIGUITY = "PROVIDER_BOUNDARY_AMBIGUITY"
    SAFETY_AMBIGUITY = "SAFETY_AMBIGUITY"

    @property
    def is_safe_abort(self) -> bool:
        return self is ActivationFailureKind.START_REJECTED

    @property
    def is_incident(self) -> bool:
        return self in {
            ActivationFailureKind.IDENTITY_AMBIGUITY,
            ActivationFailureKind.JOURNAL_AMBIGUITY,
            ActivationFailureKind.REPARSE_AMBIGUITY,
            ActivationFailureKind.PROVIDER_BOUNDARY_AMBIGUITY,
            ActivationFailureKind.SAFETY_AMBIGUITY,
        }


class ServiceBoundaryFailure(ServiceLifecycleError):
    """One fixed, content-free activation failure classification."""

    def __init__(self, kind: ActivationFailureKind) -> None:
        if type(kind) is not ActivationFailureKind:
            raise TypeError("service boundary failure kind invalid")
        self.kind = kind
        super().__init__(f"service_boundary_{kind.value.lower()}")
