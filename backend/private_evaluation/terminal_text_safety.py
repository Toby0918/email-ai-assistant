"""Pure allowlist for text that may be rendered in a real terminal."""

from __future__ import annotations

import unicodedata


_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})


def terminal_text_is_safe(value: object) -> bool:
    """Allow ordinary Unicode text and LF, rejecting terminal controls."""
    if type(value) is not str:
        return False
    return all(
        character == "\n"
        or unicodedata.category(character) not in _FORBIDDEN_CATEGORIES
        for character in value
    )
