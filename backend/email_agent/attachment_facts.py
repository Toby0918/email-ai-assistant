"""Construct bounded attachment facts from explicit business cues."""

from __future__ import annotations

import re

from .attachment_fact_safety import (
    MAX_ATTACHMENT_FACT_CHARACTERS,
    MAX_ATTACHMENT_FACTS,
    bounded_attachment_source,
    sanitize_constructed_fact,
)
from .attachment_fact_context import (
    action_clause_spans,
    is_adjacent_absence_match,
    is_cancelled_action_span,
    is_reversed_fact_match,
    is_reversed_fact_span,
    local_fact_segment,
)
from .attachment_identifiers import extract_reference_facts
MAX_CANDIDATES_PER_CATEGORY = 3

_SEPARATOR = r"\s*(?:[:#=|\-]\s*|\s+)"
_NUMBER = r"(?:\d{1,3}(?:,\d{3}){1,3}|\d{1,9})(?:\.\d{1,4})?(?![\d.,-])"
_QUANTITY_UNIT = r"(?:pcs?|pieces?|units?|sets?|kg|g|lbs?)"
_LABELED_QUANTITY = re.compile(
    rf"\b(?:quantity|qty){_SEPARATOR}(?P<value>{_NUMBER}(?:\s*{_QUANTITY_UNIT})?)\b",
    re.IGNORECASE,
)
_UNIT_QUANTITY = re.compile(
    rf"\b(?P<value>{_NUMBER}\s*{_QUANTITY_UNIT})\b",
    re.IGNORECASE,
)
_MEASUREMENT_UNIT = r"(?:mm|cm|m|in(?:ch(?:es)?)?|ft)"
_DIMENSION = re.compile(
    rf"\b(?P<value>{_NUMBER}\s*[x×]\s*{_NUMBER}\s*{_MEASUREMENT_UNIT})\b",
    re.IGNORECASE,
)
_LABELED_MEASUREMENT = re.compile(
    rf"\b(?:dimension(?:s)?|measurement(?:s)?|size){_SEPARATOR}"
    rf"(?P<value>{_NUMBER}(?:\s*[x×]\s*{_NUMBER})?\s*{_MEASUREMENT_UNIT})\b",
    re.IGNORECASE,
)
_SINGLE_MEASUREMENT = re.compile(
    rf"\b(?P<value>{_NUMBER}\s*{_MEASUREMENT_UNIT})\b",
    re.IGNORECASE,
)
_CURRENCY = r"(?:USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD|\$|€|£|¥)"
_CURRENCY_AMOUNT = re.compile(
    rf"(?<!\w)(?P<currency>{_CURRENCY})\s*(?P<amount>{_NUMBER})\b|"
    rf"\b(?P<amount_after>{_NUMBER})\s*(?P<currency_after>{_CURRENCY})(?!\w)",
    re.IGNORECASE,
)
_LABELED_AMOUNT = re.compile(
    rf"\b(?:total\s+cost|unit\s+cost|cost|amount|price|total){_SEPARATOR}"
    rf"(?:(?P<currency>{_CURRENCY})\s*)?(?P<amount>{_NUMBER})\b",
    re.IGNORECASE,
)
_DATE_VALUE = (
    r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?|today|tomorrow)"
)
_RELATIVE_DEADLINE = re.compile(
    r"\b(?P<value>within\s+\d{1,3}\s+(?:hours?|days?|weeks?))\b",
    re.IGNORECASE,
)
_LABELED_DEADLINE = re.compile(
    rf"\b(?P<cue>due(?:\s+date)?|deadline|required\s+by|deliver(?:y)?\s+by|"
    rf"ship\s+by|complete\s+by|respond\s+by){_SEPARATOR}(?P<value>{_DATE_VALUE})\b",
    re.IGNORECASE,
)
_BY_DEADLINE = re.compile(rf"\bby\s+(?P<value>{_DATE_VALUE})\b", re.IGNORECASE)
_REQUEST_SPAN = re.compile(
    r"\b(?:please|kindly|action\s+required|requested\s+action|could\s+you|can\s+you)"
    r"\s*(?:[:=|\-]\s*)?(?P<body>[^\n.!?]{1,160})",
    re.IGNORECASE,
)

_ACTION_VERBS = (
    (re.compile(r"\binvestigate\b", re.IGNORECASE), "investigate"),
    (re.compile(r"\bconfirm\b", re.IGNORECASE), "confirm"),
    (re.compile(r"\b(?:provide|send|submit|share)\b", re.IGNORECASE), "provide"),
    (re.compile(r"\b(?:review|check|verify)\b", re.IGNORECASE), "review"),
    (re.compile(r"\b(?:replace|rework|refund)\b", re.IGNORECASE), "resolve"),
    (re.compile(r"\b(?:ship|deliver)\b", re.IGNORECASE), "confirm"),
)
_ACTION_OBJECTS = (
    (re.compile(r"\b(?:damaged?|surface|quality|defects?|scratch(?:ed)?)\b", re.IGNORECASE), "quality issue"),
    (re.compile(r"\b(?:quotation|quote|pricing|price)\b", re.IGNORECASE), "quotation"),
    (re.compile(r"\b(?:quantity|qty)\b", re.IGNORECASE), "quantity"),
    (re.compile(r"\b(?:delivery|schedule|deadline)\b", re.IGNORECASE), "delivery schedule"),
    (re.compile(r"\b(?:invoice|payment)\b", re.IGNORECASE), "invoice/payment"),
    (re.compile(r"\b(?:order|purchase\s+order|po)\b", re.IGNORECASE), "order"),
    (re.compile(r"\b(?:tracking|shipment)\b", re.IGNORECASE), "shipment status"),
    (re.compile(r"\b(?:drawing|specification|spec)\b", re.IGNORECASE), "specification"),
    (re.compile(r"\b(?:sample|samples)\b", re.IGNORECASE), "samples"),
)
_OBJECT_ONLY_PREFIX = re.compile(r"\s*(?:the\s+)?$", re.IGNORECASE)
_QUALITY_SIGNALS = (
    (re.compile(r"\b(?:out\s+of|outside)\s+tolerance\b", re.IGNORECASE), "out_of_tolerance"),
    (re.compile(r"\b(?:scratch(?:ed|es)?|scuff(?:ed|s)?|surface\s+damage)\b", re.IGNORECASE), "surface_damage"),
    (re.compile(r"\b(?:crack(?:ed|s)?|broken|dent(?:ed|s)?|damaged?)\b", re.IGNORECASE), "physical_damage"),
    (re.compile(r"\bburrs?\b", re.IGNORECASE), "burrs"),
    (re.compile(r"\b(?:leak(?:ing|age)?|leaks?)\b", re.IGNORECASE), "leakage"),
    (re.compile(r"\bmissing\s+(?:part|parts|component|components)\b", re.IGNORECASE), "missing_component"),
    (re.compile(r"\b(?:failed\s+inspection|inspection\s+failure)\b", re.IGNORECASE), "inspection_failure"),
    (re.compile(r"\b(?:quality\s+issue|defect(?:ive)?|complaint)\b", re.IGNORECASE), "quality_issue"),
)


def extract_attachment_facts(
    text: str,
    metadata_facts: list[str] | None = None,
) -> list[str]:
    """Return diverse constructed facts; never return arbitrary source prose."""
    bounded_raw = bounded_attachment_source(text)
    groups = [
        _references(bounded_raw),
        _quantities(bounded_raw),
        _measurements(bounded_raw),
        _amounts(bounded_raw),
        _deadlines(bounded_raw),
        _requested_actions(bounded_raw),
        _quality_issues(bounded_raw),
    ]
    facts: list[str] = []
    remainders: list[list[str]] = []
    for group in groups:
        if group:
            _append(facts, group[0])
            remainders.append(group[1:])
    for group in remainders:
        for fact in group:
            _append(facts, fact)
            if len(facts) >= MAX_ATTACHMENT_FACTS:
                return facts
    for fact in metadata_facts or []:
        _append(facts, fact)
    return facts


def _references(text: str) -> list[str]:
    return extract_reference_facts(text)[:MAX_CANDIDATES_PER_CATEGORY]


def _quantities(text: str) -> list[str]:
    return _matched_values(text, (_LABELED_QUANTITY, _UNIT_QUANTITY), "Quantity")


def _measurements(text: str) -> list[str]:
    return _matched_values(
        text,
        (_LABELED_MEASUREMENT, _DIMENSION, _SINGLE_MEASUREMENT),
        "Measurement",
    )


def _amounts(text: str) -> list[str]:
    values: list[str] = []
    for match in _CURRENCY_AMOUNT.finditer(text):
        currency = match.group("currency") or match.group("currency_after")
        amount = match.group("amount") or match.group("amount_after")
        _append(values, f"Amount: {currency.upper()} {amount}")
    for match in _LABELED_AMOUNT.finditer(text):
        currency = match.group("currency")
        prefix = f"{currency.upper()} " if currency else ""
        _append(values, f"Amount: {prefix}{match.group('amount')}")
    return values[:MAX_CANDIDATES_PER_CATEGORY]


def _deadlines(text: str) -> list[str]:
    values: list[str] = []
    for match in _RELATIVE_DEADLINE.finditer(text):
        if is_reversed_fact_match(text, match):
            continue
        _append(values, f"Deadline: {match.group('value').lower()}")
    for match in _LABELED_DEADLINE.finditer(text):
        if is_reversed_fact_match(text, match):
            continue
        _append(values, f"Deadline: due {match.group('value')}")
    for match in _BY_DEADLINE.finditer(text):
        if is_reversed_fact_match(text, match):
            continue
        _append(values, f"Deadline: by {match.group('value')}")
    return values[:MAX_CANDIDATES_PER_CATEGORY]


def _requested_actions(text: str) -> list[str]:
    values: list[str] = []
    for match in _REQUEST_SPAN.finditer(text):
        body = match.group("body")
        pending_verb = ""
        for start, end, may_inherit in action_clause_spans(body, 0, len(body)):
            pending_verb = _append_clause_actions(
                values,
                body[start:end],
                pending_verb if may_inherit else "",
            )
    return values[:MAX_CANDIDATES_PER_CATEGORY]


def _quality_issues(text: str) -> list[str]:
    values: list[str] = []
    for pattern, label in _QUALITY_SIGNALS:
        for match in pattern.finditer(text):
            if (
                is_reversed_fact_match(text, match)
                or is_adjacent_absence_match(text, match)
            ):
                continue
            if label == "quality_issue" and _specific_quality_signal(local_fact_segment(text, match)):
                continue
            _append(values, f"Quality issue: {label}")
    return values[:MAX_CANDIDATES_PER_CATEGORY]


def _matched_values(
    text: str,
    patterns: tuple[re.Pattern[str], ...],
    label: str,
) -> list[str]:
    values: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            _append(values, f"{label}: {match.group('value')}")
    return values[:MAX_CANDIDATES_PER_CATEGORY]


def _mapped_candidates(
    text: str,
    mappings: tuple[tuple[re.Pattern[str], str], ...],
) -> list[tuple[str, re.Match[str]]]:
    candidates: list[tuple[int, str, re.Match[str]]] = []
    for pattern, label in mappings:
        for match in pattern.finditer(text):
            candidates.append((match.start(), label, match))
    return [
        (label, match)
        for _start, label, match in sorted(candidates, key=lambda item: item[0])
    ]


def _append_clause_actions(
    values: list[str],
    clause: str,
    inherited_verb: str,
) -> str:
    verbs = _mapped_candidates(clause, _ACTION_VERBS)
    safe_verbs = [
        (label, match)
        for label, match in verbs
        if not is_reversed_fact_span(clause, match.start(), match.end())
        and not is_cancelled_action_span(clause, match.start(), match.end())
    ]
    paired = False
    for target, target_match in _mapped_candidates(clause, _ACTION_OBJECTS):
        if is_reversed_fact_span(clause, target_match.start(), target_match.end()):
            continue
        preceding = [
            label
            for label, verb_match in safe_verbs
            if verb_match.end() <= target_match.start()
        ]
        object_only = _OBJECT_ONLY_PREFIX.fullmatch(clause[:target_match.start()])
        verb = preceding[-1] if preceding else inherited_verb if object_only else ""
        if verb:
            _append(values, f"Requested action: {verb} {target}")
            paired = True
    if paired:
        return ""
    return safe_verbs[-1][0] if safe_verbs else ""


def _specific_quality_signal(segment: str) -> bool:
    return any(
        label != "quality_issue" and pattern.search(segment)
        for pattern, label in _QUALITY_SIGNALS
    )


def _append(values: list[str], value: str) -> None:
    cleaned = sanitize_constructed_fact(value)
    if cleaned and cleaned not in values and len(values) < MAX_ATTACHMENT_FACTS:
        values.append(cleaned)
