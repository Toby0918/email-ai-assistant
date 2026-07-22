"""Fail-closed safety checks for model-authored attachment augmentations."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from .evidence_source import EvidenceSource
from .model_exact_fact_safety import contains_model_authored_exact_fact
from .model_text_safety import is_safe_model_text


_MAX_PUBLIC_KEY_FACTS = 5


def require_complete_attachment_coverage(
    private: Mapping[str, Any],
    fallback: Mapping[str, Any],
    sources: Mapping[str, EvidenceSource],
    violations: set[str],
    evidence: Mapping[str, Sequence[str]],
) -> None:
    """Require one independently grounded augmentation for every parsed source."""
    fallback_items = fallback.get("attachment_insights")
    expected = {
        source_id
        for source_id, source in sources.items()
        if source.kind == "attachment" and source.parsed
    }
    if not expected:
        return
    if not isinstance(fallback_items, list) or not fallback_items:
        raise ValueError("Attachment semantic target is unavailable.")
    items = private["attachment_augmentations"]
    ids = [item["source_id"] for item in items]
    indexes = [
        sources[source_id].attachment_index if source_id in sources else None
        for source_id in ids
    ]
    if len(items) != len(expected) or set(ids) != expected:
        raise ValueError("Attachment semantic coverage is incomplete.")
    for position, item in enumerate(items):
        source_id = ids[position]
        if item["evidence_sources"] != [source_id]:
            raise ValueError("Attachment semantic coverage is not source-bound.")
        pointers = _augmentation_leaf_pointers(position, item)
        if any(tuple(evidence.get(pointer, ())) != (source_id,) for pointer in pointers):
            raise ValueError("Attachment semantic evidence is incomplete.")
        if not _valid_attachment_augmentation(
            item, position, fallback_items, sources, violations, ids, indexes,
        ):
            raise ValueError("Attachment semantic coverage is unsafe.")


def safe_attachment_augmentations(
    items: object,
    fallback: object,
    sources: Mapping[str, EvidenceSource],
    violations: set[str],
) -> tuple[list[dict[str, Any]], bool]:
    """Merge validated attachment augmentations into deterministic targets."""
    result = copy.deepcopy(fallback)
    if not isinstance(items, list) or not isinstance(result, list):
        return result, True
    ids = [item.get("source_id") if isinstance(item, dict) else None for item in items]
    indexes = [sources[value].attachment_index if value in sources else None for value in ids]
    accepted: set[int] = set()
    rejected = False
    for position, item in enumerate(items):
        index = indexes[position]
        if not _valid_attachment_augmentation(
            item, position, result, sources, violations, ids, indexes,
        ):
            rejected = True
            continue
        result[index]["summary"] = copy.deepcopy(item["summary"])
        result[index]["key_facts"] = _preserve_local_key_facts(
            result[index]["key_facts"], item["key_facts"]
        )
        accepted.add(index)
    return result, rejected or len(accepted) < len(result)


def _preserve_local_key_facts(
    local_facts: Sequence[str], model_facts: Sequence[str],
) -> list[str]:
    """Keep deterministic facts byte-for-byte and append bounded model additions."""
    merged = copy.deepcopy(list(local_facts))
    for fact in model_facts:
        if len(merged) >= _MAX_PUBLIC_KEY_FACTS:
            break
        if fact not in merged:
            merged.append(copy.deepcopy(fact))
    return merged


def _augmentation_leaf_pointers(
    position: int,
    item: Mapping[str, Any],
) -> tuple[str, ...]:
    return (
        f"/attachment_augmentations/{position}/summary",
        *(
            f"/attachment_augmentations/{position}/key_facts/{index}"
            for index in range(len(item["key_facts"]))
        ),
    )


def _valid_attachment_augmentation(
    item: Mapping[str, Any],
    position: int,
    fallback_items: Sequence[Mapping[str, Any]],
    sources: Mapping[str, EvidenceSource],
    violations: set[str],
    ids: Sequence[object],
    indexes: Sequence[object],
) -> bool:
    source_id = item.get("source_id")
    source = sources.get(source_id) if isinstance(source_id, str) else None
    index = source.attachment_index if source is not None else None
    valid_index = (
        isinstance(index, int)
        and not isinstance(index, bool)
        and 0 <= index < len(fallback_items)
    )
    return bool(
        source is not None
        and source.kind == "attachment"
        and source.parsed
        and valid_index
        and ids.count(source_id) == 1
        and indexes.count(index) == 1
        and _fallback_target_matches(source, fallback_items[index])
        and isinstance(item.get("summary"), str)
        and bool(item["summary"].strip())
        and is_safe_model_text(item["summary"], item["key_facts"])
        and not contains_model_authored_exact_fact(item)
        and not any(
            value.startswith(f"/attachment_augmentations/{position}/")
            for value in violations
        )
    )


def _fallback_target_matches(
    source: EvidenceSource,
    fallback_item: Mapping[str, Any],
) -> bool:
    status_matches = fallback_item["status"] == "parsed" or (
        source.grounding_mode in {"visual", "hybrid"}
        and fallback_item["status"] == "metadata_only"
    )
    return bool(
        status_matches
        and source.public_source == "attachment:" + fallback_item["filename"]
    )
