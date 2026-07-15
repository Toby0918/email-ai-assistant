"""Private versioned schema for DeepSeek analysis and evidence pointers."""
from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from .deepseek_analysis_contract import (
    ACTION_FIELDS,
    ANALYSIS_FIELDS,
    APPROVED_EVIDENCE_PATTERNS,
    ATTACHMENT_FIELDS,
    DECISION_FIELDS,
    ENVELOPE_FIELDS,
    KEY_FACT_FIELDS,
    NEXT_STEP_FIELDS,
    OPEN_ANNOTATION_FIELDS,
    REPLY_FIELDS,
    REPLY_RECOMMENDATION_FIELDS,
    RISK_FIELDS,
    SCHEMA_VERSION,
    TIMELINE_FIELDS,
    ENUM_FIELDS,
)
from .deepseek_envelope_errors import (
    ERROR_TEXT, DeepSeekEnvelopeError, decode_provider_json as _decode_json,
    raise_invalid_envelope as _invalid,
    validate_at_boundary as _validate_boundary,
)

MAX_POINTER_INDEX_DIGITS = 10

def parse_deepseek_analysis_v1(raw: str | bytes | bytearray) -> dict[str, Any]:
    value = _decode_json(raw, _object_without_duplicate_keys)
    return validate_deepseek_analysis_v1(value)

def validate_deepseek_analysis_v1(value: object) -> dict[str, Any]:
    envelope = _validate_boundary("top_level_shape", _object, value, ENVELOPE_FIELDS)
    if envelope["schema_version"] != SCHEMA_VERSION:
        _invalid("schema_version")
    _validate_boundary("analysis_shape", _validate_analysis, envelope["analysis"])
    _validate_boundary(
        "attachment_shape",
        _validate_attachments,
        envelope["attachment_augmentations"],
    )
    _validate_boundary(
        "field_evidence_shape",
        _validate_field_evidence_shape,
        envelope["field_evidence"],
    )
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
    _enum(analysis["priority"], ENUM_FIELDS["analysis.priority"])
    _string(analysis["priority_reason"])
    _enum(analysis["category"], ENUM_FIELDS["analysis.category"])
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
    _text_objects(steps, NEXT_STEP_FIELDS)
    _text_objects(brief["key_facts"], KEY_FACT_FIELDS)
    _string_list(brief["must_check"])
    _string_list(brief["missing_info"])
    recommendation = _object(
        brief["reply_recommendation"], REPLY_RECOMMENDATION_FIELDS
    )
    if not isinstance(recommendation["should_reply"], bool):
        _invalid()
    _enum(
        recommendation["reply_type"],
        ENUM_FIELDS["analysis.decision_brief.reply_recommendation.reply_type"],
    )
    _string(recommendation["reason"])
    _enum(brief["confidence"], ENUM_FIELDS["analysis.decision_brief.confidence"])

def _validate_timeline(value: object) -> None:
    timeline = _object(value, TIMELINE_FIELDS)
    _string(timeline["previous_context"])
    _string(timeline["status_reason"])
    _text_objects(timeline["open_item_annotations"], OPEN_ANNOTATION_FIELDS)
    _string_list(timeline["evidence_sources"])

def _validate_risks(value: object) -> None:
    for item in _objects(value, RISK_FIELDS):
        _enum(item["type"], ENUM_FIELDS["analysis.risk_flags[].type"])
        _enum(item["level"], ENUM_FIELDS["analysis.risk_flags[].level"])
        _string(item["evidence"])
        _string(item["recommendation"])

def _validate_actions(value: object) -> None:
    for item in _objects(value, ACTION_FIELDS):
        _enum(item["type"], ENUM_FIELDS["analysis.suggested_actions[].type"])
        for field in ("description", "owner_hint", "due_hint"):
            _string(item[field])

def _validate_reply(value: object) -> None:
    reply = _object(value, REPLY_FIELDS)
    _string(reply["subject"])
    _string(reply["body"])
    if reply["needs_human_review"] is not True:
        _invalid()
    _string_list(reply["review_reasons"])

def _validate_attachments(value: object) -> None:
    for item in _objects(value, ATTACHMENT_FIELDS):
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
    if (
        not token
        or len(token) > MAX_POINTER_INDEX_DIGITS
        or token[0] == "0"
        or any(char not in "0123456789" for char in token)
    ):
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

def _objects(value: object, fields: Collection[str]) -> list[dict[str, Any]]:
    return [_object(item, fields) for item in _list(value)]

def _text_objects(value: object, fields: Collection[str]) -> None:
    for item in _objects(value, fields):
        for field in fields:
            _string(item[field])

def _object(value: object, fields: Collection[str]) -> dict[str, Any]:
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

def _enum(value: object, allowed: Collection[str]) -> None:
    if not isinstance(value, str) or value not in allowed:
        _invalid()

def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid("json_syntax")
        value[key] = item
    return value
