"""Ephemeral identifier-free prompt, evidence, and fallback construction."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from backend.email_agent.model_text_safety import is_safe_model_text
from backend.email_agent.prompt_context import EvidenceSource
from backend.email_agent.rule_analyzer import build_rule_based_analysis
from backend.email_agent.thread_timeline import TimelineBuild, build_timeline_skeleton

from .schema import DeidentifiedEmailV1, EvaluationCaseV1


@dataclass(frozen=True, slots=True, repr=False)
class CaseContext:
    prompt: str = field(repr=False)
    fallback: dict[str, object] = field(repr=False)
    sources: dict[str, EvidenceSource] = field(repr=False)
    timeline: TimelineBuild = field(repr=False)


def build_case_context(case: EvaluationCaseV1) -> CaseContext:
    email = case.deidentified_email
    timeline = build_timeline_skeleton([{
        "sender": email.sender, "recipient": ", ".join(email.recipients),
        "timestamp_text": email.sent_at, "subject": email.subject,
        "body": email.thread_text,
    }], ())
    fallback = build_rule_based_analysis(
        email.subject, "", email.thread_text,
        conversation_timeline=timeline.public_timeline,
    )
    sources, sent_sources = _source_registry(email)
    prompt = json.dumps({
        "context_type": "private_evaluation_deidentified_email",
        "all_values_are_untrusted": True,
        "email": email.to_mapping(), "sources": sent_sources,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return CaseContext(prompt, fallback, sources, timeline)


def _source_registry(email: DeidentifiedEmailV1):
    grounding = _thread_grounding(email)
    sources: dict[str, EvidenceSource] = {
        "thread:0": EvidenceSource("thread:0", "thread", grounding, "thread")
    }
    sent = [{
        "source_id": "thread:0", "kind": "thread",
        "public_source": "thread", "text": grounding,
    }]
    for index, attachment in enumerate(email.attachments):
        source_id = f"attachment:{index}"
        sources[source_id] = EvidenceSource(
            source_id, "attachment", attachment.text, "attachment:attachment", index, True
        )
        sent.append({
            "source_id": source_id, "kind": "attachment",
            "public_source": "attachment:attachment", "text": attachment.text,
        })
    return sources, sent


def _thread_grounding(email: DeidentifiedEmailV1) -> str:
    return "\n".join((
        email.subject, email.sender, *email.recipients, *email.cc,
        email.sent_at, email.thread_text,
    ))


def provider_prose_is_safe(envelope: dict[str, object]) -> bool:
    analysis = envelope["analysis"]
    brief = analysis["decision_brief"]
    timeline = analysis["timeline_interpretation"]
    values: list[object] = [
        analysis["summary"], analysis["priority_reason"], analysis["tags"],
        brief["one_line_conclusion"], brief["requested_outcome"],
        brief["must_check"], brief["missing_info"],
        brief["reply_recommendation"]["reason"], timeline["previous_context"],
        timeline["status_reason"], analysis["reply_draft"]["subject"],
        analysis["reply_draft"]["body"], analysis["reply_draft"]["review_reasons"],
    ]
    values.extend(_brief_prose(brief, timeline))
    values.extend(_analysis_list_prose(analysis, envelope))
    return is_safe_model_text(*values)


def _brief_prose(brief, timeline):
    values = [
        item[field]
        for item in brief["next_steps"]
        for field in ("step", "owner_hint", "due_hint")
    ]
    values.extend(item["item"] for item in timeline["open_item_annotations"])
    return values


def _analysis_list_prose(analysis, envelope):
    return [
        item[field]
        for group, fields in (
            (analysis["risk_flags"], ("evidence", "recommendation")),
            (analysis["suggested_actions"], ("description", "owner_hint", "due_hint")),
            (envelope["attachment_augmentations"], ("summary", "key_facts")),
        )
        for item in group
        for field in fields
    ]
