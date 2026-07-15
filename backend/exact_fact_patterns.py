"""Canonical exact business-identifier and calendar-date recognition."""

from __future__ import annotations

import re
from collections.abc import Iterator


_ID_VALUE = (
    r"(?=[A-Z0-9._/-]{1,64}(?![\w./-]))(?=[A-Z0-9._/-]*\d)"
    r"[A-Z0-9][A-Z0-9._/-]{0,63}(?![\w./-])"
)
_ALPHANUMERIC_ID_VALUE = (
    r"(?=[A-Z0-9._/-]{2,64}(?![\w./-]))(?=[A-Z0-9._/-]*\d)"
    r"(?=[A-Z0-9._/-]*[A-Z])[A-Z0-9][A-Z0-9._/-]{1,63}(?![\w./-])"
)
_ALPHANUMERIC_LONG_ID_VALUE = (
    r"(?=[A-Z0-9._/-]{4,64}(?![\w./-]))(?=[A-Z0-9._/-]*\d)"
    r"(?=[A-Z0-9._/-]*[A-Z])[A-Z0-9][A-Z0-9._/-]{3,63}(?![\w./-])"
)
_NUMERIC_LONG_ID_VALUE = r"\d{4,64}(?![\w/-]|\.\d)"
_NUMERIC_ID_VALUE = r"\d{1,64}(?![\w/-]|\.\d)"
_ID_WORD = r"(?:number|no\.?|id|ref(?:erence)?\.?)"
_STRONG_ID_SEPARATOR = r"[:\uff1a#/_=\-]"
_AMBIGUOUS_ID_SEPARATOR = r"[.()]"
_ALL_ID_SEPARATORS = r"[:\uff1a#._/=\-()]"
_LABEL_END = r"(?![A-Za-z0-9])"
_COUNT_OR_SECTION_SUFFIX = (
    r"(?!\s+(?:samples?|items?|units?|pieces?|documents?|sections?|"
    r"parts?|copies?|lots?|sets?|pcs?|boxes?|kg|results?|of)\b)"
)


def _identifier_family(
    kind: str, short_labels: str, long_labels: str
) -> tuple[tuple[str, re.Pattern[str]], ...]:
    patterns: list[tuple[str, re.Pattern[str]]] = []
    if short_labels:
        patterns.extend(_compact_identifier_patterns(kind, short_labels))
        patterns.extend(_short_separated_identifier_patterns(kind, short_labels))
    if long_labels:
        patterns.extend(_long_identifier_patterns(kind, long_labels))
    return tuple(patterns)


def _short_separated_identifier_patterns(
    kind: str, labels: str
) -> tuple[tuple[str, re.Pattern[str]], ...]:
    prefix = rf"(?<!\w)(?P<label>{labels}){_LABEL_END}"
    keyword = (
        rf"(?:\s+{_ID_WORD}\s*{_ALL_ID_SEPARATORS}*\s*|"
        rf"\s*{_ALL_ID_SEPARATORS}+\s*{_ID_WORD}\s*"
        rf"{_ALL_ID_SEPARATORS}*\s*)"
    )
    expressions = (
        prefix + keyword + rf"(?P<value>{_ID_VALUE})\)?",
        prefix + rf"\s*{_STRONG_ID_SEPARATOR}+\s*(?P<value>{_ID_VALUE})",
        prefix + rf"\s*{_AMBIGUOUS_ID_SEPARATOR}+\s*"
        rf"(?P<value>{_ALPHANUMERIC_ID_VALUE})\)?",
        prefix + rf"\s*{_AMBIGUOUS_ID_SEPARATOR}+\s*"
        rf"{_STRONG_ID_SEPARATOR}*\s*(?P<value>{_NUMERIC_LONG_ID_VALUE})\)?"
        + _COUNT_OR_SECTION_SUFFIX,
        prefix + rf"\s+(?P<value>{_ALPHANUMERIC_ID_VALUE})",
        prefix + rf"\s+(?P<value>{_NUMERIC_ID_VALUE})"
        + _COUNT_OR_SECTION_SUFFIX,
    )
    return tuple(
        (kind, re.compile(expression, re.IGNORECASE))
        for expression in expressions
    )


def _long_identifier_patterns(
    kind: str, labels: str
) -> tuple[tuple[str, re.Pattern[str]], ...]:
    prefix = rf"(?<!\w)(?P<label>{labels}){_LABEL_END}"
    keyword = (
        rf"(?:\s+{_ID_WORD}\s*{_ALL_ID_SEPARATORS}*\s*|"
        rf"\s*{_ALL_ID_SEPARATORS}+\s*{_ID_WORD}\s*"
        rf"{_ALL_ID_SEPARATORS}*\s*)"
    )
    expressions = (
        prefix + keyword + rf"(?P<value>{_ID_VALUE})\)?",
        prefix + rf"\s*{_STRONG_ID_SEPARATOR}+\s*(?P<value>{_ID_VALUE})",
        prefix + rf"\s*{_AMBIGUOUS_ID_SEPARATOR}+\s*"
        rf"(?P<value>{_ALPHANUMERIC_ID_VALUE})\)?",
        prefix + rf"\s*{_AMBIGUOUS_ID_SEPARATOR}+\s*"
        rf"{_STRONG_ID_SEPARATOR}*\s*(?P<value>{_NUMERIC_LONG_ID_VALUE})\)?"
        + _COUNT_OR_SECTION_SUFFIX,
        prefix + rf"\s+(?P<value>{_ALPHANUMERIC_LONG_ID_VALUE})",
        prefix + rf"\s+(?P<value>{_NUMERIC_LONG_ID_VALUE})"
        + _COUNT_OR_SECTION_SUFFIX,
    )
    return tuple(
        (kind, re.compile(expression, re.IGNORECASE))
        for expression in expressions
    )


def _compact_identifier_patterns(
    kind: str, short_labels: str
) -> tuple[tuple[str, re.Pattern[str]], ...]:
    numeric = re.compile(
        rf"(?<!\w)(?P<label>{short_labels})"
        rf"(?P<value>\d[A-Z0-9._/-]{{0,63}})(?![\w./-])",
        re.IGNORECASE,
    )
    uppercase_alphanumeric = re.compile(
        rf"(?<!\w)(?P<label>(?i:{short_labels}))"
        rf"(?P<value>(?=[A-Z0-9._/-]{{2,64}}(?![\w./-]))"
        rf"(?=[A-Z0-9._/-]*\d)[A-Z][A-Z0-9._/-]{{1,63}})"
        rf"(?![\w./-])"
    )
    return ((kind, numeric), (kind, uppercase_alphanumeric))


def _chinese_identifier(kind: str, labels: str) -> tuple[str, re.Pattern[str]]:
    return (
        kind,
        re.compile(
            rf"(?P<label>{labels})\s*{_ALL_ID_SEPARATORS}*\s*"
            rf"(?P<value>{_ID_VALUE})",
            re.IGNORECASE,
        ),
    )


EXACT_IDENTIFIER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    *_identifier_family("ORDER_ID", "PO", "order"),
    *_identifier_family("INVOICE_ID", "INV", "invoice"),
    *_identifier_family("PART_ID", "PN", "part"),
    *_identifier_family("TRACKING_ID", "TRK", "tracking"),
    *_identifier_family("TRANSACTION_ID", "RFQ|TXN", "contract|transaction"),
    _chinese_identifier("ORDER_ID", "\u91c7\u8d2d\u8ba2\u5355|\u91c7\u8d2d\u5355\u53f7?|\u8ba2\u5355\u53f7"),
    _chinese_identifier("INVOICE_ID", "\u53d1\u7968\u53f7"),
    _chinese_identifier("PART_ID", "\u96f6\u4ef6\u53f7|\u90e8\u4ef6\u53f7"),
    _chinese_identifier("TRACKING_ID", "\u8ffd\u8e2a\u53f7|\u8ddf\u8e2a\u53f7"),
    _chinese_identifier("TRANSACTION_ID", "\u5408\u540c\u53f7|\u4ea4\u6613\u53f7|\u8be2\u4ef7\u5355\u53f7"),
)

_ISO_TIME_SUFFIX = (
    r"(?:[Tt](?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,9})?)?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?)?"
)
_MONTH = (
    r"(?:Jan(?:uary|\.)?|Feb(?:ruary|\.)?|Mar(?:ch|\.)?|"
    r"Apr(?:il|\.)?|May\.?|Jun(?:e|\.)?|Jul(?:y|\.)?|"
    r"Aug(?:ust|\.)?|Sep(?:tember|t\.?|\.)?|Oct(?:ober|\.)?|"
    r"Nov(?:ember|\.)?|Dec(?:ember|\.)?)"
)
_NAME_DATE_SEPARATOR = r"(?:\s+|-)"
_NAME_DATE_YEAR_SEPARATOR = r"(?:,\s*|\s+|-)"
_DATED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ymd",
        re.compile(
            r"(?<!\d)(?P<year>(?:19|20)\d{2})[-/.]"
            r"(?P<month>0?[1-9]|1[0-2])[-/.](?P<day>0?[1-9]|[12]\d|3[01])"
            rf"{_ISO_TIME_SUFFIX}(?!\d)", re.IGNORECASE,
        ),
    ),
    (
        "year_last",
        re.compile(
            r"(?<!\d)(?P<first>0?[1-9]|[12]\d|3[01])[-/.]"
            r"(?P<second>0?[1-9]|[12]\d|3[01])[-/.]"
            r"(?P<year>(?:19|20)\d{2})(?!\d)"
        ),
    ),
    (
        "chinese",
        re.compile(
            r"(?<!\d)(?P<year>(?:19|20)\d{2})\u5e74"
            r"(?P<month>0?[1-9]|1[0-2])\u6708"
            r"(?P<day>0?[1-9]|[12]\d|3[01])(?:\u65e5|\u53f7)(?!\d)"
        ),
    ),
    (
        "month_first",
        re.compile(
            rf"(?<![A-Za-z])(?P<month_name>{_MONTH}){_NAME_DATE_SEPARATOR}"
            r"(?P<day>0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
            rf"{_NAME_DATE_YEAR_SEPARATOR}"
            r"(?P<year>(?:19|20)\d{2})(?!\d)", re.IGNORECASE,
        ),
    ),
    (
        "day_first",
        re.compile(
            rf"(?<!\d)(?P<day>0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
            rf"{_NAME_DATE_SEPARATOR}(?P<month_name>{_MONTH})"
            rf"{_NAME_DATE_YEAR_SEPARATOR}"
            r"(?P<year>(?:19|20)\d{2})(?!\d)", re.IGNORECASE,
        ),
    ),
)
EXACT_DATE_PATTERNS = tuple(pattern for _style, pattern in _DATED_PATTERNS)

_MONTH_NUMBERS = {
    name: index
    for index, names in enumerate((
        (), ("jan", "january"), ("feb", "february"), ("mar", "march"),
        ("apr", "april"), ("may",), ("jun", "june"), ("jul", "july"),
        ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"),
        ("nov", "november"), ("dec", "december"),
    ))
    for name in names
}


def iter_exact_identifiers(text: str) -> Iterator[tuple[str, str]]:
    for _kind, pattern in EXACT_IDENTIFIER_PATTERNS:
        for match in pattern.finditer(text):
            yield match.group("label"), match.group("value")


def iter_exact_date_signatures(text: str) -> Iterator[str]:
    for style, pattern in _DATED_PATTERNS:
        for match in pattern.finditer(text):
            yield _date_signature(style, match)


def _date_signature(style: str, match: re.Match[str]) -> str:
    year = int(match.group("year"))
    if style in {"ymd", "chinese"}:
        month, day = int(match.group("month")), int(match.group("day"))
    elif style in {"month_first", "day_first"}:
        month = _MONTH_NUMBERS[match.group("month_name").casefold().rstrip(".")]
        day = int(match.group("day"))
    else:
        first, second = int(match.group("first")), int(match.group("second"))
        if first > 12:
            month, day = second, first
        elif second > 12:
            month, day = first, second
        else:
            return f"ambiguous:{year:04d}:{first:02d}:{second:02d}"
    return f"{year:04d}-{month:02d}-{day:02d}"
