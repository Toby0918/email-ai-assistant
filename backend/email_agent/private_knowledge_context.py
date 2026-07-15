"""Deterministic identifier-free rendering of verified runtime knowledge cards."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from backend.private_knowledge.runtime_schema import RuntimeKnowledgeCard


MAX_KNOWLEDGE_CARDS = 8
MAX_KNOWLEDGE_CHARACTERS = 4_000


@dataclass(frozen=True, slots=True)
class RenderedKnowledgeContext:
    text: str = field(repr=False)
    card_count: int


def render_private_knowledge_context(
    cards: tuple[object, ...],
    rule_result: object,
) -> RenderedKnowledgeContext:
    """Return stable whole-card JSON lines without identifiers or envelope metadata."""
    if type(cards) is not tuple or not isinstance(rule_result, dict):
        return RenderedKnowledgeContext("", 0)
    verified = _revalidate_cards(cards)
    if verified is None:
        return RenderedKnowledgeContext("", 0)
    signals = _rule_signals(rule_result)
    ranked = sorted(
        (
            (_relevance(card, signals), card.card_id, card)
            for card in verified
        ),
        key=lambda item: (-item[0], item[1]),
    )
    payloads = tuple(
        _render_card(card) for score, _card_id, card in ranked if score > 0
    )
    text, count = _join_whole_card_payloads(
        payloads,
        MAX_KNOWLEDGE_CHARACTERS,
        MAX_KNOWLEDGE_CARDS,
    )
    return RenderedKnowledgeContext(text, count)


def _revalidate_cards(
    cards: tuple[object, ...],
) -> tuple[RuntimeKnowledgeCard, ...] | None:
    result: list[RuntimeKnowledgeCard] = []
    try:
        for card in cards:
            if not isinstance(card, RuntimeKnowledgeCard):
                return None
            result.append(RuntimeKnowledgeCard.from_mapping(card.to_mapping()))
    except Exception:
        return None
    return tuple(result)


def _rule_signals(value: dict[str, Any]) -> tuple[str, str, frozenset[str], frozenset[str]]:
    category = value.get("category") if isinstance(value.get("category"), str) else ""
    priority = value.get("priority") if isinstance(value.get("priority"), str) else ""
    risks = _item_values(value.get("risk_flags"), "type")
    actions = _item_values(value.get("suggested_actions"), "type")
    return category, priority, risks, actions


def _item_values(value: object, field_name: str) -> frozenset[str]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(
        item[field_name]
        for item in value
        if isinstance(item, dict) and isinstance(item.get(field_name), str)
    )


def _relevance(
    card: RuntimeKnowledgeCard,
    signals: tuple[str, str, frozenset[str], frozenset[str]],
) -> int:
    category, priority, risks, actions = signals
    _accountability, _direction, applicable_categories = card.applicability
    priorities, mapped_categories, mapped_risks, mapped_actions = card.enum_mapping
    return sum(
        (
            category in applicable_categories or category in mapped_categories,
            priority in priorities,
            bool(risks.intersection(mapped_risks)),
            bool(actions.intersection(mapped_actions)),
        )
    )


def _render_card(card: RuntimeKnowledgeCard) -> str:
    accountability, direction, categories = card.applicability
    payload = {
        "applicability": {
            "accountability": accountability,
            "categories": list(categories),
            "direction": direction,
        },
        "generic_rule": card.generic_rule,
        "language": card.language,
        "normalized_signals": list(card.normalized_signals),
        "rule_type": card.rule_type,
        "safe_reply_guidance": card.safe_reply_guidance,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _join_whole_card_payloads(
    payloads: tuple[str, ...],
    maximum_characters: int,
    maximum_cards: int = MAX_KNOWLEDGE_CARDS,
) -> tuple[str, int]:
    parts: list[str] = []
    for payload in payloads:
        if len(parts) >= maximum_cards:
            break
        candidate = "\n".join((*parts, payload))
        if len(candidate) <= maximum_characters:
            parts.append(payload)
    return "\n".join(parts), len(parts)
