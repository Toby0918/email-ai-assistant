"""Construct bounded attachment facts from explicit business cues."""

from __future__ import annotations

import re

from .attachment_fact_safety import (
    MAX_ATTACHMENT_FACT_CHARACTERS,
    MAX_ATTACHMENT_FACTS,
    bounded_attachment_source,
    sanitize_constructed_fact,
    valid_business_identifier,
)
from .attachment_fact_context import is_reversed_fact_match, local_fact_segment
MAX_CANDIDATES_PER_CATEGORY = 3

_SEPARATOR = r"\s*(?:[:#=|\-]\s*|\s+)"
_IDENTIFIER_VALUE = r"(?=[A-Z0-9._/-]{4,64}\b)(?=[A-Z0-9._/-]*\d)[A-Z0-9][A-Z0-9._/-]{3,63}"
_IDENTIFIER = re.compile(
    rf"\b(?P<label>request\s+for\s+quotation|rfq|purchase\s+order|p\.?\s*o\.?|"
    rf"order|invoice|tracking(?:\s+(?:number|no\.?))?|reference|ref)"
    rf"(?:\s*(?:number|no\.?|#|id))?{_SEPARATOR}(?P<value>{_IDENTIFIER_VALUE})",
    re.IGNORECASE,
)
_PREFIXED_IDENTIFIER = re.compile(
    r"\b(?P<value>(?:RFQ|PO|INV|QUOTE|PART|ITEM|TRACK)[-_/.]"
    r"(?=[A-Z0-9._/-]{2,60}\b)(?=[A-Z0-9._/-]*\d)[A-Z0-9._/-]+)",
    re.IGNORECASE,
)
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
    r"\s*(?:[:=|\-]\s*)?(?P<body>[^\n.!?;]{1,160})",
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
    values: list[str] = []
    for match in _IDENTIFIER.finditer(text):
        label = _identifier_label(match.group("label"))
        value = match.group("value").rstrip("._/-")
        if not valid_business_identifier(value):
            continue
        separator = text[match.end("label"):match.start("value")]
        if label == "Reference":
            identifier = value
        elif "-" in separator and not value.upper().startswith(f"{label.upper()}-"):
            identifier = f"{label}-{value}"
        else:
            identifier = f"{label} {value}"
        duplicate = any(existing.lower().endswith(value.lower()) for existing in values)
        if not duplicate:
            _append(values, f"Reference: {identifier}")
    for match in _PREFIXED_IDENTIFIER.finditer(text):
        value = match.group("value").rstrip("._/-")
        duplicate = any(existing.lower().endswith(value.lower()) for existing in values)
        if valid_business_identifier(value) and not duplicate:
            _append(values, f"Reference: {value}")
    return values[:MAX_CANDIDATES_PER_CATEGORY]


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
        if is_reversed_fact_match(text, match):
            continue
        body = match.group("body")
        verb = _mapped_match(body, _ACTION_VERBS)
        target = _mapped_match(body, _ACTION_OBJECTS)
        if verb and target:
            _append(values, f"Requested action: {verb} {target}")
    return values[:MAX_CANDIDATES_PER_CATEGORY]


def _quality_issues(text: str) -> list[str]:
    values: list[str] = []
    for pattern, label in _QUALITY_SIGNALS:
        for match in pattern.finditer(text):
            if is_reversed_fact_match(text, match):
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


def _identifier_label(value: str) -> str:
    normalized = re.sub(r"[^a-z]", "", value.lower())
    if normalized in {"rfq", "requestforquotation"}:
        return "RFQ"
    if normalized in {"po", "purchaseorder"}:
        return "PO"
    if normalized == "invoice":
        return "Invoice"
    if normalized.startswith("tracking"):
        return "Tracking"
    if normalized == "order":
        return "Order"
    return "Reference"


def _mapped_match(
    text: str,
    mappings: tuple[tuple[re.Pattern[str], str], ...],
) -> str:
    for pattern, label in mappings:
        if pattern.search(text):
            return label
    return ""


def _specific_quality_signal(segment: str) -> bool:
    return any(
        label != "quality_issue" and pattern.search(segment)
        for pattern, label in _QUALITY_SIGNALS
    )


def _append(values: list[str], value: str) -> None:
    cleaned = sanitize_constructed_fact(value)
    if cleaned and cleaned not in values and len(values) < MAX_ATTACHMENT_FACTS:
        values.append(cleaned)
