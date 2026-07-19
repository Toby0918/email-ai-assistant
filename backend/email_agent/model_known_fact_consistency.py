"""Reject provider prose that contradicts deterministic local MOQ facts."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .quantity_facts import labeled_quantity_facts, labeled_quantity_occurrences

_MOQ_TERM = (
    r"(?:MOQ|minimum\s+order\s+(?:qty|quantity)|最低起订量|最低订购量)"
)
_UNRESOLVED_STATE = (
    r"(?:remains?\s+pending|is\s+(?:pending|unknown|unresolved|"
    r"not\s+(?:final|confirmed))|(?:still\s+)?needs?\s+confirmation|"
    r"requires?\s+confirmation|to\s+be\s+confirmed)"
)
_MOQ_UNRESOLVED_RE = re.compile(
    rf"\b{_MOQ_TERM}\b\s+{_UNRESOLVED_STATE}|"
    rf"{_MOQ_TERM}\s*(?:仍需确认|需要确认|待确认|未确认|未明确|待定)",
    re.IGNORECASE,
)
_TRAILING_UNRESOLVED_RE = re.compile(
    rf"^\s*{_UNRESOLVED_STATE}\b",
    re.IGNORECASE,
)
_CLAUSE_RE = re.compile(r"[^.;!?。！？；;\n]+")


def provider_claims_known_moq_unresolved(
    provider_value: object,
    local_key_facts: object,
) -> bool:
    """Return whether provider prose reopens a local final MOQ fact."""
    if not _known_moq_signatures(local_key_facts):
        return False
    return any(
        _MOQ_UNRESOLVED_RE.search(clause)
        or _has_trailing_moq_uncertainty(clause)
        for text in _public_text_values(provider_value)
        for clause in _CLAUSE_RE.findall(text)
    )


def known_moq_conflicting_fields(
    private: Mapping[str, Mapping[str, object]],
    raw_analysis: Mapping[str, object],
    local_key_facts: object,
) -> tuple[str, ...]:
    """Return provider-owned fields that reopen a deterministic final MOQ."""
    analysis = private["analysis"]
    provider_values = {
        "summary": analysis["summary"],
        "priority_reason": analysis["priority_reason"],
        "tags": analysis["tags"],
        "decision_brief": analysis["decision_brief"],
        "conversation_timeline": analysis["timeline_interpretation"],
        "risk_flags": raw_analysis["risk_flags"],
        "suggested_actions": analysis["suggested_actions"],
        "reply_draft": raw_analysis["reply_draft"],
        "attachment_insights": private["attachment_augmentations"],
    }
    return tuple(
        field
        for field, provider_value in provider_values.items()
        if provider_claims_known_moq_unresolved(provider_value, local_key_facts)
    )


def _has_trailing_moq_uncertainty(clause: str) -> bool:
    return any(
        _TRAILING_UNRESOLVED_RE.match(clause[occurrence.end:])
        for occurrence in labeled_quantity_occurrences(clause)
    )


def _known_moq_signatures(local_key_facts: object) -> frozenset[str]:
    signatures: set[str] = set()
    for text in _local_key_fact_texts(local_key_facts):
        for fact in labeled_quantity_facts(text):
            signatures.update(fact.signatures)
    return frozenset(signatures)


def _local_key_fact_texts(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    texts: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            label, fact_value = item.get("label"), item.get("value")
            if isinstance(label, str) and isinstance(fact_value, str):
                texts.append(f"{label}: {fact_value}")
        elif isinstance(item, str):
            texts.append(item)
    return tuple(texts)


def _public_text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(
            text for child in value.values() for text in _public_text_values(child)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(
            text for child in value for text in _public_text_values(child)
        )
    return ()
