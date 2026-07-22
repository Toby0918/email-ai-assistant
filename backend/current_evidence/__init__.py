"""Contract-only boundary for deidentified current-click evidence submission."""

from .contract import CurrentClickEvidenceV1
from .handoff import submit_current_click_evidence

__all__ = [
    "CurrentClickEvidenceV1",
    "submit_current_click_evidence",
]
