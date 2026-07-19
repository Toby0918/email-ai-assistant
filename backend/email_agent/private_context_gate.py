"""Local-only deidentification gate for remote DeepSeek user content."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum

from backend.private_knowledge.deidentifier import deidentify_private_text
from backend.private_knowledge.entity_patterns import PATTERNS, PLACEHOLDER
from backend.private_knowledge.residual_scanner import scan_residuals

from .analysis_budget import DEEPSEEK_PROVIDER_MAX_SECONDS
from .model_request import ModelAnalysisRequest
from .multimodal_media import PreparedMediaAsset
from .private_knowledge_context import render_private_knowledge_context
from .participant_identity_aliases import (
    MAX_HEADER_CHARACTERS,
    header_identity_context as _header_identity_context,
)
from .private_prompt_genericizer import genericize_private_prompt
from .private_provider_output_gate import (
    provider_output_contains_placeholder as _output_contains_placeholder,
    provider_output_contains_private_artifact as _output_contains_artifact,
    provider_output_is_private_safe as _output_is_private_safe,
)


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


class PrivateContextFallbackCode(Enum):
    SAFETY = "safety"
    BUDGET = "budget"


@dataclass(frozen=True, slots=True)
class PrivateModelRequest:
    prompt: str = field(repr=False)
    header_values: tuple[str, ...] = field(repr=False)
    current_only_prompt: str | None = field(default=None, repr=False)
    current_only_header_values: tuple[str, ...] = field(default=(), repr=False)
    context_scope: str = "current_only"
    context_limited: bool = False
    prepared_media_assets: tuple[PreparedMediaAsset, ...] = field(
        default=(), repr=False
    )


@dataclass(frozen=True, slots=True)
class PrivateModelContext:
    model_request: ModelAnalysisRequest = field(repr=False)
    selected_card_count: int
    context_scope: str = "current_only"
    context_limited: bool = False

    @property
    def text(self) -> str:
        """Preserve the existing text-only route seam until provider routing changes."""
        return self.model_request.text


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
    knowledge = render_private_knowledge_context(cards, rule_result)
    text = _build_safe_prompt(request.prompt, request.header_values, knowledge.text)
    if text is not None:
        model_request = _model_request(text, request.prepared_media_assets)
        if model_request is None:
            return PrivateContextFallbackCode.SAFETY
        return PrivateModelContext(
            model_request,
            knowledge.card_count,
            request.context_scope if request.context_scope in {"current_only", "relevant_history"} else "current_only",
            bool(request.context_limited),
        )
    if request.current_only_prompt is None:
        return PrivateContextFallbackCode.SAFETY
    text = _build_safe_prompt(
        request.current_only_prompt,
        request.current_only_header_values,
        knowledge.text,
    )
    if text is None:
        return PrivateContextFallbackCode.SAFETY
    model_request = _model_request(text, request.prepared_media_assets)
    if model_request is None:
        return PrivateContextFallbackCode.SAFETY
    return PrivateModelContext(model_request, knowledge.card_count, "current_only", True)


def _model_request(
    text: str, assets: object,
) -> ModelAnalysisRequest | None:
    try:
        return ModelAnalysisRequest(text, assets)
    except (TypeError, ValueError):
        return None


def _build_safe_prompt(
    prompt: str, header_values: tuple[str, ...], knowledge_text: str,
) -> str | None:
    identity_context = _header_identity_context(header_values)
    if identity_context is None:
        return None
    safe_prompt = _deidentify_prompt_values(prompt, identity_context)
    if safe_prompt is None:
        return None
    if knowledge_text:
        safe_knowledge = _deidentify_plain_prompt(knowledge_text, identity_context)
        if safe_knowledge is None:
            return None
        safe_prompt += "\n\napproved_knowledge_context\n" + safe_knowledge
    return safe_prompt


def _deidentify_prompt_values(
    prompt: object, identity_context: dict[str, list[str]],
) -> str | None:
    if not isinstance(prompt, str):
        return None
    stripped = prompt.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            decoded = json.loads(
                prompt,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_json_constant,
            )
        except Exception:
            return None
        safe = _deidentify_json_values(decoded, identity_context)
        if safe is None:
            return None
        return json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
    return _deidentify_plain_prompt(prompt, identity_context)


def _deidentify_json_values(value: object, identity_context: dict[str, list[str]]) -> object:
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                return None
            safe_child = _deidentify_json_values(child, identity_context)
            if safe_child is None and child is not None:
                return None
            result[key] = safe_child
        return result
    if isinstance(value, list):
        result_list: list[object] = []
        for child in value:
            safe_child = _deidentify_json_values(child, identity_context)
            if safe_child is None and child is not None:
                return None
            result_list.append(safe_child)
        return result_list
    if isinstance(value, str):
        return _deidentify_text_value(value, identity_context)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def _deidentify_plain_prompt(
    prompt: str, identity_context: dict[str, list[str]],
) -> str | None:
    safe_lines: list[str] = []
    for line in prompt.splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z0-9_.\[\]-]*:\s+)(.*)$", line)
        prefix, value = (match.group(1), match.group(2)) if match else ("", line)
        safe_value = _deidentify_text_value(value, identity_context)
        if safe_value is None:
            return None
        safe_lines.append(_normalize_reserved_labels(prefix) + safe_value)
    return "\n".join(safe_lines)


def _deidentify_text_value(
    value: str, identity_context: dict[str, list[str]],
) -> str | None:
    value = _normalize_reserved_labels(value)
    generic_input = genericize_private_prompt(value, _PRIVATE_PLACEHOLDER)
    if generic_input is None:
        return None
    try:
        with deidentify_private_text(generic_input, identity_context) as deidentified:
            generic = genericize_private_prompt(deidentified.text, _PRIVATE_PLACEHOLDER)
            if generic is None or scan_residuals(generic):
                return None
            return generic
    except Exception:
        return None


def provider_output_is_private_safe(raw: object) -> bool:
    return _output_is_private_safe(raw, _contains_private_artifact)


def provider_output_contains_placeholder(raw: object) -> bool:
    return _output_contains_placeholder(raw, _contains_private_placeholder)


def provider_output_contains_private_artifact(raw: object) -> bool:
    return _output_contains_artifact(raw, _contains_private_artifact)


def model_request_text_is_private_safe(text: object) -> bool:
    """Revalidate one dispatch-ready text value without exposing findings."""
    if type(text) is not str or _PRIVATE_PLACEHOLDER.search(text):
        return False
    try:
        return not scan_residuals(text)
    except Exception:
        return False


def _contains_private_placeholder(value: str) -> bool:
    return bool(_PRIVATE_PLACEHOLDER.search(value))


def _contains_private_artifact(value: str) -> bool:
    return bool(
        _contains_private_placeholder(value)
        or _PRIVATE_OUTPUT_MARKER.search(value)
        or any(pattern.search(value) for pattern in _RESTORATION_PATTERNS)
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ValueError("nonstandard_json_constant")


def _provider_budget(budget: object) -> float | None:
    try:
        timeout = budget.provider_timeout_seconds(
            DEEPSEEK_PROVIDER_MAX_SECONDS,
            maximum_seconds=DEEPSEEK_PROVIDER_MAX_SECONDS,
        )
    except Exception:
        return None
    return timeout if isinstance(timeout, (int, float)) else None


def _normalize_reserved_labels(text: str) -> str:
    for label in _RESERVED_CONTROL_LABELS:
        text = text.replace(label, label.lower())
    return text
