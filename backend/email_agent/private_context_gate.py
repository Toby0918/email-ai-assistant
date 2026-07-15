"""Local-only deidentification gate for remote DeepSeek user content."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email.utils import getaddresses
from enum import Enum

from backend.private_knowledge.deidentifier import deidentify_private_text
from backend.private_knowledge.entity_patterns import PATTERNS, PLACEHOLDER
from backend.private_knowledge.residual_scanner import scan_residuals

from .analysis_budget import PROVIDER_MAX_SECONDS
from .private_knowledge_context import render_private_knowledge_context


MAX_HEADER_VALUES = 17
MAX_HEADER_CHARACTERS = 320
_RESERVED_CONTROL_LABELS = (
    "UNTRUSTED_EMAIL", "UNTRUSTED_THREAD", "UNTRUSTED_ATTACHMENT",
    "UNTRUSTED_ATTACHMENT_METADATA",
)
_RESTORATION_PATTERNS = tuple(
    pattern for kind, pattern in PATTERNS if kind == "RESTORATION_HINT"
)
_PRIVATE_OUTPUT_MARKER = re.compile(
    r"(?i)\b(?:private_context|knowledge_cards?|placeholder_mapping|resolver|"
    r"card_id|snapshot_id|vault_id|reidentif(?:y|ication)|deanonymi[sz]e)\b"
)


class PrivateContextFallbackCode(Enum):
    SAFETY = "safety"
    BUDGET = "budget"


@dataclass(frozen=True, slots=True)
class PrivateModelRequest:
    prompt: str = field(repr=False)
    header_values: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class PrivateModelContext:
    text: str = field(repr=False)
    selected_card_count: int


def build_private_model_context(
    request: PrivateModelRequest,
    rule_result: object,
    cards: tuple[object, ...],
    budget: object,
) -> PrivateModelContext | PrivateContextFallbackCode:
    """Return a plain deidentified prompt or a fixed content-free refusal code."""
    if _provider_budget(budget) is None:
        return PrivateContextFallbackCode.BUDGET
    if not isinstance(request, PrivateModelRequest) or not isinstance(request.prompt, str):
        return PrivateContextFallbackCode.SAFETY
    identity_context = _header_identity_context(request.header_values)
    if identity_context is None:
        return PrivateContextFallbackCode.SAFETY
    knowledge = render_private_knowledge_context(cards, rule_result)
    outbound = request.prompt
    if knowledge.text:
        outbound += "\n\napproved_knowledge_context\n" + knowledge.text
    try:
        with deidentify_private_text(outbound, identity_context) as deidentified:
            text = _normalize_reserved_labels(deidentified.text)
            if not isinstance(text, str) or scan_residuals(text):
                return PrivateContextFallbackCode.SAFETY
    except Exception:
        return PrivateContextFallbackCode.SAFETY
    return PrivateModelContext(text, knowledge.card_count)


def provider_output_is_private_safe(raw: object) -> bool:
    """Reject private-boundary artifacts before any DeepSeek parser sees them."""
    if type(raw) is not str:
        return False
    if PLACEHOLDER.search(raw) or _PRIVATE_OUTPUT_MARKER.search(raw):
        return False
    return not any(pattern.search(raw) for pattern in _RESTORATION_PATTERNS)


def _provider_budget(budget: object) -> float | None:
    try:
        timeout = budget.provider_timeout_seconds(PROVIDER_MAX_SECONDS)
    except Exception:
        return None
    return timeout if isinstance(timeout, (int, float)) else None


def _header_identity_context(values: object) -> dict[str, list[str]] | None:
    if type(values) is not tuple or len(values) > MAX_HEADER_VALUES:
        return None
    if any(
        not isinstance(value, str)
        or len(value) > MAX_HEADER_CHARACTERS
        or "\r" in value
        or "\n" in value
        for value in values
    ):
        return None
    try:
        names = {
            name.strip()
            for name, _address in getaddresses(list(values))
            if 1 <= len(name.strip()) <= 200
        }
    except Exception:
        return None
    return {"people": sorted(names), "organizations": []}


def _normalize_reserved_labels(text: str) -> str:
    for label in _RESERVED_CONTROL_LABELS:
        text = text.replace(label, label.lower())
    return text
