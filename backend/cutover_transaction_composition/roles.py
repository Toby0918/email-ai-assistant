"""Closed fixed transaction roles."""

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True, slots=True, repr=False)
class CutoverTransactionRolesV1:
    binding_fingerprint: str = field(repr=False)
    acl_baseline: Callable[[object], object] = field(repr=False)
    pre_mutation_gate: Callable[[object], object] = field(repr=False)
    acl_publication: Callable[[object], object] = field(repr=False)
    repository_transaction: Callable[[object], object] = field(repr=False)
    runtime_publication: Callable[[object], object] = field(repr=False)
    database_publication: Callable[[object], object] = field(repr=False)
    artifact_publication: Callable[[object], object] = field(repr=False)
    config_publication: Callable[[object], object] = field(repr=False)
    activation: Callable[[object], object] = field(repr=False)
    final_audit: Callable[[object], object] = field(repr=False)
    cutover_success: Callable[[object], object] = field(repr=False)
    recovery_inspection: Callable[[object], object] = field(repr=False)
    failed_container_preservation: Callable[[object], object] = field(
        repr=False
    )
    rollback_restoration: Callable[[object], object] = field(repr=False)
    legacy_health: Callable[[object], object] = field(repr=False)
    resume_committed: Callable[[object], object] = field(repr=False)


def has_exact_roles(value: object) -> bool:
    return (
        type(value) is CutoverTransactionRolesV1
        and type(value.binding_fingerprint) is str
        and len(value.binding_fingerprint) == 64
        and all(
            callable(item)
            for item in (
                value.acl_baseline,
                value.pre_mutation_gate,
                value.acl_publication,
                value.repository_transaction,
                value.runtime_publication,
                value.database_publication,
                value.artifact_publication,
                value.config_publication,
                value.activation,
                value.final_audit,
                value.cutover_success,
                value.recovery_inspection,
                value.failed_container_preservation,
                value.rollback_restoration,
                value.legacy_health,
                value.resume_committed,
            )
        )
    )
