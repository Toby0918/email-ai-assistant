"""Private, bounded attachment text projection for remote model requests."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass


MAX_MODEL_CHARACTERS_PER_ATTACHMENT = 6_000
MAX_MODEL_CHARACTERS_TOTAL = 24_000

_CONTROL_CHARACTERS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"
)
_SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
_ACTIVE_CONTENT_MARKER = re.compile(
    r"(?i)(?:<\s*/?\s*(?:script|object|embed|iframe)\b[^>]*>|"
    r"\b(?:vba|macro(?:s)?|auto_?open|document_?open|workbook_?open|"
    r"activex|ddeauto|powershell|cmd\.exe|mshta)\b|"
    r"\bon(?:load|error|click|mouseover)\s*=)"
)
_SCHEME_URI = re.compile(
    r"(?<![\w.+-])(?P<scheme>[A-Z][A-Z0-9+.-]{0,31}):[^\s<>{}\[\]]+",
    re.IGNORECASE,
)
_SCHEME_RELATIVE_URI = re.compile(r"(?<![\w:/])//[^\s<>{}\[\]]+")
_WWW_URI = re.compile(r"(?<![@\w.-])www\.[^\s<>{}\[\]]+", re.IGNORECASE)
_BARE_DOMAIN = re.compile(
    r"(?<![@\w.-])(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
    r"(?:com|org|net|edu|gov|mil|io|ai|co|cn|uk|de|fr|jp|au|ca|us|"
    r"info|biz|dev|app|cloud|online|site|tech|test)"
    r"(?::\d{1,5})?(?:/[^\s<>{}\[\]]*)?(?:\?[^\s<>{}\[\]]*)?(?:#[^\s<>{}\[\]]*)?",
    re.IGNORECASE,
)
_EMAIL_ADDRESS = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
_LABELED_SECRET = re.compile(
    r"(?i)\b(?:authorization|proxy[-_ ]?authorization|cookie|set[-_ ]?cookie|"
    r"password|passwd|pwd|api[-_ ]?key|access[-_ ]?token|refresh[-_ ]?token|"
    r"id[-_ ]?token|auth[-_ ]?token|token|session(?:[-_ ]?id)?|credentials?|secret)"
    r"\b\s*[:=]\s*(?:(?:bearer|basic)\s+)?"
    r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;|]+)"
)
_AUTH_SECRET = re.compile(
    r"(?i)\b(?:bearer|basic)\s+[A-Z0-9._~+/=-]{6,}"
)
_JWT_SECRET = re.compile(
    r"(?<![\w.-])[A-Z0-9_-]{8,}\.[A-Z0-9_-]{8,}\.[A-Z0-9_-]{8,}(?![\w.-])",
    re.IGNORECASE,
)
_PREFIXED_SECRET = re.compile(
    r"(?i)(?<![\w-])(?:sk|pk|xox[baprs]|ghp|github_pat|akia)[-_][A-Z0-9_-]{12,}"
)
_BASE64_LIKE = re.compile(r"(?<![A-Z0-9+/])[A-Z0-9+/]{32,}={0,2}(?![A-Z0-9+/=])", re.IGNORECASE)
_WINDOWS_PATH = re.compile(r"(?<!\w)[A-Z]:[\\/][^\s|,;]+", re.IGNORECASE)
_UNC_PATH = re.compile(r"(?<!\w)\\\\[^\\/\s]+[\\/][^\s|,;]+")
_ROOTED_OR_DOT_PATH = re.compile(
    r"(?<![\w@])(?:\.\.?[\\/]|~[\\/]|[\\/])"
    r"(?:[A-Z0-9._~-]+[\\/])+[A-Z0-9._~-]+",
    re.IGNORECASE,
)
_RELATIVE_PATH = re.compile(
    r"(?<![\w@.-])(?:[A-Z0-9._~-]+[\\/])+(?:[A-Z0-9._~-]+)",
    re.IGNORECASE,
)
_DATE_PATH_SHAPE = re.compile(r"\d{1,4}/\d{1,2}/\d{1,4}")
_BUSINESS_LABELS = {
    "amount", "deadline", "due", "invoice", "part", "po", "price", "qty",
    "quantity", "rfq", "size", "total", "usd", "eur", "cny", "rmb",
}


@dataclass(frozen=True, slots=True, repr=False)
class SanitizedModelText:
    text: str
    link_was_present: bool
    truncated: bool


@dataclass(frozen=True, slots=True, repr=False)
class AttachmentModelCandidate:
    source_id: str
    text: str


@dataclass(frozen=True, slots=True, repr=False)
class AttachmentModelContextItem:
    source_id: str
    text: str
    link_was_present: bool
    truncated: bool


@dataclass(frozen=True, slots=True, repr=False)
class AttachmentAnalysisBundle:
    display_insight: dict[str, object]
    model_candidate: AttachmentModelCandidate | None


def attachment_model_candidate(source_id: str, value: str) -> AttachmentModelCandidate | None:
    """Construct a repr-safe candidate only from already-bounded extracted text."""
    return AttachmentModelCandidate(source_id, value) if value else None


def sanitize_remote_text(
    value: str,
    max_characters: int,
    link_marker: str | None = None,
) -> SanitizedModelText:
    """Remove remote-model privacy canaries before applying the final character bound."""
    cleaned = _CONTROL_CHARACTERS.sub("", str(value or "")).replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _SCRIPT_BLOCK.sub(" ", cleaned)
    cleaned = _ACTIVE_CONTENT_MARKER.sub(" ", cleaned)
    cleaned, link_was_present = _remove_links(cleaned, link_marker)
    cleaned, emails = _protect_emails(cleaned)
    cleaned = _BARE_DOMAIN.sub(_marker(link_marker), cleaned)
    link_was_present = link_was_present or bool(_BARE_DOMAIN.search(_restore_emails(cleaned, emails)))
    cleaned = _LABELED_SECRET.sub(" ", cleaned)
    cleaned = _AUTH_SECRET.sub(" ", cleaned)
    cleaned = _JWT_SECRET.sub(" ", cleaned)
    cleaned = _PREFIXED_SECRET.sub(" ", cleaned)
    cleaned = _BASE64_LIKE.sub(_remove_base64_like, cleaned)
    cleaned = _UNC_PATH.sub(" ", cleaned)
    cleaned = _WINDOWS_PATH.sub(" ", cleaned)
    cleaned = _ROOTED_OR_DOT_PATH.sub(" ", cleaned)
    cleaned = _RELATIVE_PATH.sub(_remove_relative_path, cleaned)
    normalized = _normalize(_restore_emails(cleaned, emails))
    limit = max(0, int(max_characters))
    return SanitizedModelText(normalized[:limit], link_was_present, len(normalized) > limit)


def build_attachment_model_context(
    candidates: Iterable[AttachmentModelCandidate],
) -> tuple[AttachmentModelContextItem, ...]:
    """Sanitize candidates in input order under per-item and aggregate character limits."""
    accepted: list[AttachmentModelContextItem] = []
    remaining = MAX_MODEL_CHARACTERS_TOTAL
    for candidate in candidates:
        if remaining <= 0:
            break
        limit = min(MAX_MODEL_CHARACTERS_PER_ATTACHMENT, remaining)
        sanitized = sanitize_remote_text(candidate.text, limit)
        if not sanitized.text:
            continue
        accepted.append(AttachmentModelContextItem(
            candidate.source_id,
            sanitized.text,
            sanitized.link_was_present,
            sanitized.truncated,
        ))
        remaining -= len(sanitized.text)
    return tuple(accepted)


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
    for pattern in (_SCHEME_RELATIVE_URI, _WWW_URI):
        if pattern.search(value):
            found = True
            value = pattern.sub(_marker(link_marker), value)
    bare_found = bool(_BARE_DOMAIN.search(value))
    return value, found or bare_found


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
    value = match.group(0)
    has_mixed_classes = any(char.islower() for char in value) and any(char.isupper() for char in value)
    looks_encoded = has_mixed_classes and (any(char.isdigit() for char in value) or value.endswith("="))
    return " " if looks_encoded else value


def _remove_relative_path(match: re.Match[str]) -> str:
    value = match.group(0)
    if _DATE_PATH_SHAPE.fullmatch(value) or not any(char.isalpha() for char in value):
        return value
    return " "


def _normalize(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
