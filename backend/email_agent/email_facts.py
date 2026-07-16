"""Deterministic fact extraction for current-email analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.exact_fact_patterns import iter_exact_identifiers

from .thread_dates import deadline_date_hints


MAX_FACT_ITEMS = 5
MAX_FACT_LENGTH = 140

_SIGNATURE_START_RE = re.compile(
    r"(?i)^\s*(?:--|best regards|kind regards|regards|sincerely|"
    r"many thanks|thanks|此致|祝好)\s*[,!.，。]?\s*$"
)
_QUOTED_HEADER_RE = re.compile(
    r"(?i)^\s*(?:from|sent|date|to|cc|subject|发件人|发送时间|日期|收件人|抄送|主题)\s*[:：]"
)
_CONTACT_LINE_RE = re.compile(
    r"(?i)^\s*(?:mobile|tel(?:ephone)?|phone|e-?mail|website?|web|"
    r"wechat|whatsapp|address|地址|电话|手机|邮箱|网址)\s*[:：]"
)
_CID_OR_IMAGE_RE = re.compile(
    r"(?i)^\s*(?:cid:|image\s*(?:caption)?\s*[:：]|"
    r"[^\s]+\.(?:png|jpe?g|gif|webp))"
)
_EMAIL_RE = re.compile(
    r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}\b"
)
_URL_RE = re.compile(r"(?i)\b(?:https?|ftp)://[^\s<>]+")


@dataclass(frozen=True)
class EmailFacts:
    references: list[str]
    quantities: list[str]
    measurements: list[str]
    deadlines: list[str]
    requested_actions: list[str]
    quality_issues: list[str]

    @property
    def has_specifics(self) -> bool:
        return any((
            self.references,
            self.quantities,
            self.measurements,
            self.deadlines,
            self.requested_actions,
            self.quality_issues,
        ))


def extract_email_facts(subject: str, sender: str, clean_body: str) -> EmailFacts:
    del sender  # Sender identity is metadata, never a business fact.
    business_body = _business_body(clean_body)
    text = "\n".join(part for part in (subject, business_body) if part)
    sentences = _sentences(business_body)
    return EmailFacts(
        references=_find_references(text),
        quantities=_find_quantities(text),
        measurements=_find_measurements(text),
        deadlines=_find_deadlines(text),
        requested_actions=_find_requested_actions(sentences),
        quality_issues=_find_quality_issues(sentences),
    )


def _find_references(text: str) -> list[str]:
    refs = [_reference_display(label, value) for label, value in iter_exact_identifiers(text)]
    for match in re.finditer(
        r"\b(?P<label>PO|RFQ|part|invoice|tracking|order)\s*"
        r"(?:#|No\.?|number|ID|ref(?:erence)?\.?)?\s*[:：#._/\-=()]*\s*"
        r"(?=[A-Z0-9._/-]{4,64}\b)(?=[A-Z0-9._/-]*\d)"
        r"[A-Z0-9][A-Z0-9._/-]{3,63}\s*(?:,|and|&)\s*"
        r"(?P<value>(?=[A-Z0-9._/-]{4,64}\b)(?=[A-Z0-9._/-]*\d)"
        r"[A-Z0-9][A-Z0-9._/-]{3,63})",
        text,
        re.IGNORECASE,
    ):
        refs.append(_reference_display(match.group("label"), match.group("value")))
    for match in re.finditer(
        r"\b(?P<label>material|booking)\s*(?:#|No\.?|number)?\s*[:\-]?\s*"
        r"(?=[A-Z0-9._/-]{4,64}\b)(?=[A-Z0-9._/-]*\d)"
        r"(?P<value>[A-Z0-9][A-Z0-9._/-]{3,63})",
        text,
        re.IGNORECASE,
    ):
        refs.append(
            match.group("value")
            if match.group("label").casefold() == "material"
            else match.group(0)
        )
    return _unique_short(refs)


def _reference_display(label: str, value: str) -> str:
    normalized = " ".join(label.split()).strip(" :：#._/-=()")
    if normalized.casefold() == "tracking":
        normalized = "tracking number"
    return f"{normalized} {value}".strip()


def _find_quantities(text: str) -> list[str]:
    patterns = [
        r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*(?:pcs|pieces|units|pc|sets|kg)\b",
        r"\b\d+(?:\.\d+)?\s*(?:pcs|pieces|units|pc|sets|kg)\b",
    ]
    return _unique_short(_find_all(patterns, text))


def _find_measurements(text: str) -> list[str]:
    patterns = [
        r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|inch|inches)\s*(?:\+/-\s*\d*(?:\.\d+)?)?",
        r"\b\d+(?:\.\d+)?\s*(?:x|×)\s*\d+(?:\.\d+)?\s*(?:mm|cm|m|inch|inches)\b",
    ]
    return _unique_short(_find_all(patterns, text))


def _find_deadlines(text: str) -> list[str]:
    patterns = [
        r"\bwithin\s+\d+\s+(?:hours?|days?|weeks?)\b",
        r"\bbefore\s+[A-Z][A-Za-z]+\b",
        r"\bby\s+(?:today|tomorrow|[A-Z][A-Za-z]+\s+\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4})\b",
        r"\b(?:asap|urgent|today|tomorrow)\b",
        r"本周[一二三四五六日天]",
        r"今天|明天|尽快|马上",
    ]
    return _unique_short([*_find_all(patterns, text), *deadline_date_hints(text)])


def _find_requested_actions(sentences: list[str]) -> list[str]:
    keywords = (
        "please",
        "kindly",
        "could you",
        "can you",
        "need to",
        "required",
        "request",
        "provide",
        "confirm",
        "check",
        "investigate",
        "support",
        "请",
        "需要",
        "确认",
        "提供",
        "回复",
        "调查",
    )
    return _sentences_with_keywords(sentences, keywords)


def _find_quality_issues(sentences: list[str]) -> list[str]:
    keywords = (
        "quality",
        "complaint",
        "defective",
        "damaged",
        "failed",
        "burrs",
        "out of tolerance",
        "defect",
        "issue",
        "质量",
        "投诉",
        "不良",
        "损坏",
        "缺陷",
        "异常",
    )
    return _sentences_with_keywords(sentences, keywords)


def _sentences(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"[\n.!?。！？;；]+", normalized)
    return [part.strip(" ;:") for part in parts if part.strip(" ;:")]


def _business_body(text: object) -> str:
    if not isinstance(text, str):
        return ""
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if _SIGNATURE_START_RE.fullmatch(line) or _QUOTED_HEADER_RE.match(line):
            break
        if not line or _CONTACT_LINE_RE.match(line) or _CID_OR_IMAGE_RE.match(line):
            continue
        cleaned = _URL_RE.sub(" ", _EMAIL_RE.sub(" ", line))
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:")
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _sentences_with_keywords(sentences: list[str], keywords: tuple[str, ...]) -> list[str]:
    matches = [sentence for sentence in sentences if _contains(sentence, keywords)]
    return _unique_short(matches)


def _find_all(patterns: list[str], text: str) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(match.group(0).strip() for match in re.finditer(pattern, text, re.IGNORECASE))
    return matches


def _contains(value: str, keywords: tuple[str, ...]) -> bool:
    lower = value.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def _unique_short(items: list[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = re.sub(r"\s+", " ", item).strip(" ,.;:")
        if not cleaned:
            continue
        if len(cleaned) > MAX_FACT_LENGTH:
            cleaned = cleaned[:MAX_FACT_LENGTH].rstrip()
        key = cleaned.lower()
        if key not in seen:
            values.append(cleaned)
            seen.add(key)
        if len(values) >= MAX_FACT_ITEMS:
            break
    return values
