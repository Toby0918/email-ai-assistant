"""Immutable private DeepSeek analysis contract shared by prompt and validator."""

from __future__ import annotations

import copy
import json
from types import MappingProxyType

from .analysis_schema import (
    ACTION_TYPES,
    CATEGORIES,
    CONFIDENCE_LEVELS,
    DECISION_REPLY_TYPES,
    PRIORITIES,
    RISK_LEVELS,
    RISK_TYPES,
)


SCHEMA_VERSION = "deepseek_analysis_v1"
MAX_SYSTEM_PROMPT_CHARACTERS = 8_000

ENVELOPE_FIELDS = frozenset(
    {"schema_version", "analysis", "attachment_augmentations", "field_evidence"}
)
ANALYSIS_FIELDS = frozenset(
    {
        "summary", "priority", "priority_reason", "category", "tags",
        "decision_brief", "timeline_interpretation", "risk_flags",
        "suggested_actions", "reply_draft",
    }
)
DECISION_FIELDS = frozenset(
    {
        "one_line_conclusion", "requested_outcome", "next_steps", "key_facts",
        "must_check", "missing_info", "reply_recommendation", "confidence",
    }
)
NEXT_STEP_FIELDS = frozenset({"step", "owner_hint", "due_hint", "source"})
KEY_FACT_FIELDS = frozenset({"label", "value", "source"})
REPLY_RECOMMENDATION_FIELDS = frozenset({"should_reply", "reply_type", "reason"})
TIMELINE_FIELDS = frozenset(
    {"previous_context", "status_reason", "open_item_annotations", "evidence_sources"}
)
OPEN_ANNOTATION_FIELDS = frozenset({"open_item_id", "item"})
RISK_FIELDS = frozenset({"type", "level", "evidence", "recommendation"})
ACTION_FIELDS = frozenset({"type", "description", "owner_hint", "due_hint"})
REPLY_FIELDS = frozenset(
    {"subject", "body", "needs_human_review", "review_reasons"}
)
ATTACHMENT_FIELDS = frozenset(
    {"source_id", "summary", "key_facts", "evidence_sources"}
)

OBJECT_FIELD_SETS = MappingProxyType(
    {
        "envelope": ENVELOPE_FIELDS,
        "analysis": ANALYSIS_FIELDS,
        "analysis.decision_brief": DECISION_FIELDS,
        "analysis.decision_brief.next_steps[]": NEXT_STEP_FIELDS,
        "analysis.decision_brief.key_facts[]": KEY_FACT_FIELDS,
        "analysis.decision_brief.reply_recommendation": REPLY_RECOMMENDATION_FIELDS,
        "analysis.timeline_interpretation": TIMELINE_FIELDS,
        "analysis.timeline_interpretation.open_item_annotations[]": OPEN_ANNOTATION_FIELDS,
        "analysis.risk_flags[]": RISK_FIELDS,
        "analysis.suggested_actions[]": ACTION_FIELDS,
        "analysis.reply_draft": REPLY_FIELDS,
        "attachment_augmentations[]": ATTACHMENT_FIELDS,
    }
)

FIELD_TYPES = MappingProxyType(
    {
        "schema_version": "string",
        "analysis": "object",
        "analysis.summary": "string",
        "analysis.priority": "enum_string",
        "analysis.priority_reason": "string",
        "analysis.category": "enum_string",
        "analysis.tags": "list[string]",
        "analysis.decision_brief": "object",
        "analysis.decision_brief.one_line_conclusion": "string",
        "analysis.decision_brief.requested_outcome": "string",
        "analysis.decision_brief.next_steps": "list[object]",
        "analysis.decision_brief.next_steps[].step": "string",
        "analysis.decision_brief.next_steps[].owner_hint": "string",
        "analysis.decision_brief.next_steps[].due_hint": "string",
        "analysis.decision_brief.next_steps[].source": "string",
        "analysis.decision_brief.key_facts": "list[object]",
        "analysis.decision_brief.key_facts[].label": "string",
        "analysis.decision_brief.key_facts[].value": "string",
        "analysis.decision_brief.key_facts[].source": "string",
        "analysis.decision_brief.must_check": "list[string]",
        "analysis.decision_brief.missing_info": "list[string]",
        "analysis.decision_brief.reply_recommendation": "object",
        "analysis.decision_brief.reply_recommendation.should_reply": "boolean",
        "analysis.decision_brief.reply_recommendation.reply_type": "enum_string",
        "analysis.decision_brief.reply_recommendation.reason": "string",
        "analysis.decision_brief.confidence": "enum_string",
        "analysis.timeline_interpretation": "object",
        "analysis.timeline_interpretation.previous_context": "string",
        "analysis.timeline_interpretation.status_reason": "string",
        "analysis.timeline_interpretation.open_item_annotations": "list[object]",
        "analysis.timeline_interpretation.open_item_annotations[].open_item_id": "string",
        "analysis.timeline_interpretation.open_item_annotations[].item": "string",
        "analysis.timeline_interpretation.evidence_sources": "list[string]",
        "analysis.risk_flags": "list[object]",
        "analysis.risk_flags[].type": "enum_string",
        "analysis.risk_flags[].level": "enum_string",
        "analysis.risk_flags[].evidence": "string",
        "analysis.risk_flags[].recommendation": "string",
        "analysis.suggested_actions": "list[object]",
        "analysis.suggested_actions[].type": "enum_string",
        "analysis.suggested_actions[].description": "string",
        "analysis.suggested_actions[].owner_hint": "string",
        "analysis.suggested_actions[].due_hint": "string",
        "analysis.reply_draft": "object",
        "analysis.reply_draft.subject": "string",
        "analysis.reply_draft.body": "string",
        "analysis.reply_draft.needs_human_review": "boolean_true",
        "analysis.reply_draft.review_reasons": "list[string]",
        "attachment_augmentations": "list[object]",
        "attachment_augmentations[].source_id": "string",
        "attachment_augmentations[].summary": "string",
        "attachment_augmentations[].key_facts": "list[string]",
        "attachment_augmentations[].evidence_sources": "list[string]",
        "field_evidence": "object[string,list[string]]",
    }
)

ENUM_FIELDS = MappingProxyType(
    {
        "analysis.priority": tuple(sorted(PRIORITIES)),
        "analysis.category": tuple(sorted(CATEGORIES)),
        "analysis.decision_brief.reply_recommendation.reply_type": tuple(
            sorted(DECISION_REPLY_TYPES)
        ),
        "analysis.decision_brief.confidence": tuple(sorted(CONFIDENCE_LEVELS)),
        "analysis.risk_flags[].type": tuple(sorted(RISK_TYPES)),
        "analysis.risk_flags[].level": tuple(sorted(RISK_LEVELS)),
        "analysis.suggested_actions[].type": tuple(sorted(ACTION_TYPES)),
    }
)

EMPTY_LIST_FIELDS = (
    "analysis.tags",
    "analysis.decision_brief.key_facts",
    "analysis.decision_brief.must_check",
    "analysis.decision_brief.missing_info",
    "analysis.timeline_interpretation.open_item_annotations",
    "analysis.timeline_interpretation.evidence_sources",
    "analysis.risk_flags",
    "analysis.suggested_actions",
    "analysis.reply_draft.review_reasons",
    "attachment_augmentations",
    "attachment_augmentations[].key_facts",
    "attachment_augmentations[].evidence_sources",
)

APPROVED_EVIDENCE_PATTERNS = frozenset(
    {
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
        ("analysis", "reply_draft", "subject"),
        ("analysis", "reply_draft", "body"),
        ("analysis", "reply_draft", "review_reasons", "*"),
        ("attachment_augmentations", "*", "summary"),
        ("attachment_augmentations", "*", "key_facts", "*"),
    }
)


def complete_envelope_example() -> dict[str, object]:
    """Return a fresh, structurally complete neutral synthetic envelope."""
    return copy.deepcopy(
        {
            "schema_version": SCHEMA_VERSION,
            "analysis": {
                "summary": "示例摘要。", "priority": "normal",
                "priority_reason": "需要人工核查当前请求。", "category": "unknown",
                "tags": [],
                "decision_brief": {
                    "one_line_conclusion": "核查当前请求。",
                    "requested_outcome": "确认下一步。",
                    "next_steps": [{
                        "step": "人工核查当前请求。", "owner_hint": "",
                        "due_hint": "", "source": "thread:0",
                    }],
                    "key_facts": [{
                        "label": "来源", "value": "当前可见会话", "source": "thread:0",
                    }],
                    "must_check": [], "missing_info": [],
                    "reply_recommendation": {
                        "should_reply": True, "reply_type": "acknowledge",
                        "reason": "建议人工确认后回复。",
                    },
                    "confidence": "low",
                },
                "timeline_interpretation": {
                    "previous_context": "", "status_reason": "",
                    "open_item_annotations": [], "evidence_sources": ["thread:0"],
                },
                "risk_flags": [{
                    "type": "delivery_risk", "level": "low",
                    "evidence": "示例请求需要人工核查。",
                    "recommendation": "确认后再回复。",
                }],
                "suggested_actions": [{
                    "type": "confirm", "description": "人工核查当前请求。",
                    "owner_hint": "", "due_hint": "",
                }],
                "reply_draft": {
                    "subject": "Re: Synthetic request",
                    "body": "Thank you. We will review the request.",
                    "needs_human_review": True,
                    "review_reasons": ["发送前必须人工核查。"],
                },
            },
            "attachment_augmentations": [],
            "field_evidence": {"/analysis/summary": ["thread:0"]},
        }
    )


def complete_envelope_example_json() -> str:
    return json.dumps(
        complete_envelope_example(), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    )


def render_analysis_contract() -> str:
    """Render the exact private contract deterministically for the system prompt."""
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "objects": {
            path: {
                field: FIELD_TYPES[
                    field if path == "envelope" else f"{path}.{field}"
                ]
                for field in sorted(fields)
            }
            for path, fields in OBJECT_FIELD_SETS.items()
        },
        "enums": {path: list(values) for path, values in ENUM_FIELDS.items()},
        "rules": {
            "no_extra_keys": True,
            "null_allowed": False,
            "deidentification_placeholders": "forbidden_in_output",
            "exact_identifiers_and_dates": (
                "generic_model_reference_backend_verified_only"
            ),
            "analysis.decision_brief.next_steps": "1..4",
            "analysis.reply_draft.needs_human_review": True,
            "empty_lists_allowed_only": list(EMPTY_LIST_FIELDS),
            "source_ids": "request_local_only",
            "open_item_annotations": "supplied_ids_only_or_empty",
            "attachment_augmentations": "parsed_supplied_ids_only_or_empty",
            "field_evidence_targets": [
                "/" + "/".join(pattern)
                for pattern in sorted(APPROVED_EVIDENCE_PATTERNS)
            ],
            "field_evidence_sources": "nonempty_request_local_ids",
        },
    }
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
