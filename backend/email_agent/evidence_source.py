"""Private request-local evidence source capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_id: str
    kind: Literal["thread", "attachment"]
    grounding_text: str = field(repr=False)
    public_source: str
    attachment_index: int | None = None
    parsed: bool = False
    grounding_mode: Literal["text", "visual", "hybrid"] = "text"
    cross_language_grounding_text: str | None = field(default=None, repr=False)
