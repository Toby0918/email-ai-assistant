"""Bounded deterministic deadline hints for thread request atoms."""

from __future__ import annotations

import re


_RELATIVE_DATE_RE = re.compile(
    r"\d{1,2}月\d{1,2}日(?:前)?|(?:周[一二三四五六日天]|明天)(?:前)?"
)
_ISO_DATE_RE = re.compile(r"(?<!\d)20\d{2}[-/]\d{1,2}[-/]\d{1,2}(?!\d)")
_TIME_SUFFIX_RE = re.compile(
    r"\s+(?P<time>(?:[01]?\d|2[0-3]):[0-5]\d)"
    r"(?:\s+(?P<zone>[A-Za-z][A-Za-z0-9_+:/-]*))?"
)
_DEADLINE_CUE_BEFORE_RE = re.compile(
    r"(?:\b(?:by|before|deadline|due(?:\s+date)?|no\s+later\s+than|until)\b|"
    r"截止(?:日期)?|最晚|请于)\s*(?:is|on|at|为|[:：=-])?\s*$",
    re.IGNORECASE,
)
_DEADLINE_CUE_AFTER_RE = re.compile(r"\s*(?:前|之前|为止|截止)")
_UTC_GMT_OFFSET_RE = re.compile(
    r"(?:UTC|GMT)(?P<sign>[+-])(?P<hour>\d{1,2})(?::?(?P<minute>\d{2}))?",
    re.IGNORECASE,
)
_IANA_ZONE_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9._+-]*/[A-Za-z][A-Za-z0-9._+-]*"
    r"(?:/[A-Za-z][A-Za-z0-9._+-]*)*"
)
_KNOWN_TIMEZONE_ABBREVIATIONS = {
    "UTC", "GMT", "EST", "EDT", "CST", "CDT", "MST", "MDT", "PST", "PDT",
    "CET", "CEST", "EET", "EEST", "BST", "JST", "HKT", "SGT", "AEST", "AEDT",
}


def deadline_date_hints(text: str) -> list[str]:
    """Return ISO date/time values only when the surrounding text marks a deadline."""
    hints: list[str] = []
    for match in _ISO_DATE_RE.finditer(text):
        value, value_end = _date_value(text, match)
        prefix = text[max(0, match.start() - 64):match.start()]
        has_cue = bool(_DEADLINE_CUE_BEFORE_RE.search(prefix))
        has_cue = has_cue or bool(_DEADLINE_CUE_AFTER_RE.match(text[value_end:]))
        if has_cue and value not in hints:
            hints.append(value)
    return hints


def unambiguous_due_hint(text: str) -> str:
    relative_hints = [match.group(0) for match in _RELATIVE_DATE_RE.finditer(text)]
    hints = tuple(dict.fromkeys([*relative_hints, *deadline_date_hints(text)]))
    return hints[0] if len(hints) == 1 else ""


def _date_value(text: str, match: re.Match[str]) -> tuple[str, int]:
    value = match.group(0)
    value_end = match.end()
    suffix = _TIME_SUFFIX_RE.match(text[value_end:])
    if suffix is None:
        return value, value_end
    value = f"{value} {suffix.group('time')}"
    value_end += suffix.end("time")
    zone = suffix.group("zone")
    if zone and _valid_timezone(zone):
        value = f"{value} {zone}"
        value_end = match.end() + suffix.end("zone")
    return value, value_end


def _valid_timezone(value: str) -> bool:
    if value.upper() in _KNOWN_TIMEZONE_ABBREVIATIONS:
        return True
    offset = _UTC_GMT_OFFSET_RE.fullmatch(value)
    if offset is not None:
        hour = int(offset.group("hour"))
        minute = int(offset.group("minute") or "0")
        return hour <= 14 and minute < 60 and (hour < 14 or minute == 0)
    return _IANA_ZONE_RE.fullmatch(value) is not None
