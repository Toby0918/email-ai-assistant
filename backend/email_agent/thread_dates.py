"""Bounded deterministic deadline hints for thread request atoms."""

from __future__ import annotations

import re


_DATE_RE = re.compile(
    r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)|"
    r"\d{1,2}月\d{1,2}日(?:前)?|(?:周[一二三四五六日天]|明天)(?:前)?"
)


def unambiguous_due_hint(text: str) -> str:
    hints = tuple(dict.fromkeys(match.group(0) for match in _DATE_RE.finditer(text)))
    return hints[0] if len(hints) == 1 else ""
