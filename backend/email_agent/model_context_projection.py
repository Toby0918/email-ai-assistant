"""Safe projection helpers for provider-authored brief and timeline context."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from .model_text_safety import has_chinese, is_safe_model_text
from .prompt_context import EvidenceSource
from .thread_timeline import TimelineBuild


def safe_decision_brief(
    value: dict[str, Any],
    sources: Mapping[str, EvidenceSource],
    violations: set[str],
) -> dict[str, Any] | None:
    if any(pointer.startswith("/analysis/decision_brief/") for pointer in violations):
        return None
    required = [
        value["one_line_conclusion"], value["requested_outcome"],
        value["reply_recommendation"]["reason"], *value["must_check"],
        *value["missing_info"], *(item["step"] for item in value["next_steps"]),
    ]
    if any(not has_chinese(item) for item in required):
        return None
    prose = copy.deepcopy(value)
    for item in (*prose["next_steps"], *prose["key_facts"]):
        item.pop("source", None)
    if not is_safe_model_text(prose):
        return None
    result = copy.deepcopy(value)
    for collection in (result["next_steps"], result["key_facts"]):
        for item in collection:
            source = sources.get(item["source"])
            if source is None or (source.kind == "attachment" and not source.parsed):
                return None
            item["source"] = source.public_source
    return result


def retain_decision_safeguards(
    value: Mapping[str, Any], fallback: Mapping[str, Any]
) -> dict[str, Any]:
    """Keep deterministic review gates while retaining safe model additions."""
    result = copy.deepcopy(value)
    for field in ("must_check", "missing_info"):
        result[field] = _stable_unique_strings(
            [*fallback[field], *result[field]]
        )
    return result


def safe_timeline_interpretation(
    value: dict[str, Any],
    timeline: TimelineBuild,
    violations: set[str],
    evidence: Mapping[str, Sequence[str]],
) -> dict[str, Any] | None:
    if any(pointer.startswith("/analysis/timeline_interpretation/") for pointer in violations):
        return None
    if not _safe_chinese(value["previous_context"], value["status_reason"]):
        return None
    updates = _safe_timeline_updates(value, timeline, evidence)
    if updates is None:
        return None
    base = timeline.public_timeline
    return {
        "previous_context": value["previous_context"],
        "current_status": copy.deepcopy(base["current_status"]),
        "status_reason": value["status_reason"],
        "latest_external_request": copy.deepcopy(base["latest_external_request"]),
        "latest_internal_commitment": copy.deepcopy(base["latest_internal_commitment"]),
        "open_items": [
            {
                "item": updates.get(item.open_item_id, item.item),
                "owner_hint": item.owner_hint,
                "due_hint": item.due_hint,
                "source": item.source,
            }
            for item in timeline.open_items
        ],
        "confidence": copy.deepcopy(base["confidence"]),
    }


def _safe_timeline_updates(
    value: dict[str, Any],
    timeline: TimelineBuild,
    evidence: Mapping[str, Sequence[str]],
) -> dict[str, str] | None:
    known = {item.open_item_id: item for item in timeline.open_items}
    updates: dict[str, str] = {}
    for index, annotation in enumerate(value["open_item_annotations"]):
        item_id, text = annotation["open_item_id"], annotation["item"]
        if item_id not in known or item_id in updates or not _safe_chinese(text):
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
    return updates


def _safe_chinese(*values: str) -> bool:
    return all(has_chinese(value) and is_safe_model_text(value) for value in values)


def _stable_unique_strings(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
