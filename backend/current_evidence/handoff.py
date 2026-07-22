"""Append-only submission seam for validated current-click evidence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .contract import CurrentClickEvidenceV1, CurrentEvidenceError


@dataclass(frozen=True, slots=True)
class _EvidenceSubmissionResult:
    code: str = "evidence_accepted"

    def to_dict(self) -> dict[str, object]:
        return {"ok": True, "code": self.code}


def submit_current_click_evidence(
    value: object,
    *,
    append: Callable[[CurrentClickEvidenceV1], object],
) -> _EvidenceSubmissionResult:
    evidence = CurrentClickEvidenceV1.from_mapping(value)
    try:
        append(evidence)
    except Exception:
        raise CurrentEvidenceError("evidence_append_failed") from None
    return _EvidenceSubmissionResult()


__all__ = ["submit_current_click_evidence"]
