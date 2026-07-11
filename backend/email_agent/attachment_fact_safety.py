"""Validation for bounded facts constructed from untrusted attachment text."""

from __future__ import annotations

import re


MAX_ATTACHMENT_FACTS = 5
MAX_ATTACHMENT_FACT_CHARACTERS = 240

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_NUMBER = r"(?:\d{1,3}(?:,\d{3}){1,3}|\d{1,9})(?:\.\d{1,4})?(?![\d.,-])"
_QUANTITY_UNIT = r"(?:pcs?|pieces?|units?|sets?|kg|g|lbs?)"
_MEASUREMENT_UNIT = r"(?:mm|cm|m|in(?:ch(?:es)?)?|ft)"
_CURRENCY = r"(?:USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD|\$|€|£|¥)"
_DATE_VALUE = (
    r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?|today|tomorrow)"
)
_PREFIXED_IDENTIFIER = re.compile(
    r"(?:RFQ|PO|INV|QUOTE|PART|ITEM|TRACK)[-_/.]"
    r"(?=[A-Z0-9._/-]{2,60}$)(?=[A-Z0-9._/-]*\d)[A-Z0-9._/-]+",
    re.IGNORECASE,
)
_PREFIXED_VALUE = re.compile(
    r"^(?:RFQ|PO|INV|QUOTE|PART|ITEM|TRACK)[-_](?P<core>[A-Z0-9][A-Z0-9_-]{2,31})$",
    re.IGNORECASE,
)
_REPEATED_PREFIX = re.compile(
    r"^(?:RFQ|PO|INV|QUOTE|PART|ITEM|TRACK)[-_]",
    re.IGNORECASE,
)
_FORBIDDEN_IDENTIFIER_CHARACTERS = re.compile(r"[./\\@:]", re.IGNORECASE)
_SEPARATED_PHONE = re.compile(r"(?:^|[^\d])\d{3}[-_]\d{4}(?:$|[^\d])")
_CONSTRUCTED_FACTS = (
    re.compile(rf"Quantity: {_NUMBER}(?:\s*{_QUANTITY_UNIT})?", re.IGNORECASE),
    re.compile(
        rf"Measurement: {_NUMBER}(?:\s*[x×]\s*{_NUMBER})?\s*{_MEASUREMENT_UNIT}",
        re.IGNORECASE,
    ),
    re.compile(rf"Amount: (?:(?:{_CURRENCY})\s*)?{_NUMBER}", re.IGNORECASE),
    re.compile(
        rf"Deadline: (?:due\s+{_DATE_VALUE}|by\s+{_DATE_VALUE}|"
        r"within\s+\d{1,3}\s+(?:hours?|days?|weeks?))",
        re.IGNORECASE,
    ),
    re.compile(
        r"Requested action: (?:investigate|confirm|provide|review|resolve) "
        r"(?:quality issue|quotation|quantity|delivery schedule|invoice/payment|order|"
        r"shipment status|specification|samples)",
        re.IGNORECASE,
    ),
    re.compile(
        r"Quality issue: (?:out_of_tolerance|surface_damage|physical_damage|burrs|"
        r"leakage|missing_component|inspection_failure|quality_issue)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:Image dimensions: \d{1,6} x \d{1,6}\.|Size: \d{1,12} bytes\.)",
        re.IGNORECASE,
    ),
)


def sanitize_constructed_fact(value: object) -> str:
    """Accept only exact constructed schemas; never sanitize arbitrary prose into a fact."""
    normalized = re.sub(
        r"\s+",
        " ",
        _CONTROL_CHARACTERS.sub("", str(value or "")),
    ).strip()[:MAX_ATTACHMENT_FACT_CHARACTERS]
    if normalized.startswith("Reference: "):
        identifier = normalized.removeprefix("Reference: ")
        return normalized if _valid_constructed_identifier(identifier) else ""
    return normalized if any(pattern.fullmatch(normalized) for pattern in _CONSTRUCTED_FACTS) else ""


def valid_business_identifier(value: str) -> bool:
    """Reject phone/card/account shapes while allowing bounded explicit business IDs."""
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{3,63}", value, re.IGNORECASE):
        return False
    if _FORBIDDEN_IDENTIFIER_CHARACTERS.search(value):
        return False
    prefixed = _PREFIXED_VALUE.fullmatch(value)
    core = prefixed.group("core") if prefixed else value
    if prefixed and _REPEATED_PREFIX.match(core):
        return False
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{3,31}", core, re.IGNORECASE):
        return False
    digit_count = sum(character.isdigit() for character in core)
    if not 1 <= digit_count <= 9 or _SEPARATED_PHONE.search(core):
        return False
    has_letter = any(character.isalpha() for character in core)
    if not has_letter and digit_count < 4:
        return False
    return True


def bounded_attachment_source(value: object) -> str:
    """Keep a bounded in-memory source only for strict component extraction."""
    return _CONTROL_CHARACTERS.sub("", str(value or ""))[:2_000]


def _valid_constructed_identifier(identifier: str) -> bool:
    labeled = re.fullmatch(
        r"(?:RFQ|PO|Order|Invoice|Tracking) (?P<value>[A-Z0-9][A-Z0-9._/-]{3,63})",
        identifier,
        re.IGNORECASE,
    )
    if labeled:
        return valid_business_identifier(labeled.group("value"))
    return bool(
        _PREFIXED_IDENTIFIER.fullmatch(identifier)
        and valid_business_identifier(identifier)
    )
