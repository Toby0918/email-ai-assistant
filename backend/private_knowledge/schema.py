"""Strict, identifier-free KnowledgeCardV1 authority schema."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .entity_patterns import PLACEHOLDER
from .errors import PrivateKnowledgeError
from .residual_scanner import scan_residuals


PRIORITIES = {"urgent", "high", "normal", "low"}
CATEGORIES = {
    "customer_inquiry", "order_followup", "payment", "contract", "complaint",
    "new_product_development", "internal", "marketing", "unknown",
}
RISK_TYPES = {
    "payment_risk", "delivery_risk", "contract_risk", "quality_risk",
    "security_risk", "commitment_risk", "prompt_injection_risk",
}
ACTION_TYPES = {
    "reply", "confirm", "prepare_quote", "check_inventory", "check_delivery",
    "escalate", "wait", "ignore",
}
RULE_TYPES = {"classification", "priority", "risk", "action", "reply_guidance"}
LANGUAGES = {"zh-CN", "en"}
ACCOUNTABILITIES = {"general", "price", "payment", "contract", "quality", "legal"}
DIRECTIONS = {"any", "inbound", "outbound", "thread"}
SIGNALS = {
    "quote_request", "delivery_status", "payment_terms", "contract_language",
    "quality_issue", "security_instruction", "reply_requested", "deadline_signal",
    "inventory_request", "product_specification", "complaint_signal",
}
CONVERSATION_BUCKETS = {"1", "2", "3-5", "6-10", "11+"}
COUNTERPARTY_BUCKETS = {"1", "2-3", "4-10", "11+"}
LIFECYCLE_STATUSES = {"candidate", "approved", "deprecated", "revoked"}

_CARD_FIELDS = {
    "schema_version", "card_id", "version", "rule_type", "language",
    "applicability", "generic_rule", "normalized_signals", "enum_mapping",
    "safe_reply_guidance", "evidence", "privacy_check", "review", "lifecycle",
}
_PROFILE = re.compile(r"(?i)\b(?:customer|employee|counterparty)\s+profile\b|客户画像|员工画像")


@dataclass(frozen=True, slots=True)
class Approval:
    actor_ref: str
    role: str
    approved_at: str
    card_version: int


@dataclass(frozen=True, slots=True)
class KnowledgeCardV1:
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
    evidence: tuple[str, str]
    privacy_check: tuple[str, str]
    review: tuple[Approval, Approval | None, Approval | None, Approval | None]
    lifecycle: tuple[str, str, str, str | None]

    @classmethod
    def from_mapping(cls, value: object) -> KnowledgeCardV1:
        mapping = _exact_mapping(value, _CARD_FIELDS)
        applicability = _parse_applicability(mapping["applicability"])
        enum_mapping = _parse_enum_mapping(mapping["enum_mapping"])
        privacy = _parse_privacy(mapping["privacy_check"])
        review = _parse_review(mapping["review"], mapping["version"])
        lifecycle = _parse_lifecycle(mapping["lifecycle"])
        generic_rule = _safe_text(mapping["generic_rule"], 1_000)
        guidance = _safe_text(mapping["safe_reply_guidance"], 1_000)
        return cls(
            _equal(mapping["schema_version"], "KnowledgeCardV1"),
            _uuid(mapping["card_id"]),
            _positive_int(mapping["version"]),
            _enum(mapping["rule_type"], RULE_TYPES),
            _enum(mapping["language"], LANGUAGES),
            applicability,
            generic_rule,
            _enum_tuple(mapping["normalized_signals"], SIGNALS, 12),
            enum_mapping,
            guidance,
            _parse_evidence(mapping["evidence"]),
            privacy,
            review,
            lifecycle,
        )

    def to_mapping(self) -> dict[str, object]:
        accountability, direction, categories = self.applicability
        priorities, mapped_categories, risks, actions = self.enum_mapping
        creator, business, privacy, owner = self.review
        status, created_at, expires_at, review_due_at = self.lifecycle
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
            "evidence": {"conversation_bucket": self.evidence[0],
                         "counterparty_bucket": self.evidence[1]},
            "privacy_check": {"status": self.privacy_check[0],
                              "checked_at": self.privacy_check[1]},
            "review": {"creator": asdict(creator),
                       "business": _approval_mapping(business),
                       "privacy": _approval_mapping(privacy),
                       "owner": _approval_mapping(owner)},
            "lifecycle": {"status": status, "created_at": created_at,
                          "expires_at": expires_at, "review_due_at": review_due_at},
        }


def validate_non_verbatim(card_content: object, source_texts: object) -> None:
    content = "\n".join(_collect_strings(card_content))
    if not isinstance(source_texts, (list, tuple)) or not all(
        isinstance(item, str) for item in source_texts
    ):
        raise PrivateKnowledgeError("verbatim_input_invalid")
    for source in source_texts:
        if _shares_latin(content, source) or _shares_han(content, source):
            raise PrivateKnowledgeError("verbatim_overlap")
        normalized_content = re.sub(r"\s|[^\w一-鿿]", "", content.casefold())
        normalized_source = re.sub(r"\s|[^\w一-鿿]", "", source.casefold())
        if _has_shared_window(normalized_content, normalized_source, 24):
            raise PrivateKnowledgeError("verbatim_overlap")


def _parse_applicability(value: object) -> tuple[str, str, tuple[str, ...]]:
    item = _exact_mapping(value, {"accountability", "direction", "categories"})
    return (_enum(item["accountability"], ACCOUNTABILITIES),
            _enum(item["direction"], DIRECTIONS),
            _enum_tuple(item["categories"], CATEGORIES, 9))


def _parse_enum_mapping(value: object) -> tuple[tuple[str, ...], ...]:
    item = _exact_mapping(value, {"priorities", "categories", "risks", "actions"})
    return (_enum_tuple(item["priorities"], PRIORITIES, 4),
            _enum_tuple(item["categories"], CATEGORIES, 9),
            _enum_tuple(item["risks"], RISK_TYPES, 7),
            _enum_tuple(item["actions"], ACTION_TYPES, 8))


def _parse_evidence(value: object) -> tuple[str, str]:
    item = _exact_mapping(value, {"conversation_bucket", "counterparty_bucket"})
    return (_enum(item["conversation_bucket"], CONVERSATION_BUCKETS),
            _enum(item["counterparty_bucket"], COUNTERPARTY_BUCKETS))


def _parse_privacy(value: object) -> tuple[str, str]:
    item = _exact_mapping(value, {"status", "checked_at"})
    return (_equal(item["status"], "passed"), _timestamp(item["checked_at"]))


def _parse_review(value: object, version: object) -> tuple[Approval, Approval | None, Approval | None, Approval | None]:
    item = _exact_mapping(value, {"creator", "business", "privacy", "owner"})
    parsed_version = _positive_int(version)
    creator = _approval(item["creator"], "creator", parsed_version)
    return (creator, _optional_approval(item["business"], "business", parsed_version),
            _optional_approval(item["privacy"], "privacy_security", parsed_version),
            _optional_approval(item["owner"], "accountable_owner", parsed_version))


def _parse_lifecycle(value: object) -> tuple[str, str, str, str | None]:
    item = _exact_mapping(value, {"status", "created_at", "expires_at", "review_due_at"})
    due = item["review_due_at"]
    if due is not None:
        due = _timestamp(due)
    return (_enum(item["status"], LIFECYCLE_STATUSES), _timestamp(item["created_at"]),
            _timestamp(item["expires_at"]), due)


def _approval(value: object, role: str, version: int) -> Approval:
    item = _exact_mapping(value, {"actor_ref", "role", "approved_at", "card_version"})
    actor = item["actor_ref"]
    if not isinstance(actor, str) or re.fullmatch(r"actor-[a-z0-9-]{3,80}", actor) is None:
        raise PrivateKnowledgeError("schema_invalid")
    return Approval(actor, _equal(item["role"], role), _timestamp(item["approved_at"]),
                    _equal(item["card_version"], version))


def _optional_approval(value: object, role: str, version: int) -> Approval | None:
    return None if value is None else _approval(value, role, version)


def _safe_text(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise PrivateKnowledgeError("schema_invalid")
    if PLACEHOLDER.search(value) or _PROFILE.search(value) or scan_residuals(value):
        raise PrivateKnowledgeError("forbidden_content")
    return value.strip()


def _exact_mapping(value: object, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise PrivateKnowledgeError("schema_invalid")
    return value


def _enum_tuple(value: object, allowed: set[str], maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise PrivateKnowledgeError("schema_invalid")
    result = tuple(_enum(item, allowed) for item in value)
    if len(set(result)) != len(result):
        raise PrivateKnowledgeError("schema_invalid")
    return result


def _enum(value: object, allowed: set[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise PrivateKnowledgeError("schema_invalid")
    return value


def _equal(value: object, expected: Any) -> Any:
    if type(value) is not type(expected) or value != expected:
        raise PrivateKnowledgeError("schema_invalid")
    return value


def _positive_int(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise PrivateKnowledgeError("schema_invalid")
    return value


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise PrivateKnowledgeError("schema_invalid")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise PrivateKnowledgeError("schema_invalid") from None
    if str(parsed) != value or parsed.version != 4:
        raise PrivateKnowledgeError("schema_invalid")
    return value


def _timestamp(value: object) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PrivateKnowledgeError("schema_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise PrivateKnowledgeError("schema_invalid") from None
    if parsed.utcoffset() is None or parsed.microsecond:
        raise PrivateKnowledgeError("schema_invalid")
    return value


def _approval_mapping(value: Approval | None) -> dict[str, object] | None:
    return None if value is None else asdict(value)


def _collect_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _collect_strings(item)]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in _collect_strings(item)]
    return []


def _shares_latin(left: str, right: str) -> bool:
    left_words = re.findall(r"[a-z0-9]+", left.casefold())
    right_text = " ".join(re.findall(r"[a-z0-9]+", right.casefold()))
    return any(" ".join(left_words[index:index + 6]) in right_text
               for index in range(max(0, len(left_words) - 5)))


def _shares_han(left: str, right: str) -> bool:
    left_han = "".join(re.findall(r"[一-鿿]", left))
    right_han = "".join(re.findall(r"[一-鿿]", right))
    return _has_shared_window(left_han, right_han, 12)


def _has_shared_window(left: str, right: str, size: int) -> bool:
    if len(left) < size or len(right) < size:
        return False
    return any(left[index:index + size] in right for index in range(len(left) - size + 1))
