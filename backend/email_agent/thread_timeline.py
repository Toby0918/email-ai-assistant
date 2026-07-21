"""Deterministic reconstruction of the visible current-email conversation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .thread_dates import unambiguous_due_hint
from .thread_participants import classify_participant
from .thread_outcomes import track_request_states
from .thread_requests import (
    extract_outcome_atoms,
    extract_request_atoms,
    merge_request_atom_sources,
)
from .thread_segments import normalize_and_order_segments


_MAX_SIGNAL_CHARS = 2_600
_MAX_FACTUAL_OPEN_ITEMS = 19
_COMMITMENT_RE = re.compile(
    r"\b(will|plan|expect|arrange|follow up)\b|将|计划|预计|尽快|安排",
    re.IGNORECASE,
)
_QUOTE_REQUEST_RE = re.compile(r"\b(rfq|quote|quotation)\b|报价|询价", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ThreadSource:
    source_id: str
    sender: str
    recipient: str
    timestamp_text: str
    subject: str
    body: str


@dataclass(frozen=True, slots=True)
class TimelineOpenItem:
    open_item_id: str
    item: str
    owner_hint: str
    due_hint: str
    source: str
    evidence_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TimelineBuild:
    public_timeline: dict[str, object]
    open_items: tuple[TimelineOpenItem, ...]
    sources: tuple[ThreadSource, ...]
    current_source_id: str | None = None
    coverage_complete: bool = True


def build_conversation_timeline(
    segments: list[dict[str, str]], internal_domains: tuple[str, ...]
) -> dict[str, object]:
    """Summarize only the supplied visible thread segments into seven fields."""
    return build_timeline_skeleton(segments, internal_domains).public_timeline


def build_timeline_skeleton(
    segments: list[object], internal_domains: tuple[str, ...], *,
    trusted_current_segment: object | None = None,
) -> TimelineBuild:
    """Build the public timeline plus request-local factual source membership."""
    ordered, timestamps_reliable, coverage_complete, current_appended = (
        normalize_and_order_segments(
        segments, trusted_current_segment=trusted_current_segment
        )
    )
    domains = _normalize_domains(internal_domains)
    sources = tuple(_thread_source(segment, index) for index, segment in enumerate(ordered))
    events = [
        _extract_event(segment, domains, source.source_id)
        for segment, source in zip(ordered, sources)
    ]
    public_timeline, open_items, coverage_complete = _summarize_progress(
        events, timestamps_reliable, coverage_complete
    )
    current_source_id = sources[-1].source_id if current_appended and sources else None
    return TimelineBuild(public_timeline, open_items, sources, current_source_id, coverage_complete)


def _thread_source(segment: dict[str, object], index: int) -> ThreadSource:
    return ThreadSource(
        source_id=f"thread:{index}",
        sender=str(segment["sender"]),
        recipient=str(segment["recipient"]),
        timestamp_text=str(segment["timestamp_text"]),
        subject=str(segment["subject"]),
        body=str(segment["body"]),
    )


def _extract_event(
    segment: dict[str, object], internal_domains: tuple[str, ...], source_id: str
) -> dict[str, object]:
    subject = str(segment["subject"])
    body = str(segment["body"])
    signal_text = _combine_text(subject, body, "\n")[:_MAX_SIGNAL_CHARS]
    role, participant_complete = classify_participant(
        str(segment["sender"]), internal_domains
    )
    request_atoms, coverage_complete = (
        _external_request_atoms(subject, body, source_id)
        if role != "internal"
        else ((), True)
    )
    return {
        "display_text": _combine_text(subject, body, "；"),
        "role": role,
        "request_atoms": request_atoms,
        "request_coverage_complete": coverage_complete and participant_complete,
        "outcome_atoms": extract_outcome_atoms(signal_text) if role == "internal" else (),
        "commitment": role == "internal" and _COMMITMENT_RE.search(signal_text) is not None,
    }


def _external_request_atoms(
    subject: str, body: str, source_id: str
) -> tuple[tuple[dict[str, object], ...], bool]:
    subject_atoms, subject_complete = extract_request_atoms(
        subject, unambiguous_due_hint(subject)
    )
    body_atoms, body_complete = extract_request_atoms(body, unambiguous_due_hint(body))
    merged, merge_complete = merge_request_atom_sources(subject_atoms, body_atoms)
    sourced = tuple({**atom, "source_id": source_id} for atom in merged)
    return sourced, subject_complete and body_complete and merge_complete


def _summarize_progress(
    events: list[dict[str, object]],
    timestamps_reliable: bool,
    segment_coverage_complete: bool,
) -> tuple[dict[str, object], tuple[TimelineOpenItem, ...], bool]:
    if not events:
        return (*_unknown_timeline(segment_coverage_complete), segment_coverage_complete)

    commitments = [event for event in events if event["commitment"]]
    request_states, request_coverage_complete = track_request_states(events)
    coverage_complete = segment_coverage_complete and request_coverage_complete
    pending = [state for state in request_states if not state["resolved"]]
    resolved_count = len(request_states) - len(pending)
    blocked_count = sum(1 for state in pending if state["blocked"])
    selected_state = pending[-1] if pending else (request_states[-1] if request_states else None)
    selected_request = selected_state["event"] if selected_state is not None else None
    status, status_reason, open_items, open_item_coverage_complete = _status_and_open_items(
        request_states,
        pending,
        resolved_count,
        blocked_count,
        coverage_complete,
    )
    identifier = _event_identifier(selected_request)
    if identifier:
        status_reason = f"{status_reason} 关联标识：{identifier}。"

    public_timeline = {
        "previous_context": _previous_context(events),
        "current_status": status,
        "status_reason": status_reason,
        "latest_external_request": _event_statement("外部请求", selected_request),
        "latest_internal_commitment": _event_statement("内部将跟进", commitments[-1] if commitments else None),
        "open_items": _public_open_items(open_items),
        "confidence": (
            "high"
            if timestamps_reliable and coverage_complete and open_item_coverage_complete
            else "low"
        ),
    }
    return public_timeline, open_items, coverage_complete and open_item_coverage_complete


def _status_and_open_items(
    request_states: list[dict[str, object]],
    pending: list[dict[str, object]],
    resolved_count: int,
    blocked_count: int,
    coverage_complete: bool,
) -> tuple[str, str, tuple[TimelineOpenItem, ...], bool]:
    if not coverage_complete:
        reason = "部分会话内容或外部请求因安全限制被省略，需人工复核后再判断状态。"
        status = "unresolved" if request_states else "unknown"
        return status, reason, (_coverage_open_item(0),), False
    if pending:
        status = "partially_resolved" if resolved_count else "unresolved"
        reason = f"已明确完成{resolved_count}项，仍有{len(pending)}项外部请求待处理。"
        if blocked_count:
            reason = f"{reason} 其中{blocked_count}项存在阻塞。"
        factual = tuple(
            _request_open_item(index, _event_dict(state["event"]))
            for index, state in enumerate(pending[:_MAX_FACTUAL_OPEN_ITEMS])
        )
        if len(pending) > _MAX_FACTUAL_OPEN_ITEMS:
            return status, reason, (*factual, _coverage_open_item(len(factual))), False
        return status, reason, factual, True
    if request_states:
        return "resolved", "所有已识别外部请求均有匹配的明确完成结果。", (), True
    return "unknown", "未跟踪到外部请求，无法判断事项状态。", (), True


def _unknown_timeline(
    coverage_complete: bool,
) -> tuple[dict[str, object], tuple[TimelineOpenItem, ...]]:
    _, status_reason, open_items, _ = _status_and_open_items(
        [], [], 0, 0, coverage_complete
    )
    public_timeline = {
        "previous_context": "未识别可用会话信息。",
        "current_status": "unknown",
        "status_reason": status_reason,
        "latest_external_request": "",
        "latest_internal_commitment": "",
        "open_items": _public_open_items(open_items),
        "confidence": "low",
    }
    return public_timeline, open_items


def _request_open_item(index: int, event: dict[str, object]) -> TimelineOpenItem:
    signal_text = str(event["signal_text"])
    return TimelineOpenItem(
        open_item_id=f"open:{index}",
        item=f"处理外部请求：{_excerpt(str(event['display_text']))}",
        owner_hint="internal_sales" if _QUOTE_REQUEST_RE.search(signal_text) else "internal_follow_up",
        due_hint=str(event["due_hint"]),
        source="thread",
        evidence_sources=(str(event["source_id"]),),
    )


def _coverage_open_item(index: int) -> TimelineOpenItem:
    return TimelineOpenItem(
        open_item_id=f"open:{index}",
        item="部分会话内容或外部请求被省略，请人工复核完整会话。",
        owner_hint="internal_follow_up",
        due_hint="",
        source="thread",
        evidence_sources=(),
    )


def _public_open_items(items: tuple[TimelineOpenItem, ...]) -> list[dict[str, str]]:
    return [
        {
            "item": item.item,
            "owner_hint": item.owner_hint,
            "due_hint": item.due_hint,
            "source": item.source,
        }
        for item in items
    ]


def _previous_context(events: list[dict[str, object]]) -> str:
    roles: list[str] = []
    if any(event["role"] == "external" for event in events):
        roles.append("外部往来")
    if any(event["role"] == "internal" for event in events):
        roles.append("内部跟进")
    detail = "和".join(roles) if roles else "会话往来"
    return f"已整理{len(events)}条可用会话，包含{detail}。"


def _event_statement(label: str, event: object) -> str:
    if not isinstance(event, dict):
        return ""
    return f"{label}：{_excerpt(str(event['display_text']))}"


def _event_identifier(event: object) -> str:
    if not isinstance(event, dict):
        return ""
    identifiers = event["identifiers"]
    return str(identifiers[0]) if identifiers else ""


def _event_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _normalize_domains(internal_domains: object) -> tuple[str, ...]:
    if not isinstance(internal_domains, tuple):
        return ()
    return tuple(
        domain[:256].strip().lower()
        for domain in internal_domains
        if isinstance(domain, str) and domain[:256].strip()
    )


def _combine_text(subject: str, body: str, separator: str) -> str:
    return separator.join(part for part in (subject, body) if part)


def _excerpt(text: str, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]
