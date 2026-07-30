"""Closed read-only preflight roles."""

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True, slots=True, repr=False)
class RealHostPreflightRolesV1:
    binding_fingerprint: str = field(repr=False)
    current_topology: Callable[[object], object] = field(repr=False)
    host_baseline: Callable[[object], object] = field(repr=False)
    evidence_review: Callable[[object], object] = field(repr=False)
    evidence_verification: Callable[[object], object] = field(repr=False)
    final_audit_readiness: Callable[[object], object] = field(repr=False)
    recovery_inspection: Callable[[object], object] = field(repr=False)


def has_exact_roles(value: object) -> bool:
    return (
        type(value) is RealHostPreflightRolesV1
        and type(value.binding_fingerprint) is str
        and len(value.binding_fingerprint) == 64
        and all(
            callable(item)
            for item in (
                value.current_topology,
                value.host_baseline,
                value.evidence_review,
                value.evidence_verification,
                value.final_audit_readiness,
                value.recovery_inspection,
            )
        )
    )
