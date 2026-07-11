"""Bounded explicit position identities for atomic thread work items."""

from __future__ import annotations

import re


_POSITION_TOKEN = (
    r"(?:[A-Z]|(?=[A-Z0-9-]{1,16}(?![A-Z0-9_-]))"
    r"(?=[A-Z0-9-]*\d)[A-Z0-9-]+)"
)
_POSITION_RE = re.compile(
    rf"(?<![A-Z0-9_])(?P<label>lines?|items?|options?|rows?)\s*"
    rf"(?:#|no\.?\s*)?(?P<token>{_POSITION_TOKEN})(?![A-Z0-9_-])",
    re.IGNORECASE,
)
_POSITION_LIST_RE = re.compile(
    rf"\b(?P<label>lines?|items?|options?|rows?)\s+"
    rf"(?P<values>{_POSITION_TOKEN}(?:\s*,\s*{_POSITION_TOKEN})+"
    rf"(?:\s*,?\s*(?:and|&)\s*{_POSITION_TOKEN})?|"
    rf"{_POSITION_TOKEN}\s+(?:and|&)\s+{_POSITION_TOKEN})"
    rf"(?![A-Z0-9_-])",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(_POSITION_TOKEN, re.IGNORECASE)
_LIST_SEPARATOR_RE = re.compile(r"\s*(?:,|\band\b|&)\s*", re.IGNORECASE)


def expand_position_lists(text: str) -> str:
    return _POSITION_LIST_RE.sub(_expanded_list, text)


def extract_positions(text: str) -> tuple[str, ...]:
    return tuple(
        f"{match.group('label').lower().rstrip('s')}:{match.group('token').upper()}"
        for match in _POSITION_RE.finditer(text)
    )


def _expanded_list(match: re.Match[str]) -> str:
    label = match.group("label").lower().rstrip("s")
    tokens = tuple(
        token
        for token in _LIST_SEPARATOR_RE.split(match.group("values"))
        if _TOKEN_RE.fullmatch(token)
    )
    return ", ".join(f"{label} {token}" for token in tokens)
