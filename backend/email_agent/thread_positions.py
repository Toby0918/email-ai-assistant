"""Bounded explicit position identities for atomic thread work items."""

from __future__ import annotations

import re


_POSITION_RE = re.compile(
    r"(?<![A-Z0-9_])(?P<label>line|item|option|row)\s*(?:#|no\.?\s*)?"
    r"(?P<token>(?=[A-Z0-9-]{1,16}(?![A-Z0-9_-]))(?=[A-Z0-9-]*\d)"
    r"[A-Z0-9-]+|[A-Z])(?![A-Z0-9_-])",
    re.IGNORECASE,
)


def extract_positions(text: str) -> tuple[str, ...]:
    return tuple(
        f"{match.group('label').lower()}:{match.group('token').upper()}"
        for match in _POSITION_RE.finditer(text)
    )
