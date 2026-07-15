"""Content-free residual detection for deidentified text fields."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .entity_patterns import (
    AMBIGUOUS_CONTROLS,
    IDENTITY_LIKE_PATTERNS,
    PATTERNS,
    PLACEHOLDER,
)
from .errors import PrivateKnowledgeError


@dataclass(frozen=True, slots=True)
class ResidualFinding:
    code: str
    count: int

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or type(self.count) is not int or self.count <= 0:
            raise PrivateKnowledgeError("residual_finding_invalid")


def scan_residuals(deidentified: object) -> tuple[ResidualFinding, ...]:
    text = getattr(deidentified, "text", deidentified)
    if not isinstance(text, str):
        return (ResidualFinding("residual_input_invalid", 1),)
    scrubbed = PLACEHOLDER.sub(" ", text)
    counts: dict[str, int] = {}
    if AMBIGUOUS_CONTROLS.search(scrubbed):
        counts["residual_ambiguous_control"] = 1
    for kind, pattern in PATTERNS:
        count = sum(1 for _match in pattern.finditer(scrubbed))
        if count:
            counts[f"residual_{kind.lower()}"] = count
    for kind, pattern in IDENTITY_LIKE_PATTERNS:
        count = sum(1 for _match in pattern.finditer(scrubbed))
        if count:
            counts[f"residual_{kind.lower()}"] = count
    ambiguous = re.findall(r"(?<!\w)[A-Z]{2,}[-_:][A-Z0-9][A-Z0-9_-]{4,}(?!\w)", scrubbed)
    if ambiguous:
        counts["residual_ambiguous_entity"] = len(ambiguous)
    return tuple(ResidualFinding(code, counts[code]) for code in sorted(counts))
