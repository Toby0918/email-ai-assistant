"""Local reversal checks for facts constructed from attachment text."""

from __future__ import annotations

import re


MAX_FACT_CONTEXT_CHARACTERS = 240
_BOUNDARIES = "\n.!?;"
_NEGATION = re.compile(
    r"\b(?:do\s+not|does\s+not|did\s+not|can\s+not|cannot|not|never|no|"
    r"no\s+evidence\s+of|no\s+longer|without|free\s+of)\b|"
    r"\b(?:don|doesn|didn|isn|aren|wasn|weren|can)['’]t\b",
    re.IGNORECASE,
)
_RESOLUTION = re.compile(
    r"\b(?:now\s+)?(?:resolved|corrected|fixed|cleared|closed)\b",
    re.IGNORECASE,
)


def is_reversed_fact_match(text: str, match: re.Match[str]) -> bool:
    """Return true when the match's local clause negates or resolves the signal."""
    segment = local_fact_segment(text, match)
    return bool(_NEGATION.search(segment) or _RESOLUTION.search(segment))


def local_fact_segment(text: str, match: re.Match[str]) -> str:
    """Return the bounded clause containing one potential fact match."""
    start = match.start()
    end = match.end()
    left = max((text.rfind(boundary, 0, start) for boundary in _BOUNDARIES), default=-1) + 1
    right_candidates = [
        position
        for boundary in _BOUNDARIES
        if (position := text.find(boundary, end)) >= 0
    ]
    right = min(right_candidates, default=len(text))
    bounded_left = max(left, start - MAX_FACT_CONTEXT_CHARACTERS)
    bounded_right = min(right, end + MAX_FACT_CONTEXT_CHARACTERS)
    return text[bounded_left:bounded_right]
