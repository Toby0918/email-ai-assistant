"""Clause-local reversal checks for facts constructed from attachment text."""

from __future__ import annotations

import re


MAX_FACT_CONTEXT_CHARACTERS = 240
MAX_REVERSAL_TOKENS = 8
_CLAUSE_BOUNDARY = re.compile(
    r"[\n.!?;,]+|\b(?:but|however|yet|although|though|nevertheless)\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[A-Za-z]+(?:['\u2019][A-Za-z]+)?")
_PRE_REVERSAL = re.compile(
    r"\b(?:no|not|never|cannot|without|free\s+(?:of|from)|no\s+evidence\s+of|"
    r"no\s+longer)\b|"
    r"\b(?:ain|aren|can|couldn|didn|doesn|don|hadn|hasn|haven|isn|mightn|"
    r"mustn|needn|oughtn|shan|shouldn|wasn|weren|won|wouldn)['\u2019]t\b",
    re.IGNORECASE,
)
_POST_REVERSAL = re.compile(
    r"\b(?:absent|resolved|corrected|fixed|cleared|closed|removed|repaired|"
    r"stopped|eliminated|remediated|withdrawn|waived|cancelled|canceled|revoked)\b",
    re.IGNORECASE,
)
_ACTION_CANCELLATION = re.compile(
    r"\b(?:cancel|disregard|skip)(?:\s+(?:the|this|that|previous|prior|current))?"
    r"\s+(?:request|action|instruction)\b",
    re.IGNORECASE,
)


def is_reversed_fact_match(text: str, match: re.Match[str]) -> bool:
    """Return true when bounded context negates or retires one candidate."""
    return is_reversed_fact_span(text, match.start(), match.end())


def is_reversed_fact_span(text: str, start: int, end: int) -> bool:
    """Check finite tokens immediately before and after an absolute span."""
    clause_start, clause_end = _clause_bounds(text, start, end)
    before = _bounded_tokens(text[clause_start:start], from_end=True)
    after = _bounded_tokens(text[end:clause_end], from_end=False)
    return bool(_PRE_REVERSAL.search(before) or _POST_REVERSAL.search(after))


def is_cancelled_action_span(text: str, start: int, end: int) -> bool:
    """Reject a requested-action candidate that cancels or skips the request."""
    clause_start, _clause_end = _clause_bounds(text, start, end)
    before = text[max(clause_start, start - MAX_FACT_CONTEXT_CHARACTERS):start]
    return bool(_ACTION_CANCELLATION.search(before))


def local_fact_segment(text: str, match: re.Match[str]) -> str:
    """Return only the bounded clause containing one potential fact match."""
    start, end = _clause_bounds(text, match.start(), match.end())
    bounded_start = max(start, match.start() - MAX_FACT_CONTEXT_CHARACTERS)
    bounded_end = min(end, match.end() + MAX_FACT_CONTEXT_CHARACTERS)
    return text[bounded_start:bounded_end]


def _clause_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = 0
    right = len(text)
    for boundary in _CLAUSE_BOUNDARY.finditer(text):
        if boundary.end() <= start:
            left = boundary.end()
            continue
        if boundary.start() >= end:
            right = boundary.start()
            break
    return left, right


def _bounded_tokens(value: str, *, from_end: bool) -> str:
    tokens = _WORD.findall(value)
    selected = tokens[-MAX_REVERSAL_TOKENS:] if from_end else tokens[:MAX_REVERSAL_TOKENS]
    return " ".join(selected)
