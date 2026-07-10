"""Bounded text accumulation and privacy-safe display sanitization."""

from __future__ import annotations

import re


MAX_EXTRACTED_CHARACTERS = 2_000

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_NON_WHITESPACE_TOKEN = re.compile(r"\S+")
_URI_MARKER = re.compile(r"(?:[A-Za-z][A-Za-z0-9+.-]*:|www\.)\S", re.IGNORECASE)


class TextBudget:
    def __init__(self, limit: int = MAX_EXTRACTED_CHARACTERS) -> None:
        self.limit = limit
        self.parts: list[str] = []
        self.character_count = 0
        self.truncated = False

    @property
    def exhausted(self) -> bool:
        return self.character_count >= self.limit

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def add(self, value: str, unit_limit: int, separator: str = "\n") -> None:
        if self.exhausted:
            self.truncated = True
            return
        bounded_value = value[:unit_limit]
        if len(value) > unit_limit:
            self.truncated = True
        safe_value = sanitize_text(bounded_value)
        if len(safe_value) > unit_limit:
            safe_value = safe_value[:unit_limit]
            self.truncated = True
        if not safe_value:
            return
        prefix = separator if self.parts else ""
        available = self.limit - self.character_count
        addition = f"{prefix}{safe_value}"
        if len(addition) > available:
            addition = addition[:available]
            self.truncated = True
        self.parts.append(addition)
        self.character_count += len(addition)

    def mark_omitted(self) -> None:
        self.truncated = True


def sanitize_text(value: str) -> str:
    without_controls = _CONTROL_CHARACTERS.sub("", value)
    without_urls = _NON_WHITESPACE_TOKEN.sub(_redact_uri_token, without_controls)
    return re.sub(r"\s+", " ", without_urls).strip()


def _redact_uri_token(match: re.Match[str]) -> str:
    token = match.group(0)
    if _URI_MARKER.search(token):
        return "[link removed]"
    return token
