"""Exact staged rollback adapter available to the lifecycle transaction."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Callable


@dataclass(frozen=True, slots=True, repr=False)
class JournalDrivenRollbackAdapter:
    verify_new_service_stopped: Callable[[object], object] = field(repr=False)
    preserve_new_evidence: Callable[[], object] = field(repr=False)
    publish_failed_container: Callable[[object], object] = field(repr=False)
    restore_original_topology: Callable[[object], object] = field(repr=False)
    verify_legacy_prerequisites: Callable[[object], object] = field(
        repr=False
    )

def has_exact_rollback_adapter(value: object) -> bool:
    return (
        type(value) is JournalDrivenRollbackAdapter
        and all(callable(getattr(value, item.name)) for item in fields(value))
    )
