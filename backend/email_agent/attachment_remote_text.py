"""Privacy sanitization for bounded attachment text sent to remote models."""

from __future__ import annotations

import re
from dataclasses import dataclass


_CONTROL_CHARACTERS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"
)
_ACTIVE_TAG_BLOCK = re.compile(
    r"<(?P<tag>script|object|embed|iframe)\b[^>]*>.*?</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_UNCLOSED_ACTIVE_TAG = re.compile(
    r"<\s*(?:script|object|embed|iframe)\b[^>]*>[^|\r\n]*",
    re.IGNORECASE,
)
_ACTIVE_TAG = re.compile(r"<\s*/?\s*(?:script|object|embed|iframe)\b[^>]*>", re.IGNORECASE)
_ACTIVE_CONTENT_FIELD = re.compile(
    r"(?i)(?:\b(?:vba|macro(?:s)?|auto_?open|document_?open|workbook_?open|"
    r"activex|ddeauto|powershell|cmd\.exe|mshta)\b|"
    r"\bon(?:load|error|click|mouseover)\s*=)[^|\r\n]*"
)
_SCHEME_URI = re.compile(
    r"(?<![\w.+-])(?P<scheme>[A-Z][A-Z0-9+.-]{0,31}):[^\s<>{}\[\]]+",
    re.IGNORECASE,
)
_SCHEME_RELATIVE_URI = re.compile(r"(?<![\w:/])//[^\s<>{}\[\]]+")
_WWW_URI = re.compile(r"(?<![@\w.-])www\.[^\s<>{}\[\]]+", re.IGNORECASE)
_BARE_HOST = re.compile(
    r"(?<![\\/@\w.-])(?:[A-Z0-9._~%!$&'()*+,;=-]+:[^@\s/|]+@)?(?:"
    r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}|"
    r"(?:\d{1,3}\.){3}\d{1,3})"
    r"(?::\d{1,5})?(?:/[^\s<>{}\[\]|]*)?(?:\?[^\s<>{}\[\]|]*)?(?:#[^\s<>{}\[\]|]*)?",
    re.IGNORECASE,
)
_EMAIL_ADDRESS = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
_LABELED_SECRET = re.compile(
    r"(?i)\b(?:authorization|proxy[-_ ]?authorization|cookie|set[-_ ]?cookie|"
    r"password|passwd|pwd|api[-_ ]?key|client[-_ ]?secret|private[-_ ]?key|"
    r"access[-_ ]?token|refresh[-_ ]?token|id[-_ ]?token|auth[-_ ]?token|"
    r"token|session[-_ ]?id|session(?![-_ ]?id)|credentials?|secret|key)"
    r"\b(?![\s_-]+(?:reset|rotation|expiry|expiration|expired|policy|issue)\b)"
    r"(?:(?:\s+(?:is|equals?))|\s*[:=]|\s+)\s*[^|\r\n]*"
)
_SAFE_BUSINESS_SUFFIX = re.compile(
    r"[.!?]\s+(?P<business>(?:(?:PO|RFQ|invoice|part|qty|quantity|due|deadline|"
    r"currency|date|USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD)\b|"
    r"\d{4}-\d{2}-\d{2}\b|[$€£¥]\s*\d)[^|\r\n]*)$",
    re.IGNORECASE,
)
_AUTH_SECRET = re.compile(r"(?i)\b(?:bearer|basic)\b[^|\r\n]*")
_JWT_SECRET = re.compile(
    r"(?<![\w.-])[A-Z0-9_-]{8,}\.[A-Z0-9_-]{8,}\.[A-Z0-9_-]{8,}(?![\w.-])",
    re.IGNORECASE,
)
_PREFIXED_SECRET = re.compile(
    r"(?i)(?<![\w-])(?:sk|pk|xox[baprs]|ghp|github_pat|akia)[-_][A-Z0-9_-]{12,}"
)
_BASE64_LIKE = re.compile(
    r"(?<![A-Z0-9+/_=-])(?:[A-Z0-9+/_-]{32,}={0,2}|[A-Z0-9+/]{16,}={1,2})"
    r"(?![A-Z0-9+/_=-])",
    re.IGNORECASE,
)
_BUSINESS_ID_TOKEN = re.compile(
    r"(?:PO|RFQ|INV|PN|PART)[-_/]?[A-Z0-9][A-Z0-9._/-]*",
    re.IGNORECASE,
)
_WINDOWS_PATH = re.compile(r"(?<!\w)[A-Z]:[\\/][^\s|,;]+", re.IGNORECASE)
_UNC_PATH = re.compile(r"(?<!\w)\\\\[^\\/\s]+[\\/][^\s|,;]+")
_ROOTED_OR_DOT_PATH = re.compile(
    r"(?<![\w@])(?:\.{1,2}[\\/]|~?[\\/])"
    r"[A-Z0-9._~-]+(?:[\\/][A-Z0-9._~-]+)*",
    re.IGNORECASE,
)
_RELATIVE_PATH = re.compile(
    r"(?<![\w@.-])(?:[A-Z0-9._~-]+[\\/])+[A-Z0-9._~-]+(?![\w.-])",
    re.IGNORECASE,
)
_DATE_PATH_SHAPE = re.compile(r"\d{1,4}/\d{1,2}/\d{1,4}")
_CURRENCY_PAIR = re.compile(
    r"(?:USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD)/(?:USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD)",
    re.IGNORECASE,
)
_PART_SLASH_ID = re.compile(r"(?:PN|PART)/[A-Z0-9][A-Z0-9._-]{1,63}", re.IGNORECASE)
_LETTER_RELATION = re.compile(r"(?:[A-Z]/){1,4}[A-Z]", re.IGNORECASE)
_BUSINESS_LABELS = {
    "amount", "deadline", "due", "invoice", "part", "po", "price", "qty",
    "quantity", "rfq", "size", "total", "usd", "eur", "cny", "rmb",
}
_BOUNDARY_ID_TOKEN = re.compile(
    r"(?i)\b(?:po|order|txn|transaction)\s*[:#-]?\s*[a-z0-9][a-z0-9-]{3,}\b"
)
_BOUNDARY_PHONE_TOKEN = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")
_BOUNDARY_SENSITIVE_PATTERNS = (_EMAIL_ADDRESS, _BOUNDARY_ID_TOKEN, _BOUNDARY_PHONE_TOKEN)
_NO_SPACE_SENTENCE_BOUNDARIES = frozenset("!?。！？")


@dataclass(frozen=True, slots=True, repr=False)
class SanitizedModelText:
    text: str
    link_was_present: bool
    truncated: bool


def sanitize_remote_text(
    value: str,
    max_characters: int,
    link_marker: str | None = None,
) -> SanitizedModelText:
    """Remove remote-model privacy canaries before applying the final character bound."""
    cleaned = _CONTROL_CHARACTERS.sub("", str(value or "")).replace("\r\n", "\n").replace("\r", "\n")
    cleaned, link_was_present = _remove_links(cleaned, link_marker)
    for pattern in (_ACTIVE_TAG_BLOCK, _UNCLOSED_ACTIVE_TAG, _ACTIVE_TAG, _ACTIVE_CONTENT_FIELD):
        cleaned = pattern.sub(" ", cleaned)
    cleaned, emails = _protect_emails(cleaned)
    for pattern, replacement in (
        (_LABELED_SECRET, _remove_labeled_secret),
        (_AUTH_SECRET, " "),
        (_JWT_SECRET, " "),
        (_PREFIXED_SECRET, " "),
        (_BASE64_LIKE, _remove_base64_like),
        (_UNC_PATH, " "),
        (_WINDOWS_PATH, " "),
        (_ROOTED_OR_DOT_PATH, _remove_rooted_path),
        (_RELATIVE_PATH, _remove_relative_path),
    ):
        cleaned = pattern.sub(replacement, cleaned)
    normalized = _normalize(_restore_emails(cleaned, emails))
    limit = max(0, int(max_characters))
    return SanitizedModelText(
        _token_safe_bound(normalized, limit),
        link_was_present,
        len(normalized) > limit,
    )


def _remove_links(value: str, link_marker: str | None) -> tuple[str, bool]:
    found = False

    def replace_scheme(match: re.Match[str]) -> str:
        nonlocal found
        token = match.group(0)
        scheme = match.group("scheme").casefold()
        if scheme in _BUSINESS_LABELS and not token.startswith(f"{scheme}://"):
            return token
        if re.match(r"^[A-Z]:[\\/](?![\\/])", token, re.IGNORECASE):
            return token
        found = True
        return _marker(link_marker)

    value = _SCHEME_URI.sub(replace_scheme, value)
    for pattern in (_SCHEME_RELATIVE_URI, _WWW_URI, _BARE_HOST):
        if pattern.search(value):
            found = True
            value = pattern.sub(_marker(link_marker), value)
    return value, found


def _protect_emails(value: str) -> tuple[str, tuple[str, ...]]:
    emails: list[str] = []

    def protect(match: re.Match[str]) -> str:
        emails.append(match.group(0))
        return f"\ue000{len(emails) - 1}\ue001"

    return _EMAIL_ADDRESS.sub(protect, value), tuple(emails)


def _restore_emails(value: str, emails: tuple[str, ...]) -> str:
    for index, email in enumerate(emails):
        value = value.replace(f"\ue000{index}\ue001", email)
    return value


def _marker(link_marker: str | None) -> str:
    return link_marker or " "


def _remove_base64_like(match: re.Match[str]) -> str:
    return match.group(0) if _BUSINESS_ID_TOKEN.fullmatch(match.group(0)) else " "


def _remove_labeled_secret(match: re.Match[str]) -> str:
    suffix = _SAFE_BUSINESS_SUFFIX.search(match.group(0))
    return suffix.group("business") if suffix else " "


def _remove_rooted_path(match: re.Match[str]) -> str:
    value = match.group(0)
    return " " if any(char.isalpha() for char in value) else value


def _remove_relative_path(match: re.Match[str]) -> str:
    value = match.group(0)
    slash_value = value.replace("\\", "/")
    if (
        _DATE_PATH_SHAPE.fullmatch(slash_value)
        or _CURRENCY_PAIR.fullmatch(slash_value)
        or _PART_SLASH_ID.fullmatch(slash_value)
        or _LETTER_RELATION.fullmatch(slash_value)
        or not any(char.isalpha() for char in slash_value)
    ):
        return value
    return " "


def _normalize(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _token_safe_bound(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 0:
        return ""
    sensitive_start = _crossing_sensitive_start(value, limit)
    if sensitive_start is not None:
        return _token_safe_bound(value, sensitive_start)
    prefix = value[:limit]
    if prefix[-1].isspace() or value[limit].isspace():
        return prefix.rstrip()
    boundary = max(
        (index for index, character in enumerate(prefix) if character.isspace()),
        default=-1,
    )
    sentence_boundary = max(
        (
            index
            for index, character in enumerate(prefix)
            if character in _NO_SPACE_SENTENCE_BOUNDARIES
        ),
        default=-1,
    )
    cut = max(boundary, sentence_boundary + 1)
    return prefix[:cut].rstrip() if cut >= 0 else ""


def _crossing_sensitive_start(value: str, limit: int) -> int | None:
    starts = (
        match.start()
        for pattern in _BOUNDARY_SENSITIVE_PATTERNS
        for match in pattern.finditer(value)
        if match.start() < limit < match.end()
    )
    return min(starts, default=None)
