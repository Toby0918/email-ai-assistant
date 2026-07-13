"""Private versioned schema for DeepSeek analysis and evidence pointers."""
from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from typing import Any, NoReturn

from .analysis_schema import (
    ACTION_TYPES, CATEGORIES, CONFIDENCE_LEVELS, DECISION_REPLY_TYPES, PRIORITIES,
    RISK_LEVELS, RISK_TYPES,
)

SCHEMA_VERSION = "deepseek_analysis_v1"
ERROR_TEXT = "DeepSeek analysis envelope is invalid."
ENVELOPE_FIELDS = {"schema_version", "analysis", "attachment_augmentations", "field_evidence"}
ANALYSIS_FIELDS = {
    "summary", "priority", "priority_reason", "category", "tags", "decision_brief",
    "timeline_interpretation", "risk_flags", "suggested_actions", "reply_draft",
}
DECISION_FIELDS = {
    "one_line_conclusion", "requested_outcome", "next_steps", "key_facts",
    "must_check", "missing_info", "reply_recommendation", "confidence",
}
APPROVED_EVIDENCE_PATTERNS = {
    ("analysis", "summary"), ("analysis", "priority_reason"),
    ("analysis", "tags", "*"),
    ("analysis", "decision_brief", "one_line_conclusion"),
    ("analysis", "decision_brief", "requested_outcome"),
    ("analysis", "decision_brief", "next_steps", "*", "step"),
    ("analysis", "decision_brief", "next_steps", "*", "owner_hint"),
    ("analysis", "decision_brief", "next_steps", "*", "due_hint"),
    ("analysis", "decision_brief", "key_facts", "*", "label"),
    ("analysis", "decision_brief", "key_facts", "*", "value"),
    ("analysis", "decision_brief", "must_check", "*"),
    ("analysis", "decision_brief", "missing_info", "*"),
    ("analysis", "decision_brief", "reply_recommendation", "reason"),
    ("analysis", "timeline_interpretation", "previous_context"),
    ("analysis", "timeline_interpretation", "status_reason"),
    ("analysis", "timeline_interpretation", "open_item_annotations", "*", "item"),
    ("analysis", "risk_flags", "*", "evidence"),
    ("analysis", "risk_flags", "*", "recommendation"),
    ("analysis", "suggested_actions", "*", "description"),
    ("analysis", "suggested_actions", "*", "owner_hint"),
    ("analysis", "suggested_actions", "*", "due_hint"),
    ("analysis", "reply_draft", "subject"), ("analysis", "reply_draft", "body"),
    ("analysis", "reply_draft", "review_reasons", "*"),
    ("attachment_augmentations", "*", "summary"),
    ("attachment_augmentations", "*", "key_facts", "*"),
}

class DeepSeekEnvelopeError(ValueError):
    """Raised when the private provider envelope fails closed."""

def parse_deepseek_analysis_v1(raw: str | bytes | bytearray) -> dict[str, Any]:
    try:
        if not isinstance(raw, (str, bytes, bytearray)):
            _invalid()
        value = json.loads(raw, object_pairs_hook=_object_without_duplicate_keys)
        return validate_deepseek_analysis_v1(value)
    except (DeepSeekEnvelopeError, json.JSONDecodeError, RecursionError, TypeError, UnicodeDecodeError):
        _invalid()

def validate_deepseek_analysis_v1(value: object) -> dict[str, Any]:
    envelope = _object(value, ENVELOPE_FIELDS)
    if envelope["schema_version"] != SCHEMA_VERSION:
        _invalid()
    _validate_analysis(envelope["analysis"])
    _validate_attachments(envelope["attachment_augmentations"])
    _validate_field_evidence_shape(envelope["field_evidence"])
    return envelope

def canonical_json_pointer(pointer: str) -> tuple[str, ...]:
    if not isinstance(pointer, str):
        _invalid()
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        _invalid()
    return tuple(_decode_pointer_token(token) for token in pointer[1:].split("/"))

def validate_envelope_evidence(
    envelope: object, sources: Collection[str] | Mapping[str, object]
) -> dict[str, tuple[str, ...]]:
    validated = validate_deepseek_analysis_v1(envelope)
    source_ids = _source_ids(sources)
    timeline = validated["analysis"]["timeline_interpretation"]
    _validate_source_list(timeline["evidence_sources"], source_ids, allow_empty=True)
    for attachment in validated["attachment_augmentations"]:
        if attachment["source_id"] not in source_ids:
            _invalid()
        _validate_source_list(attachment["evidence_sources"], source_ids, allow_empty=True)
    result: dict[str, tuple[str, ...]] = {}
    seen_targets: set[tuple[str, ...]] = set()
    for raw_pointer, evidence_sources in validated["field_evidence"].items():
        tokens = canonical_json_pointer(raw_pointer)
        if not tokens or tokens in seen_targets:
            _invalid()
        target, pattern = _resolve_pointer(validated, tokens)
        if not isinstance(target, str) or pattern not in APPROVED_EVIDENCE_PATTERNS:
            _invalid()
        _validate_source_list(evidence_sources, source_ids, allow_empty=False)
        canonical = _encode_pointer(tokens)
        if canonical in result:
            _invalid()
        seen_targets.add(tokens)
        result[canonical] = tuple(evidence_sources)
    return result

def _validate_analysis(value: object) -> None:
    analysis = _object(value, ANALYSIS_FIELDS)
    _string(analysis["summary"])
    _enum(analysis["priority"], PRIORITIES)
    _string(analysis["priority_reason"])
    _enum(analysis["category"], CATEGORIES)
    _string_list(analysis["tags"])
    _validate_decision_brief(analysis["decision_brief"])
    _validate_timeline(analysis["timeline_interpretation"])
    _validate_risks(analysis["risk_flags"])
    _validate_actions(analysis["suggested_actions"])
    _validate_reply(analysis["reply_draft"])

def _validate_decision_brief(value: object) -> None:
    brief = _object(value, DECISION_FIELDS)
    _string(brief["one_line_conclusion"])
    _string(brief["requested_outcome"])
    steps = _list(brief["next_steps"])
    if not 1 <= len(steps) <= 4:
        _invalid()
    _text_objects(steps, {"step", "owner_hint", "due_hint", "source"})
    _text_objects(brief["key_facts"], {"label", "value", "source"})
    _string_list(brief["must_check"])
    _string_list(brief["missing_info"])
    recommendation = _object(
        brief["reply_recommendation"], {"should_reply", "reply_type", "reason"}
    )
    if not isinstance(recommendation["should_reply"], bool):
        _invalid()
    _enum(recommendation["reply_type"], DECISION_REPLY_TYPES)
    _string(recommendation["reason"])
    _enum(brief["confidence"], CONFIDENCE_LEVELS)

def _validate_timeline(value: object) -> None:
    timeline = _object(
        value, {"previous_context", "status_reason", "open_item_annotations", "evidence_sources"}
    )
    _string(timeline["previous_context"])
    _string(timeline["status_reason"])
    _text_objects(timeline["open_item_annotations"], {"open_item_id", "item"})
    _string_list(timeline["evidence_sources"])

def _validate_risks(value: object) -> None:
    for item in _objects(value, {"type", "level", "evidence", "recommendation"}):
        _enum(item["type"], RISK_TYPES)
        _enum(item["level"], RISK_LEVELS)
        _string(item["evidence"])
        _string(item["recommendation"])

def _validate_actions(value: object) -> None:
    for item in _objects(value, {"type", "description", "owner_hint", "due_hint"}):
        _enum(item["type"], ACTION_TYPES)
        for field in ("description", "owner_hint", "due_hint"):
            _string(item[field])

def _validate_reply(value: object) -> None:
    reply = _object(value, {"subject", "body", "needs_human_review", "review_reasons"})
    _string(reply["subject"])
    _string(reply["body"])
    if reply["needs_human_review"] is not True:
        _invalid()
    _string_list(reply["review_reasons"])

def _validate_attachments(value: object) -> None:
    fields = {"source_id", "summary", "key_facts", "evidence_sources"}
    for item in _objects(value, fields):
        _string(item["source_id"])
        _string(item["summary"])
        _string_list(item["key_facts"])
        _string_list(item["evidence_sources"])

def _validate_field_evidence_shape(value: object) -> None:
    if not isinstance(value, dict):
        _invalid()
    for pointer, sources in value.items():
        _string(pointer)
        _string_list(sources)

def _resolve_pointer(root: object, tokens: tuple[str, ...]) -> tuple[object, tuple[str, ...]]:
    current = root
    pattern: list[str] = []
    for token in tokens:
        if isinstance(current, dict):
            if token not in current:
                _invalid()
            current = current[token]
            pattern.append(token)
        elif isinstance(current, list):
            index = _list_index(token)
            if index >= len(current):
                _invalid()
            current = current[index]
            pattern.append("*")
        else:
            _invalid()
    return current, tuple(pattern)

def _list_index(token: str) -> int:
    if token == "0":
        return 0
    if not token or token[0] == "0" or any(char not in "0123456789" for char in token):
        _invalid()
    return int(token)

def _decode_pointer_token(token: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(token):
        if token[index] != "~":
            result.append(token[index])
            index += 1
        else:
            if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
                _invalid()
            result.append("~" if token[index + 1] == "0" else "/")
            index += 2
    return "".join(result)

def _encode_pointer(tokens: tuple[str, ...]) -> str:
    return "/" + "/".join(token.replace("~", "~0").replace("/", "~1") for token in tokens)

def _source_ids(sources: Collection[str] | Mapping[str, object]) -> set[str]:
    try:
        result = set(sources)
    except TypeError:
        _invalid()
    if any(not isinstance(source, str) or not source for source in result):
        _invalid()
    return result

def _validate_source_list(values: list[str], source_ids: set[str], *, allow_empty: bool) -> None:
    if not allow_empty and not values:
        _invalid()
    if len(values) != len(set(values)) or any(value not in source_ids for value in values):
        _invalid()

def _objects(value: object, fields: set[str]) -> list[dict[str, Any]]:
    return [_object(item, fields) for item in _list(value)]

def _text_objects(value: object, fields: set[str]) -> None:
    for item in _objects(value, fields):
        for field in fields:
            _string(item[field])

def _object(value: object, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _invalid()
    return value

def _list(value: object) -> list[Any]:
    if not isinstance(value, list):
        _invalid()
    return value

def _string_list(value: object) -> list[str]:
    values = _list(value)
    if not all(isinstance(item, str) for item in values):
        _invalid()
    return values

def _string(value: object) -> None:
    if not isinstance(value, str):
        _invalid()

def _enum(value: object, allowed: set[str]) -> None:
    if not isinstance(value, str) or value not in allowed:
        _invalid()

def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value

def _invalid() -> NoReturn:
    raise DeepSeekEnvelopeError(ERROR_TEXT) from None
