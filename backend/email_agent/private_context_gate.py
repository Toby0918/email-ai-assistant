"""Local-only deidentification gate for remote DeepSeek user content."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from email.utils import getaddresses
from enum import Enum

from backend.private_knowledge.deidentifier import deidentify_private_text
from backend.private_knowledge.entity_patterns import PATTERNS, PLACEHOLDER
from backend.private_knowledge.residual_scanner import scan_residuals

from .analysis_budget import DEEPSEEK_PROVIDER_MAX_SECONDS
from .private_knowledge_context import render_private_knowledge_context
from .private_prompt_genericizer import genericize_private_prompt


MAX_HEADER_VALUES = 117
MAX_HEADER_CHARACTERS = 512
MAX_IDENTITY_NAMES = 100
MAX_PROVIDER_OUTPUT_CHARACTERS = 65_536
MAX_PROVIDER_OUTPUT_DEPTH = 32
MAX_PROVIDER_OUTPUT_ITEMS = 4_096
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
_PRIVATE_PLACEHOLDER = re.compile(PLACEHOLDER.pattern, re.IGNORECASE)
_HEADER_EMAIL = re.compile(r"(?i)[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}\Z")


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
    outbound = genericize_private_prompt(outbound, _PRIVATE_PLACEHOLDER)
    if outbound is None:
        return PrivateContextFallbackCode.SAFETY
    try:
        with deidentify_private_text(outbound, identity_context) as deidentified:
            placeholder_text = _normalize_reserved_labels(deidentified.text)
            text = genericize_private_prompt(placeholder_text, _PRIVATE_PLACEHOLDER)
            if text is None or scan_residuals(text):
                return PrivateContextFallbackCode.SAFETY
    except Exception:
        return PrivateContextFallbackCode.SAFETY
    return PrivateModelContext(text, knowledge.card_count)


def provider_output_is_private_safe(raw: object) -> bool:
    """Reject private-boundary artifacts before any DeepSeek parser sees them."""
    if type(raw) is not str:
        return False
    if _contains_private_artifact(raw):
        return False
    if not raw or len(raw) > MAX_PROVIDER_OUTPUT_CHARACTERS:
        return False
    try:
        decoded = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except Exception:
        return False
    return _decoded_output_is_private_safe(decoded)


def provider_output_contains_placeholder(raw: object) -> bool:
    """Return only whether a bounded provider output echoes a private token."""
    if (
        type(raw) is not str
        or not raw
        or len(raw) > MAX_PROVIDER_OUTPUT_CHARACTERS
    ):
        return False
    if _PRIVATE_PLACEHOLDER.search(raw):
        return True
    try:
        decoded = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except Exception:
        return False
    return _decoded_contains_placeholder(decoded)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ValueError("nonstandard_json_constant")


def _decoded_output_is_private_safe(decoded: object) -> bool:
    items = 0
    stack = [(decoded, 0)]
    while stack:
        value, depth = stack.pop()
        items += 1
        if depth > MAX_PROVIDER_OUTPUT_DEPTH or items > MAX_PROVIDER_OUTPUT_ITEMS:
            return False
        if isinstance(value, dict):
            for key, child in value.items():
                if _contains_private_artifact(key):
                    return False
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            if _contains_private_artifact(value):
                return False
        elif isinstance(value, float) and not math.isfinite(value):
            return False
        elif value is not None and not isinstance(value, (bool, int, float)):
            return False
    return True


def _decoded_contains_placeholder(decoded: object) -> bool:
    items = 0
    stack = [(decoded, 0)]
    while stack:
        value, depth = stack.pop()
        items += 1
        if depth > MAX_PROVIDER_OUTPUT_DEPTH or items > MAX_PROVIDER_OUTPUT_ITEMS:
            return False
        if isinstance(value, dict):
            for key, child in value.items():
                if _PRIVATE_PLACEHOLDER.search(key):
                    return True
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str) and _PRIVATE_PLACEHOLDER.search(value):
            return True
    return False


def _contains_private_artifact(value: str) -> bool:
    return bool(
        _PRIVATE_PLACEHOLDER.search(value)
        or _PRIVATE_OUTPUT_MARKER.search(value)
        or any(pattern.search(value) for pattern in _RESTORATION_PATTERNS)
    )


def _provider_budget(budget: object) -> float | None:
    try:
        timeout = budget.provider_timeout_seconds(
            DEEPSEEK_PROVIDER_MAX_SECONDS,
            maximum_seconds=DEEPSEEK_PROVIDER_MAX_SECONDS,
        )
    except Exception:
        return None
    return timeout if isinstance(timeout, (int, float)) else None


def _header_identity_context(values: object) -> dict[str, list[str]] | None:
    if type(values) is not tuple or len(values) > MAX_HEADER_VALUES:
        return None
    if any(
        not isinstance(value, str)
        or len(value) >= MAX_HEADER_CHARACTERS
        or "\r" in value
        or "\n" in value
        for value in values
    ):
        return None
    names: set[str] = set()
    for value in values:
        parsed_names = _display_names(value)
        if parsed_names is None:
            return None
        names.update(parsed_names)
    if len(names) > MAX_IDENTITY_NAMES:
        return None
    return {"people": sorted(names), "organizations": []}


def _display_names(value: str) -> tuple[str, ...] | None:
    candidate = value.strip()
    if not candidate:
        return ()
    bracketed = "<" in candidate or ">" in candidate
    if candidate.count("<") != candidate.count(">"):
        return None
    try:
        parsed = getaddresses([candidate])
    except Exception:
        return None
    if not parsed or any(not name.strip() and not address.strip() for name, address in parsed):
        return None
    names: list[str] = []
    for name, address in parsed:
        display = name.strip()
        mailbox = address.strip()
        if bracketed and _HEADER_EMAIL.fullmatch(mailbox) is None:
            return None
        if "@" in mailbox and _HEADER_EMAIL.fullmatch(mailbox) is None:
            return None
        if not display and mailbox and "@" not in mailbox:
            display = mailbox
        if display:
            if not 1 <= len(display) <= 200:
                return None
            names.append(display)
    return tuple(names)


def _normalize_reserved_labels(text: str) -> str:
    for label in _RESERVED_CONTROL_LABELS:
        text = text.replace(label, label.lower())
    return text
