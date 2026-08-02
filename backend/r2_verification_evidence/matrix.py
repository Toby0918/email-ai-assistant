"""Fixed forward/reverse R2 semantic journal-gap matrix."""

from __future__ import annotations

from dataclasses import dataclass


_SEMANTICS = (
    "acl_scan",
    "staging",
    "publication",
    "service",
    "audit_append",
    "recovery",
    "final_seal",
)
_DIRECTIONS = ("forward", "reverse")
_GAPS = (
    "before_intent",
    "after_intent",
    "after_effect",
    "after_stable_observation",
    "after_commit",
)


@dataclass(frozen=True, slots=True)
class R2SemanticGapCaseV1:
    semantic: str
    direction: str
    gap: str


def semantic_gap_matrix() -> tuple[R2SemanticGapCaseV1, ...]:
    return tuple(
        R2SemanticGapCaseV1(semantic, direction, gap)
        for semantic in _SEMANTICS
        for direction in _DIRECTIONS
        for gap in _GAPS
    )
