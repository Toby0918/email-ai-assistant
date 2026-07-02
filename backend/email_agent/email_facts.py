"""Deterministic fact extraction for current-email analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass


MAX_FACT_ITEMS = 5
MAX_FACT_LENGTH = 140


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
    text = "\n".join(part for part in (subject, sender, clean_body) if part)
    sentences = _sentences(text)
    return EmailFacts(
        references=_find_references(text),
        quantities=_find_quantities(text),
        measurements=_find_measurements(text),
        deadlines=_find_deadlines(text),
        requested_actions=_find_requested_actions(sentences),
        quality_issues=_find_quality_issues(sentences),
    )


def _find_references(text: str) -> list[str]:
    refs: list[str] = []
    labelled = [
        (r"\bPO\s*(?:#|No\.?|number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9-]{4,})", "PO {}"),
        (r"\binvoice\s*(?:#|No\.?|number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9-]{4,})", "invoice {}"),
        (r"\btracking(?:\s+number)?\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{4,})", "tracking number {}"),
        (r"\bmaterial\s*(?:#|No\.?|number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9-]{4,})", "{}"),
        (r"\bbooking\s*(?:#|No\.?|number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9-]{4,})", "booking {}"),
    ]
    for pattern, template in labelled:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            refs.append(template.format(match.group(1)))
    refs.extend(re.findall(r"\b[A-Z]{1,6}\d{3,}[A-Z0-9-]*\b", text))
    refs.extend(re.findall(r"\b\d{6,}[A-Z0-9-]*\b", text))
    return _unique_short(refs)


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
    return _unique_short(_find_all(patterns, text))


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
    normalized = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", normalized)
    return [part.strip(" ;:") for part in parts if part.strip(" ;:")]


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
