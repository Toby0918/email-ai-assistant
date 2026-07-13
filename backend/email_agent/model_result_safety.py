"""Fail-closed projection of a private DeepSeek envelope into public analysis."""
from __future__ import annotations
import copy, re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .analysis_schema import validate_analysis_result
from .deepseek_analysis_schema import validate_deepseek_analysis_v1, validate_envelope_evidence
from .model_grounding import find_grounding_violations
from .prompt_context import EvidenceSource
from .thread_timeline import TimelineBuild
_FIELDS = (
    "summary", "priority", "priority_reason", "category", "tags", "decision_brief",
    "conversation_timeline", "risk_flags",
    "suggested_actions", "reply_draft", "attachment_insights",
)
_FIXED = {"risk_flags", "suggested_actions", "reply_draft", "attachment_insights"}
_CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
_AUTO_ACTION_RE = re.compile(
    r"(?:自动|直接|无需人工|系统将).{0,16}(?:发送|回复|删除|归档|转发|支付|签署)|"
    r"\b(?:auto(?:matically)?[- ]?|without human (?:review|approval).{0,12})(?:send|reply|delete|archive|forward|pay|sign)\b|"
    r"\b(?:send|reply|delete|archive|forward|pay|sign).{0,12}(?:automatically|without human (?:review|approval))\b", re.I,
)
_COMMITMENT_RE = re.compile(
    r"\b(?:i|we)\s+(?:(?:will|shall)\s+(?:ship|dispatch|deliver|fulfil|fulfill|pay)|"
    r"(?:will\s+)?(?:guarantee|commit(?:\s+to)?|accept|agree(?:\s+to)?).{0,32}"
    r"(?:price|quote|delivery|payment|contract|terms?|quality|warranty|legal|liability))\b|"
    r"(?:我方|我们|我).{0,12}(?:保证|承诺|接受|同意|会|将).{0,20}"
    r"(?:发货|交付|履行|付款|支付|价格|报价|合同|条款|质量|保修|法律|责任|赔偿)", re.I,
)
@dataclass(frozen=True, slots=True)
class SafeMergeResult:
    analysis: dict[str, Any]
    used_model: bool
    fallback_fields: tuple[str, ...]

def merge_deepseek_analysis_v1(
    envelope: object, *, fallback: Mapping[str, Any], sources: Mapping[str, EvidenceSource],
    timeline: TimelineBuild, evidence: Mapping[str, Sequence[str]],
) -> SafeMergeResult:
    """Merge only safe 9B1 fields; any global uncertainty returns the fallback."""
    try:
        private = copy.deepcopy(validate_deepseek_analysis_v1(envelope))
        normalized_evidence = _validate_global_inputs(private, evidence, sources)
        violations = {item.pointer for item in find_grounding_violations(private, normalized_evidence, sources)}
        public = _public_fallback(fallback)
        kept = set(_FIXED)
        analysis = private["analysis"]
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
        validate_analysis_result(public)
        _validate_analysis_language(public)
        used_model = any(public[field] != fallback[field] for field in set(_FIELDS) - kept)
        fields = tuple(field for field in _FIELDS if field in kept)
        return SafeMergeResult(public, used_model, fields)
    except Exception:
        return SafeMergeResult(_public_fallback(fallback), False, ("all",))

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
            unsafe = not _has_chinese(analysis[field]) or f"/analysis/{field}" in violations
        elif field == "tags":
            unsafe = any(pointer.startswith("/analysis/tags/") for pointer in violations)
        if unsafe:
            kept.add(field)
        else:
            public[field] = copy.deepcopy(analysis[field])

def _safe_brief(
    value: dict[str, Any], sources: Mapping[str, EvidenceSource], violations: set[str]
) -> dict[str, Any] | None:
    if any(pointer.startswith("/analysis/decision_brief/") for pointer in violations):
        return None
    required = [value["one_line_conclusion"], value["requested_outcome"],
                value["reply_recommendation"]["reason"], *value["must_check"], *value["missing_info"]]
    required.extend(item["step"] for item in value["next_steps"])
    text = repr(value)
    if any(not _has_chinese(item) for item in required):
        return None
    if _AUTO_ACTION_RE.search(text) or _COMMITMENT_RE.search(text):
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
    if not _has_chinese(value["previous_context"]) or not _has_chinese(value["status_reason"]):
        return None
    known = {item.open_item_id: item for item in timeline.open_items}
    updates: dict[str, str] = {}
    for index, annotation in enumerate(value["open_item_annotations"]):
        item_id, text = annotation["open_item_id"], annotation["item"]
        if item_id not in known or item_id in updates or not _has_chinese(text):
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

def _validate_analysis_language(value: dict[str, Any]) -> None:
    brief = value["decision_brief"]
    required = [value["summary"], value["priority_reason"], brief["one_line_conclusion"],
                brief["requested_outcome"], brief["reply_recommendation"]["reason"]]
    required += [item["step"] for item in brief["next_steps"]] + brief["must_check"] + brief["missing_info"]
    timeline = value["conversation_timeline"]
    required += [timeline["previous_context"], timeline["status_reason"]] + [item["item"] for item in timeline["open_items"]]
    required += [item[field] for item in value["risk_flags"] for field in ("evidence", "recommendation")]
    required += [item["description"] for item in value["suggested_actions"]] + value["reply_draft"]["review_reasons"]
    if any(item and not _has_chinese(item) for item in required):
        raise ValueError("Analysis prose must be Chinese.")
    draft = value["reply_draft"]
    if _has_chinese(draft["subject"]) or _has_chinese(draft["body"]):
        raise ValueError("External reply draft must be English.")

def _public_fallback(value: Mapping[str, Any]) -> dict[str, Any]:
    return {field: copy.deepcopy(value[field]) for field in _FIELDS}

def _has_chinese(value: str) -> bool:
    return bool(_CHINESE_RE.search(value))
