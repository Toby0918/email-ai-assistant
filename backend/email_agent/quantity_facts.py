from __future__ import annotations

import re
from dataclasses import dataclass


_LABEL = (
    r"(?:MOQ|minimum\s+order\s+(?:qty|quantity)|最低起订量|最低订购量)"
)
_VALUE = r"[1-9]\d{0,8}(?:,\d{3})*"
_UNIT = r"(?:pc|pcs|piece|pieces|unit|units|set|sets|件|个|套)"
_CONNECTOR = r"(?:is|are|为|是|[:=：])?"
_FACT_RE = re.compile(
    rf"(?<!\w)(?:best\s+)?(?P<label>{_LABEL})\s*"
    rf"{_CONNECTOR}\s*"
    rf"(?P<values>{_VALUE}(?:\s*/\s*{_VALUE}){{0,3}})\s*"
    rf"(?P<unit>{_UNIT})(?!\w)",
    re.IGNORECASE,
)
_CANDIDATE_RE = re.compile(
    rf"(?<!\w)(?:best\s+)?(?P<label>{_LABEL})\s*"
    rf"{_CONNECTOR}\s*"
    rf"(?P<values>{_VALUE}(?:\s*/\s*{_VALUE}){{0,3}})"
    rf"(?:\s+(?P<unit>[A-Za-z]+|[\u4e00-\u9fff]+))?(?!\w)",
    re.IGNORECASE,
)
_NON_FINAL_RE = re.compile(
    r"\b(?:pending|to\s+be\s+confirmed|not\s+final|unknown|"
    r"subject\s+to\s+confirmation)\b|待确认|未明确|未最终确认",
    re.IGNORECASE,
)
_DISALLOWED_CLAUSE_RE = re.compile(
    r"\b(?:price\s+table|quotation\s+table|best\s+regards|"
    r"kind\s+regards|original\s+message)\b|\|",
    re.IGNORECASE,
)
_CONTACT_FRAGMENT_RE = re.compile(
    r"\b(?:phone|mobile|tel|email|wechat|whatsapp|contact)\b\s*:?[ \t]*"
    r"(?:\+?[0-9][0-9() -]{6,}|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|"
    r"https?://\S+|www\.\S+)",
    re.IGNORECASE,
)
_CURRENCY_AMOUNT = (
    r"(?:\b(?:USD|EUR|GBP|CNY|RMB)\b\s*|[$\u20ac\u00a3]\s*)"
    r"\d{1,9}(?:[.,]\d{1,2})?"
)
_COMPACT_CURRENCY_AFTER_RE = re.compile(
    rf"^[ \t|,:-]*{_CURRENCY_AMOUNT}(?=$|[ \t|,;:.])",
    re.IGNORECASE,
)
_COMPACT_CURRENCY_BEFORE_RE = re.compile(
    rf"{_CURRENCY_AMOUNT}[ \t|,:-]*$",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b(?:19|20)\d{2}\s*/\s*\d{1,2}\s*/\s*\d{1,2}\b")
_RATIO_RE = re.compile(r"\bratio\b", re.IGNORECASE)
_CLAUSE_BOUNDARY_RE = re.compile(r"[\n;；。]|\.(?=\s|$)")
_UNIT_MAP = {
    "pc": "pcs",
    "pcs": "pcs",
    "piece": "pcs",
    "pieces": "pcs",
    "件": "pcs",
    "个": "pcs",
    "unit": "units",
    "units": "units",
    "set": "sets",
    "sets": "sets",
    "套": "sets",
}


@dataclass(frozen=True, slots=True)
class LabeledQuantityFact:
    display: str
    signatures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LabeledQuantityOccurrence:
    fact: LabeledQuantityFact
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class LabeledQuantityCandidateOccurrence:
    fact: LabeledQuantityFact | None
    start: int
    end: int


def labeled_quantity_facts(text: object) -> tuple[LabeledQuantityFact, ...]:
    output: list[LabeledQuantityFact] = []
    for occurrence in labeled_quantity_occurrences(text):
        if occurrence.fact not in output:
            output.append(occurrence.fact)
    return tuple(output)


def labeled_quantity_occurrences(
    text: object,
) -> tuple[LabeledQuantityOccurrence, ...]:
    if not isinstance(text, str) or not text:
        return ()
    return tuple(_valid_labeled_quantity_occurrences(text))


def labeled_quantity_candidate_occurrences(
    text: object,
) -> tuple[LabeledQuantityCandidateOccurrence, ...]:
    if not isinstance(text, str) or not text:
        return ()
    valid_by_span = {
        (occurrence.start, occurrence.end): occurrence.fact
        for occurrence in labeled_quantity_occurrences(text)
    }
    return tuple(
        LabeledQuantityCandidateOccurrence(
            valid_by_span.get((match.start(), match.end())),
            match.start(),
            match.end(),
        )
        for match in _CANDIDATE_RE.finditer(text)
    )


def _valid_labeled_quantity_occurrences(
    text: str,
):
    for match in _FACT_RE.finditer(text):
        clause = _clause_containing(text, match.start(), match.end())
        if _is_disallowed_clause(clause) or _has_compact_currency_amount(
            text, match
        ):
            continue
        values = "/".join(
            part.replace(",", "")
            for part in re.split(r"\s*/\s*", match.group("values"))
        )
        unit = _canonical_unit(match.group("unit"))
        signatures = (
            f"quantity:moq:{values}",
            f"quantity:moq-unit:{values}:{unit}",
        )
        fact = LabeledQuantityFact(f"MOQ {values} {unit}", signatures)
        yield LabeledQuantityOccurrence(fact, match.start(), match.end())


def has_final_labeled_quantity_statement(text: object) -> bool:
    return bool(labeled_quantity_facts(text))


def _clause_containing(text: str, start: int, end: int) -> str:
    before = text[:start]
    after = text[end:]
    left_match = list(_CLAUSE_BOUNDARY_RE.finditer(before))
    left = left_match[-1].end() if left_match else 0
    right_match = _CLAUSE_BOUNDARY_RE.search(after)
    right = end + right_match.start() if right_match else len(text)
    return text[left:right]


def _is_disallowed_clause(clause: str) -> bool:
    return bool(
        _NON_FINAL_RE.search(clause)
        or _DISALLOWED_CLAUSE_RE.search(clause)
        or _CONTACT_FRAGMENT_RE.search(clause)
        or _DATE_RE.search(clause)
        or _RATIO_RE.search(clause)
    )


def _has_compact_currency_amount(text: str, match: re.Match[str]) -> bool:
    return bool(
        _COMPACT_CURRENCY_BEFORE_RE.search(text[: match.start()])
        or _COMPACT_CURRENCY_AFTER_RE.match(text[match.end() :])
    )


def _canonical_unit(unit: str) -> str:
    return _UNIT_MAP[unit.casefold()]
