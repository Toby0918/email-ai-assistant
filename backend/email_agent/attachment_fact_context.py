"""Clause-local reversal checks for facts constructed from attachment text."""

from __future__ import annotations

import re


MAX_FACT_CONTEXT_CHARACTERS = 240
MAX_REVERSAL_TOKENS = 8
_CLAUSE_BOUNDARY = re.compile(
    r"[\n.!?;,]+|\b(?:but|however|yet|although|though|nevertheless)\b",
    re.IGNORECASE,
)
_ACTION_CLAUSE_BOUNDARY = re.compile(
    r"[\n.!?;,]+|\b(?:and|but|however|then|yet|although|though|nevertheless)\b",
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
_PRE_RESOLUTION_INSTRUCTION = re.compile(
    r"\b(?:resolve|repair|remove|stop|fix|clear|eliminate|remediate)(?:\s+the)?$",
    re.IGNORECASE,
)
_POST_RESOLUTION = re.compile(
    r"\b(?:absent|resolved|corrected|fixed|cleared|closed|removed|repaired|"
    r"stopped|eliminated|remediated|withdrawn|waived|cancelled|canceled|revoked)\b",
    re.IGNORECASE,
)
_POST_ABSENCE = re.compile(
    r"\b(?:not\s+required|(?:do|does|did)\s+not\s+apply|"
    r"no\s+longer\s+applicable|optional)\b",
    re.IGNORECASE,
)
_ADJACENT_ABSENCE_PREFIX = re.compile(
    r"(?:\b(?:0|zero|nil)\s+|\bnon-)\s*$",
    re.IGNORECASE,
)
_ADJACENT_FREE_SUFFIX = re.compile(r"^(?:\s*-\s*|\s+)free\b", re.IGNORECASE)
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
    return bool(
        _PRE_REVERSAL.search(before)
        or _PRE_RESOLUTION_INSTRUCTION.search(before)
        or _POST_ABSENCE.search(after)
        or _has_unnegated_resolution(after)
    )


def is_adjacent_absence_match(text: str, match: re.Match[str]) -> bool:
    """Reject only absence markers immediately adjacent to a quality signal."""
    before = text[max(0, match.start() - 32):match.start()]
    after = text[match.end():min(len(text), match.end() + 16)]
    return bool(
        _ADJACENT_ABSENCE_PREFIX.search(before)
        or _ADJACENT_FREE_SUFFIX.search(after)
    )


def action_clause_spans(text: str, start: int, end: int) -> list[tuple[int, int, bool]]:
    """Return clauses and whether a contrast permits one pending verb."""
    spans: list[tuple[int, int, bool]] = []
    cursor = start
    may_inherit = False
    for boundary in _ACTION_CLAUSE_BOUNDARY.finditer(text, start, end):
        appended = _append_trimmed_span(
            spans,
            text,
            cursor,
            boundary.start(),
            may_inherit,
        )
        boundary_text = boundary.group().lower()
        if boundary_text in {"but", "however"}:
            may_inherit = True
        elif appended:
            may_inherit = False
        cursor = boundary.end()
    _append_trimmed_span(spans, text, cursor, end, may_inherit)
    return spans


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


def _has_unnegated_resolution(after: str) -> bool:
    return any(
        not _resolution_is_negated(after, match.start())
        for match in _POST_RESOLUTION.finditer(after)
    )


def _resolution_is_negated(value: str, resolution_start: int) -> bool:
    tokens = [token.lower() for token in _WORD.findall(value[:resolution_start])]
    if not tokens:
        return False
    if _is_negation_token(tokens[-1]):
        return True
    if tokens[-1] in {"be", "been", "being"} and len(tokens) > 1:
        return _is_negation_token(tokens[-2])
    return len(tokens) > 1 and tokens[-2:] == ["no", "longer"]


def _is_negation_token(value: str) -> bool:
    if value in {"no", "not", "never"}:
        return True
    return bool(re.fullmatch(
        r"(?:ain|aren|can|couldn|didn|doesn|don|hadn|hasn|haven|isn|mightn|"
        r"mustn|needn|oughtn|shan|shouldn|wasn|weren|won|wouldn)['\u2019]t",
        value,
        re.IGNORECASE,
    ))


def _append_trimmed_span(
    spans: list[tuple[int, int, bool]],
    text: str,
    start: int,
    end: int,
    may_inherit: bool,
) -> bool:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append((start, end, may_inherit))
        return True
    return False
