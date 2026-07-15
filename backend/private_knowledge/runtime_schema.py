"""Authority-free immutable schema exposed to the normal read-only runtime."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .entity_patterns import PLACEHOLDER
from .errors import PrivateKnowledgeError
from .residual_scanner import scan_residuals
from .schema import (
    ACCOUNTABILITIES,
    ACTION_TYPES,
    CATEGORIES,
    DIRECTIONS,
    LANGUAGES,
    PRIORITIES,
    RISK_TYPES,
    RULE_TYPES,
    SIGNALS,
    KnowledgeCardV1,
)


_FIELDS = {
    "schema_version", "card_id", "version", "rule_type", "language",
    "applicability", "generic_rule", "normalized_signals", "enum_mapping",
    "safe_reply_guidance",
}


@dataclass(frozen=True, slots=True)
class RuntimeKnowledgeCard:
    schema_version: str
    card_id: str
    version: int
    rule_type: str
    language: str
    applicability: tuple[str, str, tuple[str, ...]]
    generic_rule: str
    normalized_signals: tuple[str, ...]
    enum_mapping: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]
    safe_reply_guidance: str

    @classmethod
    def from_authority(cls, card: KnowledgeCardV1) -> RuntimeKnowledgeCard:
        if not isinstance(card, KnowledgeCardV1):
            raise PrivateKnowledgeError("snapshot_schema_invalid")
        accountability, direction, categories = card.applicability
        priorities, mapped_categories, risks, actions = card.enum_mapping
        return cls(
            "RuntimeKnowledgeCardV1", card.card_id, card.version, card.rule_type,
            card.language, (accountability, direction, categories), card.generic_rule,
            card.normalized_signals,
            (priorities, mapped_categories, risks, actions), card.safe_reply_guidance,
        )

    @classmethod
    def from_mapping(cls, value: object) -> RuntimeKnowledgeCard:
        if not isinstance(value, dict) or set(value) != _FIELDS:
            raise PrivateKnowledgeError("snapshot_schema_invalid")
        applicability = _mapping(value["applicability"], {"accountability", "direction", "categories"})
        enums = _mapping(value["enum_mapping"], {"priorities", "categories", "risks", "actions"})
        return cls(
            _equal(value["schema_version"], "RuntimeKnowledgeCardV1"),
            _uuid4(value["card_id"]), _positive_int(value["version"]),
            _enum(value["rule_type"], RULE_TYPES), _enum(value["language"], LANGUAGES),
            (_enum(applicability["accountability"], ACCOUNTABILITIES),
             _enum(applicability["direction"], DIRECTIONS),
             _enum_tuple(applicability["categories"], CATEGORIES, 9)),
            _text(value["generic_rule"]),
            _enum_tuple(value["normalized_signals"], SIGNALS, 12),
            (_enum_tuple(enums["priorities"], PRIORITIES, 4),
             _enum_tuple(enums["categories"], CATEGORIES, 9),
             _enum_tuple(enums["risks"], RISK_TYPES, 7),
             _enum_tuple(enums["actions"], ACTION_TYPES, 8)),
            _text(value["safe_reply_guidance"]),
        )

    def to_mapping(self) -> dict[str, object]:
        accountability, direction, categories = self.applicability
        priorities, mapped_categories, risks, actions = self.enum_mapping
        return {
            "schema_version": self.schema_version, "card_id": self.card_id,
            "version": self.version, "rule_type": self.rule_type,
            "language": self.language,
            "applicability": {"accountability": accountability, "direction": direction,
                              "categories": list(categories)},
            "generic_rule": self.generic_rule,
            "normalized_signals": list(self.normalized_signals),
            "enum_mapping": {"priorities": list(priorities),
                             "categories": list(mapped_categories),
                             "risks": list(risks), "actions": list(actions)},
            "safe_reply_guidance": self.safe_reply_guidance,
        }


def _mapping(value: object, fields: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    return value


def _enum_tuple(value: object, allowed: set[str], maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    result = tuple(_enum(item, allowed) for item in value)
    if len(result) != len(set(result)):
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    return result


def _enum(value: object, allowed: set[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    return value


def _text(value: object) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 1_000
            or PLACEHOLDER.search(value) or scan_residuals(value)):
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    return value


def _positive_int(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    return value


def _uuid4(value: object) -> str:
    if not isinstance(value, str):
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise PrivateKnowledgeError("snapshot_schema_invalid") from None
    if str(parsed) != value or parsed.version != 4:
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    return value


def _equal(value: object, expected: str) -> str:
    if value != expected:
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    return expected
