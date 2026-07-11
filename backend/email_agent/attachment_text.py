"""Bounded text accumulation and privacy-safe display sanitization."""

from __future__ import annotations

import re


MAX_EXTRACTED_CHARACTERS = 2_000

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_NON_WHITESPACE_TOKEN = re.compile(r"\S+")
_URI_MARKER = re.compile(r"(?:[A-Za-z][A-Za-z0-9+.-]*:|www\.)\S", re.IGNORECASE)
_EMAIL_ADDRESS = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
_LOCAL_PATH = re.compile(
    r"(?<!\w)(?:[A-Z]:[\\/][^\s]+|\\\\[^\\/\s]+[\\/][^\s]+|~?[\\/]"
    r"(?:[^\\/\s]+[\\/])+[^\s]*)",
    re.IGNORECASE,
)
_LONG_DIGIT_SEQUENCE = re.compile(r"\d(?:[\s(),.+_:/\\-]*\d){6,}")


class TextBudget:
    def __init__(self, limit: int = MAX_EXTRACTED_CHARACTERS) -> None:
        self.limit = limit
        self.parts: list[str] = []
        self.fact_parts: list[str] = []
        self.character_count = 0
        self.fact_character_count = 0
        self.truncated = False

    @property
    def exhausted(self) -> bool:
        return self.character_count >= self.limit

    @property
    def text(self) -> str:
        return "".join(self.parts)

    @property
    def fact_text(self) -> str:
        return "".join(self.fact_parts)

    def add(
        self,
        value: str,
        unit_limit: int,
        separator: str = "\n",
        *,
        fact_value: str | None = None,
    ) -> None:
        if self.exhausted:
            self.truncated = True
            return
        bounded_value = value[:unit_limit]
        self._add_fact_source(
            (fact_value if fact_value is not None else bounded_value)[:unit_limit],
            separator,
        )
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

    def _add_fact_source(self, value: str, separator: str) -> None:
        if not value or self.fact_character_count >= self.limit:
            return
        prefix = separator if self.fact_parts else ""
        addition = f"{prefix}{_CONTROL_CHARACTERS.sub('', value)}"
        available = self.limit - self.fact_character_count
        bounded = addition[:available]
        self.fact_parts.append(bounded)
        self.fact_character_count += len(bounded)

    def mark_omitted(self) -> None:
        self.truncated = True


def sanitize_text(value: str) -> str:
    without_controls = _CONTROL_CHARACTERS.sub("", value)
    without_urls = _NON_WHITESPACE_TOKEN.sub(_redact_uri_token, without_controls)
    without_emails = _EMAIL_ADDRESS.sub("[email removed]", without_urls)
    without_paths = _LOCAL_PATH.sub("[path removed]", without_emails)
    without_long_numbers = _LONG_DIGIT_SEQUENCE.sub("[number removed]", without_paths)
    return re.sub(r"\s+", " ", without_long_numbers).strip()


def _redact_uri_token(match: re.Match[str]) -> str:
    token = match.group(0)
    if _URI_MARKER.search(token):
        return "[link removed]"
    return token
