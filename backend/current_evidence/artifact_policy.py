"""Content-free rejection predicates for current-evidence private artifacts."""

from __future__ import annotations

import re
import unicodedata


_CONTROL_CHARACTERS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f"
    r"\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"
)
_DEFAULT_IGNORABLE_CHARACTERS = re.compile(
    r"[\u034f\u115f-\u1160\u17b4-\u17b5\u180b-\u180f\u2065\u3164"
    r"\ufe00-\ufe0f\uffa0\ufff0-\ufff8\U000e0000-\U000e0fff]"
)
_FORBIDDEN_UNICODE_CATEGORIES = ("Cf", "Cs")
_SAFE_CREDENTIAL_POLICY_PROSE = re.compile(
    r"(?i)\A(?:"
    r"password reset status is (?:complete|documented|pending|under review)|"
    r"api[-_ ]?key rotation policy is (?:documented|pending|under review)|"
    r"(?:access[-_ ]?)?token (?:expiry|expiration) is (?:documented|pending|"
    r"tomorrow|under review|handled by the provider boundary)|"
    r"private[-_ ]?key rotation is (?:documented|pending|under review|"
    r"never delegated to the browser)|"
    r"cookie policy (?:is documented|is under review|needs review)|"
    r"session[-_ ]?id expiry is (?:documented|pending|under review)"
    r")[.!?]?\Z"
)
_RAW_MESSAGE_HEADER = re.compile(
    r"^[ \t]*(?:subject|from|to|cc|bcc|reply-to|date|message-id|"
    r"in-reply-to|references|return-path|received)\s*[:：]",
    re.IGNORECASE | re.MULTILINE,
)
_PRIVATE_METADATA_FIELD = re.compile(
    r"(?i)(?<!\w)(?:"
    r"(?:message|thread|record|case|source|attachment|snapshot|vault|"
    r"folder|customer)[-_ ]?id|(?:mailbox[-_ ]?)?uid|"
    r"file[-_ ]?name|(?:file|local)[-_ ]?path|private[-_ ]?url|"
    r"download[-_ ]?url|content[-_ ]?base64|binary|bytes|"
    r"placeholder[-_ ]?mapping|restoration[-_ ]?mapping|runtime[-_ ]?cards?|"
    r"authority(?:[-_ ]?metadata)?|snapshot[-_ ]?metadata|"
    r"(?:raw[-_ ]?)?(?:provider|model)[-_ ]?(?:response|output)|"
    r"prompt"
    r")\s*[:：=＝]"
)
_UNSEPARATED_PRIVATE_IDENTIFIER = re.compile(
    r"(?i)(?<!\w)(?:(?:message|thread|record|case|source|attachment|snapshot|"
    r"vault|folder|customer)[-_ ]?id|(?:mailbox[-_ ]?)?uid)\b"
    r"\s+(?:[-=:：＝]\s*)?\S[^|\r\n]*"
)
_LABELED_SECRET = re.compile(
    r"(?i)\b(?:password|passwd|pwd|api[-_ ]?key|client[-_ ]?secret|"
    r"private[-_ ]?key|"
    r"access[-_ ]?token|refresh[-_ ]?token|id[-_ ]?token|auth[-_ ]?token|"
    r"token|session[-_ ]?id|credentials?|secret)\b"
    r"(?:(?:\s+(?:is|equals?))|\s*[:：=＝])\s*\S[^|\r\n]*"
)
_UNSEPARATED_SECRET = re.compile(
    r"(?i)\b(?:password|passwd|pwd|api[-_ ]?key|private[-_ ]?key|"
    r"access[-_ ]?token|token|session[-_ ]?id|cookie|client[-_ ]?secret|"
    r"refresh[-_ ]?token|id[-_ ]?token|auth[-_ ]?token|credentials?|secret)\b"
    r"\s+(?:[-=:：＝]\s*)?\S[^|\r\n]*"
)
_AUTHORIZATION_FIELD = re.compile(
    r"(?i)\b(?:authorization|proxy[-_ ]?authorization|cookie|set[-_ ]?cookie)"
    r"\b\s*[:：=＝]\s*\S[^|\r\n]*"
)
_AUTH_SECRET = re.compile(
    r"(?i:\b(?:bearer|basic))\s+(?:"
    r"(?=[A-Za-z0-9._~+/-]{12,}(?![A-Za-z0-9._~+/-]))"
    r"(?=[A-Za-z0-9._~+/-]*[0-9._~+/-])"
    r"[A-Za-z0-9._~+/-]{12,}|"
    r"[A-Za-z]{16,}(?=[ \t]*(?:[.,;:!?)]|$))"
    r")(?![A-Za-z0-9._~+/-])",
    re.MULTILINE,
)
_JWT_SECRET = re.compile(
    r"(?<![\w.-])[A-Z0-9_-]{8,}\.[A-Z0-9_-]{8,}\."
    r"[A-Z0-9_-]{8,}(?![\w.-])",
    re.IGNORECASE,
)
_PREFIXED_SECRET = re.compile(
    r"(?i)(?<![\w-])(?:sk|pk|xox[baprs]|ghp|github_pat|akia)"
    r"[-_][A-Z0-9_-]{12,}"
)
_BASE64_LIKE = re.compile(
    r"(?<![A-Z0-9+/_=-])(?:[A-Z0-9+/_-]{32,}={0,2}|"
    r"[A-Z0-9+/]{16,}={1,2})(?![A-Z0-9+/_=-])",
    re.IGNORECASE,
)
_SERIALIZED_MAPPING = re.compile(
    r"(?:\{|\[)\s*['\"][^{}\[\]\r\n]{1,64}['\"]\s*:"
)
_FORBIDDEN_PATTERNS = (
    _CONTROL_CHARACTERS,
    _DEFAULT_IGNORABLE_CHARACTERS,
    _RAW_MESSAGE_HEADER,
    _PRIVATE_METADATA_FIELD,
    _UNSEPARATED_PRIVATE_IDENTIFIER,
    _LABELED_SECRET,
    _UNSEPARATED_SECRET,
    _AUTHORIZATION_FIELD,
    _AUTH_SECRET,
    _JWT_SECRET,
    _PREFIXED_SECRET,
    _BASE64_LIKE,
    _SERIALIZED_MAPPING,
)


def has_forbidden_artifact(value: str) -> bool:
    """Return only whether a bounded string contains a forbidden artifact."""
    normalized = unicodedata.normalize("NFKC", value)
    if any(
        unicodedata.category(character) in _FORBIDDEN_UNICODE_CATEGORIES
        for character in normalized
    ):
        return True
    safe_policy_prose = _SAFE_CREDENTIAL_POLICY_PROSE.search(normalized) is not None
    return any(
        pattern.search(normalized) is not None
        for pattern in _FORBIDDEN_PATTERNS
        if not (safe_policy_prose and pattern is _UNSEPARATED_SECRET)
    )


__all__ = ["has_forbidden_artifact"]
