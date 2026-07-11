"""Structural clause splitting for bounded thread evidence."""

from __future__ import annotations

import re
from collections.abc import Callable


SENTENCE_SPLIT_RE = re.compile(r"[.!?。！？；;\n]+")
COMMA_SPLIT_RE = re.compile(r"[,\uFF0C]")
CONJUNCTION_SPLIT_RE = re.compile(
    r"\s+\b(?:and|but)\b\s+|同时|并且|以及|但是|不过|然而|但", re.IGNORECASE
)


def split_evidence_clauses(
    text: str,
    has_evidence: Callable[[str], bool],
    has_context: Callable[[str], bool],
) -> tuple[str, ...]:
    clauses: list[str] = []
    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    for sentence in sentences:
        raw_coordinated = [
            part.strip() for part in CONJUNCTION_SPLIT_RE.split(sentence) if part.strip()
        ]
        coordinated = _merge_fragments(raw_coordinated, has_evidence, has_context, " ")
        for clause in coordinated:
            comma_parts = [part.strip() for part in COMMA_SPLIT_RE.split(clause) if part.strip()]
            clauses.extend(_merge_fragments(comma_parts, has_evidence, has_context, ", "))
    return tuple(clauses)


def _merge_fragments(
    parts: list[str],
    has_evidence: Callable[[str], bool],
    has_context: Callable[[str], bool],
    separator: str,
) -> tuple[str, ...]:
    if not parts:
        return ()
    clauses: list[str] = []
    current = parts[0]
    for part in parts[1:]:
        if has_evidence(part) and has_context(part):
            clauses.append(current)
            current = part
        else:
            current = f"{current}{separator}{part}"
    clauses.append(current)
    return tuple(clauses)
