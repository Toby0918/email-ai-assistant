"""Shared local-only sensitive-span recognition without captured-value output."""

from __future__ import annotations

import re
from collections.abc import Iterable


PLACEHOLDER = re.compile(r"<[A-Z_]+_[1-9][0-9]*>")
AMBIGUOUS_CONTROLS = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")

_PROMPT = re.compile(
    r"(?im)^[^\r\n.!?]*(?:ignore\s+(?:all\s+)?previous\s+instructions|"
    r"system\s+prompt|reveal\s+(?:the\s+)?prompt|"
    r"忽略.{0,12}(?:指令|提示词)|你现在是)[^\r\n.!?]*(?:[.!?]|$)"
)

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PROMPT_INJECTION", _PROMPT),
    ("MESSAGE_ID", re.compile(r"(?i)(?:message-id\s*:\s*)?<[^<>\s]+@[^<>\s]+>")),
    ("UNC_PATH", re.compile(r"\\\\[^\\\s]+\\[^\r\n\s;,]+")),
    ("LOCAL_PATH", re.compile(r"(?i)(?:[a-z]:\\|/(?:home|users|var|tmp)/)[^\r\n\s]+")),
    ("URL", re.compile(r"(?i)\b(?:https?|ftp)://[^\s<>]+")),
    ("EMAIL", re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}\b")),
    ("SOURCE_HASH", re.compile(r"(?i)\b(?:sha(?:256)?\s*[:=]?\s*)?[0-9a-f]{64}\b")),
    ("SOURCE_LOCATOR", re.compile(r"(?i)\b(?:source\s+(?:record|locator)|record[_ -]?id)\s*[:=#]?\s*[0-9a-f-]{16,}\b")),
    ("RESTORATION_HINT", re.compile(r"(?i)\b(?:restore|recover|replace).{0,30}(?:original|placeholder|mapping|value)\b")),
    ("ORDER_ID", re.compile(r"(?i)\b(?:po|order)\s*[:#-]?\s*[a-z0-9][a-z0-9-]{3,}\b")),
    ("INVOICE_ID", re.compile(r"(?i)\b(?:inv|invoice)\s*[:#-]?\s*[a-z0-9][a-z0-9-]{3,}\b")),
    ("TRACKING_ID", re.compile(r"(?i)\b(?:trk|tracking)\s*[:#-]?\s*[a-z0-9][a-z0-9-]{3,}\b")),
    ("PART_ID", re.compile(r"(?i)\b(?:pn|part)\s*[:#-]?\s*[a-z0-9][a-z0-9-]{3,}\b")),
    ("TRANSACTION_ID", re.compile(r"(?i)\b(?:txn|transaction)\s*[:#-]?\s*[a-z0-9][a-z0-9-]{3,}\b")),
    ("AMOUNT", re.compile(r"(?i)(?:\b(?:usd|cny|rmb|eur|gbp)\s*|[$¥€£]\s*)\d[\d,]*(?:\.\d{1,2})?\b")),
    ("DATE", re.compile(r"\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")),
    ("ADDRESS", re.compile(r"(?i)\b\d{1,6}\s+[a-z][a-z .'-]{2,}\s(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr)\b|[一-鿿]{2,}(?:路|街|大道)\d+号")),
    ("FILENAME", re.compile(r"(?i)(?<![/\\\w.-])[\w.-]{1,120}\.(?:pdf|docx?|xlsx?|png|jpe?g|txt|csv|zip)\b")),
    ("DOMAIN", re.compile(r"(?i)\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b")),
)


def iter_context_patterns(context: object) -> Iterable[tuple[str, re.Pattern[str]]]:
    if context is None:
        return ()
    if not isinstance(context, dict) or set(context) - {"people", "organizations"}:
        raise TypeError
    result: list[tuple[str, re.Pattern[str]]] = []
    for key, kind in (("people", "PERSON"), ("organizations", "ORGANIZATION")):
        values = context.get(key, ())
        if not isinstance(values, (list, tuple)) or len(values) > 100:
            raise TypeError
        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200:
                raise TypeError
            normalized.append(value.strip())
        for value in sorted(set(normalized), key=len, reverse=True):
            result.append((kind, re.compile(re.escape(value), re.IGNORECASE)))
    return tuple(result)
