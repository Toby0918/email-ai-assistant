"""Conservative complete-sentence boundaries for attachment model evidence."""

from __future__ import annotations

import re


_STRONG_TERMINATORS = frozenset("!?。！？")
_CLOSERS = frozenset("\"'”’)]}】》〉」』")
_OPENERS = frozenset("\"'“‘([{【《〈「『")
_BULLETS = frozenset("-*•")
_COMMON_ABBREVIATIONS = frozenset({
    "approx", "co", "corp", "dept", "dr", "e.g", "etc", "fig", "i.e",
    "inc", "jr", "ltd", "max", "min", "mr", "mrs", "ms", "no", "prof",
    "qty", "ref", "rev", "sr", "vs",
})
_LAST_WORD = re.compile(r"([A-Za-z]+)\Z")
_INITIALISM = re.compile(r"(?:\b[A-Za-z]\.)+[A-Za-z]\Z")


def complete_sentence_prefix(
    value: str, *, final_ascii_period_is_ambiguous: bool,
) -> str:
    """Return only the prefix ending at the last conservative sentence boundary."""
    end = 0
    for _start, boundary in complete_sentence_spans(
        value,
        final_ascii_period_is_ambiguous=final_ascii_period_is_ambiguous,
    ):
        end = boundary
    return value[:end].rstrip()


def complete_sentences(value: str) -> tuple[str, ...]:
    """Split source text into conservative, independently complete sentences."""
    return tuple(
        sentence
        for start, end in complete_sentence_spans(
            value,
            final_ascii_period_is_ambiguous=False,
        )
        if (sentence := value[start:end].strip())
    )


def complete_sentence_spans(
    value: str, *, final_ascii_period_is_ambiguous: bool,
) -> tuple[tuple[int, int], ...]:
    """Return non-overlapping complete sentence spans without trusting abbreviations."""
    spans: list[tuple[int, int]] = []
    start = 0
    for index, character in enumerate(value):
        end = _boundary_end(
            value,
            index,
            character,
            final_ascii_period_is_ambiguous,
        )
        if end is None:
            continue
        if value[start:end].strip():
            spans.append((start, end))
        start = end
    return tuple(spans)


def _boundary_end(
    value: str,
    index: int,
    character: str,
    final_ascii_period_is_ambiguous: bool,
) -> int | None:
    if character in _STRONG_TERMINATORS:
        return _consume_closers(value, index + 1)
    if character != "." or not _ascii_period_is_boundary(
        value, index, final_ascii_period_is_ambiguous,
    ):
        return None
    return _consume_closers(value, index + 1)


def _ascii_period_is_boundary(
    value: str, index: int, final_ascii_period_is_ambiguous: bool,
) -> bool:
    before = value[index - 1] if index else ""
    after = value[index + 1] if index + 1 < len(value) else ""
    if before == "." or after == ".":
        return False
    if before.isdigit() and after.isdigit():
        return False
    prefix = value[:index]
    word_match = _LAST_WORD.search(prefix)
    word = word_match.group(1).casefold() if word_match else ""
    if len(word) == 1 or word in _COMMON_ABBREVIATIONS:
        return False
    if _INITIALISM.search(prefix):
        return False

    cursor = _consume_closers(value, index + 1)
    if cursor >= len(value):
        return not final_ascii_period_is_ambiguous
    if not value[cursor].isspace():
        return False
    crossed_line = False
    while cursor < len(value) and value[cursor].isspace():
        crossed_line = crossed_line or value[cursor] in "\r\n"
        cursor += 1
    if cursor >= len(value):
        return not final_ascii_period_is_ambiguous
    while cursor < len(value) and value[cursor] in _OPENERS:
        cursor += 1
    if cursor >= len(value):
        return False
    next_character = value[cursor]
    if crossed_line or next_character in _BULLETS:
        return True
    if next_character.isalpha():
        return next_character.isupper() or not next_character.isascii()
    return next_character.isdigit()


def _consume_closers(value: str, cursor: int) -> int:
    while cursor < len(value) and value[cursor] in _CLOSERS:
        cursor += 1
    return cursor


__all__ = ["complete_sentence_prefix", "complete_sentences"]
