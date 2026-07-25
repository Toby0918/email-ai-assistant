"""Fixed, content-free public ContainerAudit results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuditStatus(str, Enum):
    """The complete public status allowlist."""

    PASSED = "container_audit_passed"
    FAILED = "container_audit_failed"


@dataclass(frozen=True, slots=True)
class AuditCounts:
    """One accepted or rejected manual audit."""

    accepted: int
    rejected: int


@dataclass(frozen=True, slots=True)
class ContainerAuditResult:
    """A public result with no diagnostic or evidence field."""

    status: AuditStatus
    counts: AuditCounts


PASSED_RESULT = ContainerAuditResult(
    status=AuditStatus.PASSED,
    counts=AuditCounts(accepted=1, rejected=0),
)
FAILED_RESULT = ContainerAuditResult(
    status=AuditStatus.FAILED,
    counts=AuditCounts(accepted=0, rejected=1),
)
