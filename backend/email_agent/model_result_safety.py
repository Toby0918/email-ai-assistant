"""Fail-closed projection of a private DeepSeek envelope into public analysis."""
from __future__ import annotations
import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .analysis_schema import validate_analysis_result
from .deepseek_analysis_schema import validate_deepseek_analysis_v1, validate_envelope_evidence
from .model_grounding import find_grounding_violations
from .model_text_safety import has_chinese, has_unconditional_commitment, has_unsafe_operation, validate_public_language
from .prompt_context import EvidenceSource
from .thread_timeline import TimelineBuild
_FIELDS = (
    "summary", "priority", "priority_reason", "category", "tags", "decision_brief",
    "conversation_timeline", "risk_flags", "suggested_actions", "reply_draft", "attachment_insights",
)
_DRAFT_REASON = "模型草稿未通过安全检查，已保留规则草稿。"
_RISK_FIELDS = {"type", "level", "evidence", "recommendation"}
_DRAFT_FIELDS = {"subject", "body", "needs_human_review", "review_reasons"}
@dataclass(frozen=True, slots=True)
class SafeMergeResult:
    analysis: dict[str, Any]
    used_model: bool
    fallback_fields: tuple[str, ...]

def merge_deepseek_analysis_v1(
    envelope: object, *, fallback: Mapping[str, Any], sources: Mapping[str, EvidenceSource],
    timeline: TimelineBuild, evidence: Mapping[str, Sequence[str]],
) -> SafeMergeResult:
    """Merge safe provider fields while retaining deterministic local safeguards."""
    try:
        private, raw = _validated_private(envelope, fallback)
        normalized_evidence = _validate_global_inputs(private, evidence, sources)
        violations = {item.pointer for item in find_grounding_violations(private, normalized_evidence, sources)}
        public = _public_fallback(fallback)
        kept: set[str] = set()
        analysis = private["analysis"]
        raw_analysis = raw["analysis"]
        _merge_direct(public, analysis, violations, kept)
        brief = _safe_brief(analysis["decision_brief"], sources, violations)
        if brief is None:
            kept.add("decision_brief")
        else:
            public["decision_brief"] = brief
        merged_timeline = _safe_timeline(
            analysis["timeline_interpretation"], timeline, violations, normalized_evidence
        )
        if merged_timeline is None:
            kept.add("conversation_timeline")
            public["conversation_timeline"] = copy.deepcopy(timeline.public_timeline)
        else:
            public["conversation_timeline"] = merged_timeline
        _merge_extended(public, fallback, private, raw_analysis, sources, violations, kept)
        validate_analysis_result(public)
        validate_public_language(public)
        used_model = any(public[field] != fallback[field] for field in _FIELDS)
        fields = tuple(field for field in _FIELDS if field in kept)
        return SafeMergeResult(public, used_model, fields)
    except Exception:
        return SafeMergeResult(_public_fallback(fallback), False, ("all",))

def _validated_private(envelope: object, fallback: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = copy.deepcopy(envelope)
    candidate = copy.deepcopy(raw)
    analysis = candidate["analysis"]
    risks = analysis["risk_flags"]
    if isinstance(risks, list):
        placeholder = {"type": "security_risk", "level": "low", "evidence": "", "recommendation": ""}
        analysis["risk_flags"] = [item if _risk_shape(item) else placeholder for item in risks]
    else:
        analysis["risk_flags"] = []
    draft = analysis["reply_draft"]
    if not _draft_shape(draft):
        analysis["reply_draft"] = copy.deepcopy(fallback["reply_draft"])
    else:
        draft["needs_human_review"] = True
    return validate_deepseek_analysis_v1(candidate), raw

def _validate_global_inputs(
    envelope: dict[str, Any], evidence: Mapping[str, Sequence[str]],
    sources: Mapping[str, EvidenceSource],
) -> dict[str, tuple[str, ...]]:
    if any(
        key != source.source_id
        or source.kind not in {"thread", "attachment"}
        or not isinstance(source.public_source, str)
        or not source.public_source
        for key, source in sources.items()
    ):
        raise ValueError("Invalid source registry.")
    envelope_evidence = validate_envelope_evidence(envelope, sources)
    supplied: dict[str, tuple[str, ...]] = {}
    for pointer, values in evidence.items():
        if not isinstance(pointer, str) or isinstance(values, (str, bytes)):
            raise ValueError("Invalid evidence map.")
        supplied[pointer] = tuple(values)
    if supplied != envelope_evidence:
        raise ValueError("Evidence map does not match envelope.")
    return supplied

def _merge_direct(
    public: dict[str, Any], analysis: dict[str, Any],
    violations: set[str], kept: set[str],
) -> None:
    for field in ("summary", "priority", "priority_reason", "category", "tags"):
        unsafe = False
        if field in {"summary", "priority_reason"}:
            unsafe = not has_chinese(analysis[field]) or f"/analysis/{field}" in violations
        elif field == "tags":
            unsafe = any(pointer.startswith("/analysis/tags/") for pointer in violations)
        if unsafe:
            kept.add(field)
        else:
            public[field] = copy.deepcopy(analysis[field])

def _merge_extended(public, fallback, private, raw_analysis, sources, violations, kept) -> None:
    values = {
        "risk_flags": _safe_risks(raw_analysis["risk_flags"], fallback["risk_flags"], violations),
        "suggested_actions": _safe_actions(private["analysis"]["suggested_actions"], fallback["suggested_actions"], violations),
        "reply_draft": _safe_draft(raw_analysis["reply_draft"], fallback["reply_draft"], violations),
        "attachment_insights": _safe_attachments(private["attachment_augmentations"], fallback["attachment_insights"], sources, violations),
    }
    for field, (value, fell_back) in values.items():
        public[field] = value
        if fell_back:
            kept.add(field)

def _risk_shape(item: object) -> bool:
    return isinstance(item, dict) and set(item) == _RISK_FIELDS and all(
        isinstance(item[field], str) for field in _RISK_FIELDS
    )

def _draft_shape(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != _DRAFT_FIELDS:
        return False
    return all(isinstance(value[field], str) for field in ("subject", "body")) and (
        isinstance(value["needs_human_review"], bool)
        and isinstance(value["review_reasons"], list)
        and all(isinstance(item, str) for item in value["review_reasons"])
    )

def _safe_risks(
    items: object, fallback: object, violations: set[str]
) -> tuple[list[dict[str, Any]], bool]:
    result = copy.deepcopy(fallback)
    if not isinstance(items, list):
        return result, True
    seen = {(item["type"], item["evidence"], item["recommendation"]) for item in result}
    rejected = False
    for index, item in enumerate(items):
        pointer = f"/analysis/risk_flags/{index}/"
        if not _risk_shape(item):
            rejected = True
            continue
        key = (item["type"], item["evidence"], item["recommendation"])
        unsafe = (
            key in seen or not has_chinese(item["evidence"])
            or not has_chinese(item["recommendation"])
            or any(value.startswith(pointer) for value in violations)
        )
        if unsafe:
            rejected = True
            continue
        result.append(copy.deepcopy(item))
        seen.add(key)
    return result, rejected or result == fallback

def _safe_actions(
    items: object, fallback: object, violations: set[str]
) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(items, list):
        return copy.deepcopy(fallback), True
    for index, item in enumerate(items):
        prefix = f"/analysis/suggested_actions/{index}/"
        description = item.get("description") if isinstance(item, dict) else None
        if (
            not isinstance(description, str) or not has_chinese(description)
            or any(value.startswith(prefix) for value in violations)
            or has_unsafe_operation(description) or has_unconditional_commitment(description)
        ):
            return copy.deepcopy(fallback), True
    return copy.deepcopy(items), False

def _safe_draft(
    value: object, fallback: object, violations: set[str]
) -> tuple[dict[str, Any], bool]:
    safe = _draft_shape(value) and value["needs_human_review"] is True
    if safe:
        safe = not has_chinese(value["subject"]) and not has_chinese(value["body"])
        safe = safe and all(has_chinese(item) for item in value["review_reasons"])
        safe = safe and not any(
            item.startswith("/analysis/reply_draft/") for item in violations
        )
        safe = safe and not has_unsafe_operation(value["subject"] + "\n" + value["body"])
        safe = safe and not has_unconditional_commitment(value["subject"] + "\n" + value["body"])
    if safe:
        return copy.deepcopy(value), False
    result = copy.deepcopy(fallback)
    result["needs_human_review"] = True
    if _DRAFT_REASON not in result["review_reasons"]:
        result["review_reasons"].append(_DRAFT_REASON)
    return result, True

def _safe_attachments(
    items: object, fallback: object, sources: Mapping[str, EvidenceSource],
    violations: set[str],
) -> tuple[list[dict[str, Any]], bool]:
    result = copy.deepcopy(fallback)
    if not isinstance(items, list) or not isinstance(result, list):
        return result, True
    ids = [item.get("source_id") if isinstance(item, dict) else None for item in items]
    indexes = [sources[value].attachment_index if value in sources else None for value in ids]
    accepted: set[int] = set()
    rejected = False
    for position, item in enumerate(items):
        source_id, index = ids[position], indexes[position]
        source = sources.get(source_id) if isinstance(source_id, str) else None
        valid_index = isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(result)
        valid = (
            source is not None and source.kind == "attachment" and source.parsed
            and valid_index and ids.count(source_id) == 1 and indexes.count(index) == 1
            and result[index]["status"] == "parsed"
            and source.public_source == "attachment:" + result[index]["filename"]
            and not any(value.startswith(f"/attachment_augmentations/{position}/") for value in violations)
        )
        if not valid:
            rejected = True
            continue
        result[index]["summary"] = copy.deepcopy(item["summary"])
        result[index]["key_facts"] = copy.deepcopy(item["key_facts"])
        accepted.add(index)
    return result, rejected or len(accepted) < len(result)

def _safe_brief(
    value: dict[str, Any], sources: Mapping[str, EvidenceSource], violations: set[str]
) -> dict[str, Any] | None:
    if any(pointer.startswith("/analysis/decision_brief/") for pointer in violations):
        return None
    required = [value["one_line_conclusion"], value["requested_outcome"],
                value["reply_recommendation"]["reason"], *value["must_check"], *value["missing_info"]]
    required.extend(item["step"] for item in value["next_steps"])
    text = repr(value)
    if any(not has_chinese(item) for item in required):
        return None
    if has_unsafe_operation(text) or has_unconditional_commitment(text):
        return None
    result = copy.deepcopy(value)
    for collection in (result["next_steps"], result["key_facts"]):
        for item in collection:
            source = sources.get(item["source"])
            if source is None or (source.kind == "attachment" and not source.parsed):
                return None
            item["source"] = source.public_source
    return result

def _safe_timeline(
    value: dict[str, Any], timeline: TimelineBuild, violations: set[str],
    evidence: Mapping[str, Sequence[str]],
) -> dict[str, Any] | None:
    if any(pointer.startswith("/analysis/timeline_interpretation/") for pointer in violations):
        return None
    if not has_chinese(value["previous_context"]) or not has_chinese(value["status_reason"]):
        return None
    known = {item.open_item_id: item for item in timeline.open_items}
    updates: dict[str, str] = {}
    for index, annotation in enumerate(value["open_item_annotations"]):
        item_id, text = annotation["open_item_id"], annotation["item"]
        if item_id not in known or item_id in updates or not has_chinese(text):
            return None
        item = known[item_id]
        if not item.evidence_sources:
            updates[item_id] = item.item
            continue
        pointer = f"/analysis/timeline_interpretation/open_item_annotations/{index}/item"
        claimed = evidence.get(pointer, ())
        if not claimed or not set(claimed).issubset(item.evidence_sources):
            return None
        updates[item_id] = text
    base = timeline.public_timeline
    return {
        "previous_context": value["previous_context"],
        "current_status": copy.deepcopy(base["current_status"]),
        "status_reason": value["status_reason"],
        "latest_external_request": copy.deepcopy(base["latest_external_request"]),
        "latest_internal_commitment": copy.deepcopy(base["latest_internal_commitment"]),
        "open_items": [
            {
                "item": updates.get(item.open_item_id, item.item), "owner_hint": item.owner_hint,
                "due_hint": item.due_hint, "source": item.source,
            }
            for item in timeline.open_items
        ],
        "confidence": copy.deepcopy(base["confidence"]),
    }

def _public_fallback(value: Mapping[str, Any]) -> dict[str, Any]:
    return {field: copy.deepcopy(value[field]) for field in _FIELDS}
