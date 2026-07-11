"""Full-field parsing and validation for attachment business identifiers."""

from __future__ import annotations

from dataclasses import dataclass
import re


MAX_REFERENCE_FACTS = 3
_LABEL_SOURCE = (
    r"request\s+for\s+quotation|rfq|purchase\s+order|p\.?\s*o\.?|"
    r"order|invoice|tracking(?:\s+(?:number|no\.?))?|reference|ref"
)
_FIELD = re.compile(
    rf"^(?P<label>{_LABEL_SOURCE})(?:\s*(?:number|no\.?|#|id))?"
    r"(?:\s*[:#=]\s*|\s+)"
    r"(?P<value>[A-Z0-9_-]{4,64})\s*[.,;!?]?\s*$",
    re.IGNORECASE,
)
_LABEL_ONLY = re.compile(
    rf"^(?P<label>{_LABEL_SOURCE})(?:\s*(?:number|no\.?|#|id))?\s*$",
    re.IGNORECASE,
)
_MIXED_CORE = re.compile(r"[A-Z0-9]+(?:[-_][A-Z0-9]+)*", re.IGNORECASE)
_PREFIX_TO_LABEL = {
    "RFQ": "RFQ",
    "QUOTE": "RFQ",
    "PO": "PO",
    "INV": "Invoice",
    "TRACK": "Tracking",
    "TRK": "Tracking",
    "ORDER": "Order",
    "ORD": "Order",
    "PART": "Reference",
    "ITEM": "Reference",
}
_PREFIXES = tuple(sorted(_PREFIX_TO_LABEL, key=len, reverse=True))


@dataclass(frozen=True)
class ParsedIdentifier:
    fact: str
    identity: tuple[str, str]


def extract_reference_facts(text: str) -> list[str]:
    """Return reference facts only from complete field-shaped segments."""
    facts: list[str] = []
    identities: set[tuple[str, str]] = set()
    for segment in _field_segments(text):
        match = _FIELD.fullmatch(segment)
        if not match:
            continue
        parsed = _parse_identifier(match.group("label"), match.group("value"))
        if not parsed or parsed.identity in identities:
            continue
        identities.add(parsed.identity)
        facts.append(parsed.fact)
        if len(facts) >= MAX_REFERENCE_FACTS:
            break
    return facts


def valid_constructed_reference(identifier: str) -> bool:
    """Validate the value following the constructed ``Reference:`` prefix."""
    labeled = re.fullmatch(
        r"(?P<label>RFQ|PO|Order|Invoice|Tracking) "
        r"(?P<value>[A-Z0-9_-]{4,64})",
        identifier,
        re.IGNORECASE,
    )
    if labeled:
        return _parse_identifier(labeled.group("label"), labeled.group("value")) is not None
    return _parse_identifier("Reference", identifier) is not None


def _field_segments(text: str) -> list[str]:
    segments: list[str] = []
    blocks = re.split(r"[\r\n]+|(?<=[.!?])\s+", text)
    for block in blocks:
        if "|" not in block:
            if block.strip():
                segments.append(block.strip())
            continue
        cells = [cell.strip() for cell in block.split("|") if cell.strip()]
        if len(cells) != 2:
            continue
        label = _LABEL_ONLY.fullmatch(cells[0])
        if label:
            segments.append(f"{label.group('label')}: {cells[1]}")
    return segments


def _parse_identifier(raw_label: str, raw_value: str) -> ParsedIdentifier | None:
    label = _canonical_label(raw_label)
    value = raw_value.strip()
    prefix, core, malformed = _recognized_prefix(value)
    if malformed:
        return None
    if prefix:
        prefix_label = _PREFIX_TO_LABEL[prefix]
        if label != "Reference" and prefix_label != label:
            return None
        canonical_label = prefix_label if label == "Reference" else label
    else:
        core = value
        canonical_label = label
    if not _valid_core(core):
        return None
    display = value if label == "Reference" else f"{label} {value}"
    return ParsedIdentifier(
        fact=f"Reference: {display}",
        identity=(canonical_label.casefold(), core.upper()),
    )


def _recognized_prefix(value: str) -> tuple[str, str, bool]:
    upper = value.upper()
    for prefix in _PREFIXES:
        if not upper.startswith(prefix):
            continue
        rest = value[len(prefix):]
        if rest.startswith(("-", "_")):
            core = rest[1:]
        elif rest.isdigit():
            core = rest
        else:
            if any(rest.upper().startswith(other) for other in _PREFIXES):
                return "", "", True
            continue
        if not core or any(core.upper().startswith(other) for other in _PREFIXES):
            return "", "", True
        return prefix, core, False
    return "", value, False


def _valid_core(value: str) -> bool:
    if re.fullmatch(r"\d{4,9}", value):
        return True
    if not 4 <= len(value) <= 32 or not _MIXED_CORE.fullmatch(value):
        return False
    digit_count = sum(character.isdigit() for character in value)
    return (
        1 <= digit_count <= 9
        and any(character.isalpha() for character in value)
    )


def _canonical_label(value: str) -> str:
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
