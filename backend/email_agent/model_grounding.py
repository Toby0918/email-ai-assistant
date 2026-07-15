"""Validate critical model claims against request-local evidence sources."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from backend.exact_fact_patterns import (
    iter_exact_date_signatures,
    iter_exact_identifiers,
)

from .deepseek_analysis_schema import APPROVED_EVIDENCE_PATTERNS
from .model_text_safety import passive_commitment_categories
from .prompt_context import EvidenceSource

_INVALID_SOURCE_REASON = "Evidence source is invalid."
_UNGROUNDED_REASON = "Critical model text is not grounded."
_UNAVAILABLE_ATTACHMENT_REASON = "Attachment evidence is unavailable."
_AMOUNT_RE = re.compile(
    r"(?:(?P<prefix>USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD|[$€¥£])\s*"
    r"(?P<prefix_value>\d[\d,]*(?:\.\d+)?)|(?P<suffix_value>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<suffix>USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD))",
    re.IGNORECASE,
)
_RELATIVE_DEADLINE_RE = re.compile(
    r"\b(today|tomorrow|eod|end\s+of\s+day|this\s+week|next\s+week|"
    r"within\s+\d+\s+(?:days?|hours?)|by\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b|"
    r"今天|明天|本周|下周|今日|明日|\d+\s*(?:天|小时)内|周[一二三四五六日天]前",
    re.IGNORECASE,
)
_QUANTITY_RE = re.compile(
    r"\b(?:qty|quantity)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(pcs?|units?)?\b|"
    r"数量\s*[:：=]?\s*(\d+(?:\.\d+)?)\s*(件|个|套)?",
    re.IGNORECASE,
)
_UNIT_QUANTITY_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(pcs?|units?)\b", re.IGNORECASE)
_MEASUREMENT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|in|inch(?:es)?)\b",
    re.IGNORECASE,
)
_SINGLE_MEASUREMENT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(kg|mg|g|mm|cm|km|m|in|inch(?:es)?|ml|l)\b",
    re.IGNORECASE,
)
_OUTCOME_RE = re.compile(
    r"\b(completed|resolved|closed|sent|delivered|finished)\b|"
    r"已?完成|已?解决|已?关闭|已发送|已交付",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(
    r"\b(not|never|no|without|isn't|aren't|wasn't|weren't|hasn't|haven't)\b|"
    r"尚未|未|没有|并未|不",
    re.IGNORECASE,
)
_CLAUSE_RE = re.compile(r"[^;；.!?。！？\n]+")
_ACTOR_RE = re.compile(r"\b(?:i|we)\b|我方|我们|我", re.IGNORECASE)
_SAFE_ACTION_PREFIX_RE = re.compile(
    r"\b(?:review|check|verify)\b(?:\s+(?:the|this|current))?\s*$|"
    r"(?:审核|检查|核实|复核)(?:一下|本次|当前|该)?\s*$",
    re.IGNORECASE,
)
_COMMITMENT_ACTION_RE = re.compile(
    r"\b(?:accept|confirm|guarantee|commit|agree|deliver|pay)\b|接受|确认|保证|承诺|同意|交付|付款|支付",
    re.IGNORECASE,
)
_COMMITMENT_TERMS = {
    "price": re.compile(r"\b(price|quote|quotation|cost|discount)\b|价格|报价|折扣", re.I),
    "delivery": re.compile(r"\b(deliver|delivery|shipment|dispatch|eta)\b|交付|交期|发货", re.I),
    "payment": re.compile(r"\b(pay|payment|invoice)\b|付款|支付|发票", re.I),
    "contract": re.compile(r"\b(contract|terms?)\b|合同|条款", re.I),
    "quality": re.compile(r"\b(quality|warranty|specification)\b|质量|保修|规格", re.I),
    "legal": re.compile(r"\b(legal|liability|liable|indemnity)\b|法律|责任|赔偿", re.I),
}
_CURRENCY_NAMES = {"$": "usd", "€": "eur", "¥": "cny", "£": "gbp"}


@dataclass(frozen=True, slots=True)
class GroundingViolation:
    pointer: str
    reason: str


def find_grounding_violations(
    envelope: object,
    evidence: Mapping[str, Sequence[str]],
    sources: Mapping[str, EvidenceSource],
) -> tuple[GroundingViolation, ...]:
    """Return one generic deterministic violation for each unsafe text leaf."""
    leaves = dict(_approved_text_leaves(envelope))
    violations: dict[str, GroundingViolation] = {}
    for pointer, claimed in evidence.items():
        if any(source_id not in sources for source_id in claimed):
            violations[pointer] = GroundingViolation(pointer, _INVALID_SOURCE_REASON)
    for pointer, text in leaves.items():
        signatures = _critical_signatures(text)
        claimed = tuple(evidence.get(pointer, ()))
        if pointer in violations:
            continue
        if signatures and not claimed:
            violations[pointer] = GroundingViolation(pointer, _UNGROUNDED_REASON)
            continue
        attachment = _attachment_owner_for_pointer(envelope, pointer)
        if attachment is not None:
            owner_id, object_evidence = attachment
            owner = sources.get(owner_id)
            if owner_id not in claimed or owner_id not in object_evidence:
                violations[pointer] = GroundingViolation(pointer, _UNGROUNDED_REASON)
                continue
            if owner is None:
                violations[pointer] = GroundingViolation(pointer, _INVALID_SOURCE_REASON)
                continue
            if owner.kind != "attachment" or not owner.parsed:
                violations[pointer] = GroundingViolation(pointer, _UNAVAILABLE_ATTACHMENT_REASON)
                continue
        for source_id in claimed:
            source = sources.get(source_id)
            if source is None:
                break
            if signatures and source.kind == "attachment" and not source.parsed:
                violations[pointer] = GroundingViolation(
                    pointer, _UNAVAILABLE_ATTACHMENT_REASON
                )
                break
            if signatures and not signatures.issubset(
                _critical_signatures(source.grounding_text)
            ):
                violations[pointer] = GroundingViolation(pointer, _UNGROUNDED_REASON)
                break
    return tuple(violations[pointer] for pointer in sorted(violations))


def _approved_text_leaves(
    value: object,
    tokens: tuple[str, ...] = (),
    pattern: tuple[str, ...] = (),
):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _approved_text_leaves(child, (*tokens, str(key)), (*pattern, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _approved_text_leaves(child, (*tokens, str(index)), (*pattern, "*"))
    elif isinstance(value, str) and pattern in APPROVED_EVIDENCE_PATTERNS:
        yield _pointer(tokens), value


def _pointer(tokens: tuple[str, ...]) -> str:
    return "/" + "/".join(token.replace("~", "~0").replace("/", "~1") for token in tokens)


def _attachment_owner_for_pointer(
    envelope: object, pointer: str
) -> tuple[str, tuple[str, ...]] | None:
    if not pointer.startswith("/attachment_augmentations/") or not isinstance(envelope, dict):
        return None
    tokens = pointer.split("/")
    try:
        item = envelope["attachment_augmentations"][int(tokens[2])]
        source_id = item["source_id"]
        evidence_sources = item["evidence_sources"]
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    if not isinstance(source_id, str) or not isinstance(evidence_sources, list):
        return None
    return source_id, tuple(value for value in evidence_sources if isinstance(value, str))


def _critical_signatures(text: str) -> frozenset[str]:
    signatures: set[str] = set()
    for label, value in iter_exact_identifiers(text):
        signatures.add(f"id:{_identifier_label(label)}:{_compact(value)}")
    for match in _AMOUNT_RE.finditer(text):
        currency = match.group("prefix") or match.group("suffix")
        value = match.group("prefix_value") or match.group("suffix_value")
        signatures.add(f"amount:{_currency(currency)}:{_number(value)}")
    signatures.update(
        "date:" + value for value in iter_exact_date_signatures(text)
    )
    signatures.update(
        "deadline:" + _compact(match.group(0))
        for match in _RELATIVE_DEADLINE_RE.finditer(text)
    )
    for match in _QUANTITY_RE.finditer(text):
        value = match.group(1) or match.group(3)
        unit = match.group(2) or match.group(4) or ""
        signatures.add(f"quantity:{_number(value)}:{_unit(unit)}")
    for value, unit in _UNIT_QUANTITY_RE.findall(text):
        signatures.add(f"quantity:{_number(value)}:{_unit(unit)}")
    for first, second, unit in _MEASUREMENT_RE.findall(text):
        signatures.add(f"measurement:{_number(first)}x{_number(second)}:{_unit(unit)}")
    for value, unit in _SINGLE_MEASUREMENT_RE.findall(text):
        signatures.add(f"measurement:{_number(value)}:{_unit(unit)}")
    signatures.update(_outcome_signatures(text))
    signatures.update(_commitment_signatures(text))
    return frozenset(signatures)


def _outcome_signatures(text: str) -> set[str]:
    signatures: set[str] = set()
    for match in _OUTCOME_RE.finditer(text):
        prefix = re.split(r"[;；,.，。!?！？\n]", text[:match.start()])[-1]
        polarity = "negative" if _NEGATION_RE.search(prefix) else "positive"
        signatures.add(f"outcome:{_outcome_category(match.group(0))}:{polarity}")
    return signatures


def _commitment_signatures(text: str) -> set[str]:
    signatures = {
        "commitment:" + category for category in passive_commitment_categories(text)
    }
    for clause in _CLAUSE_RE.findall(text):
        actor = _ACTOR_RE.search(clause)
        if actor is None:
            continue
        for action in _COMMITMENT_ACTION_RE.finditer(clause, actor.end()):
            if _SAFE_ACTION_PREFIX_RE.search(clause[actor.end():action.start()]):
                continue
            tail = clause[action.start():]
            signatures.update(
                "commitment:" + name
                for name, pattern in _COMMITMENT_TERMS.items()
                if pattern.search(tail)
            )
    return signatures


def _compact(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w]", "", normalized)


def _number(value: str) -> str:
    normalized = value.replace(",", "").lstrip("0") or "0"
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _currency(value: str) -> str:
    normalized = _CURRENCY_NAMES.get(value, value.casefold())
    return "cny" if normalized == "rmb" else normalized


def _unit(value: str) -> str:
    normalized = _compact(value)
    aliases = {
        "pc": "pcs", "piece": "pcs", "pieces": "pcs", "unit": "units",
        "inch": "in", "inches": "in",
    }
    return aliases.get(normalized, normalized)


def _identifier_label(value: str) -> str:
    normalized = _compact(value)
    aliases = {
        "po": "po", "order": "po", "ordernumber": "po", "采购订单": "po", "订单号": "po",
        "rfq": "rfq", "invoice": "invoice", "inv": "invoice", "发票号": "invoice",
        "part": "part", "partnumber": "part", "pn": "part", "零件号": "part",
        "tracking": "tracking", "trackingnumber": "tracking", "追踪号": "tracking",
        "contract": "contract", "contractnumber": "contract", "合同号": "contract",
    }
    return aliases.get(normalized, normalized)


def _outcome_category(value: str) -> str:
    normalized = _compact(value)
    for category, markers in (
        ("delivered", ("deliver", "交付")), ("sent", ("sent", "发送")),
        ("closed", ("closed", "关闭")), ("resolved", ("resolved", "解决")),
    ):
        if any(marker in normalized for marker in markers):
            return category
    return "completed"
