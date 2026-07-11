"""Deterministic reconstruction of the visible current-email conversation."""

from __future__ import annotations

import re

from .thread_participants import participant_role
from .thread_outcomes import track_request_states
from .thread_requests import (
    extract_outcome_atoms,
    extract_request_atoms,
    merge_request_atom_sources,
)
from .thread_segments import normalize_and_order_segments


_MAX_SIGNAL_CHARS = 2_600
_COMMITMENT_RE = re.compile(
    r"\b(will|plan|expect|arrange|follow up)\b|将|计划|预计|尽快|安排",
    re.IGNORECASE,
)
_QUOTE_REQUEST_RE = re.compile(r"\b(rfq|quote|quotation)\b|报价|询价", re.IGNORECASE)
_DATE_RE = re.compile(
    r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)|\d{1,2}月\d{1,2}日(?:前)?|(?:周[一二三四五六日天]|明天)(?:前)?"
)
def build_conversation_timeline(
    segments: list[dict[str, str]], internal_domains: tuple[str, ...]
) -> dict[str, object]:
    """Summarize only the supplied visible thread segments into seven fields."""
    ordered, timestamps_reliable, segment_coverage_complete = normalize_and_order_segments(segments)
    domains = _normalize_domains(internal_domains)
    events = [_extract_event(segment, domains) for segment in ordered]
    return _summarize_progress(events, timestamps_reliable, segment_coverage_complete)


def _extract_event(segment: dict[str, object], internal_domains: tuple[str, ...]) -> dict[str, object]:
    subject = str(segment["subject"])
    body = str(segment["body"])
    signal_text = _combine_text(subject, body, "\n")[:_MAX_SIGNAL_CHARS]
    role = participant_role(str(segment["sender"]), internal_domains)
    due_hint = _match_text(_DATE_RE, signal_text)
    request_atoms, coverage_complete = (
        _external_request_atoms(subject, body, due_hint) if role == "external" else ((), True)
    )
    return {
        "display_text": _combine_text(subject, body, "；"),
        "role": role,
        "request_atoms": request_atoms,
        "request_coverage_complete": coverage_complete,
        "outcome_atoms": extract_outcome_atoms(signal_text) if role == "internal" else (),
        "commitment": role == "internal" and _COMMITMENT_RE.search(signal_text) is not None,
    }


def _external_request_atoms(
    subject: str, body: str, due_hint: str
) -> tuple[tuple[dict[str, object], ...], bool]:
    subject_atoms, subject_complete = extract_request_atoms(subject, due_hint)
    body_atoms, body_complete = extract_request_atoms(body, due_hint)
    merged, merge_complete = merge_request_atom_sources(subject_atoms, body_atoms)
    return merged, subject_complete and body_complete and merge_complete


def _summarize_progress(
    events: list[dict[str, object]],
    timestamps_reliable: bool,
    segment_coverage_complete: bool,
) -> dict[str, object]:
    if not events:
        return _unknown_timeline(segment_coverage_complete)

    commitments = [event for event in events if event["commitment"]]
    request_states, request_coverage_complete = track_request_states(events)
    coverage_complete = segment_coverage_complete and request_coverage_complete
    pending = [state for state in request_states if not state["resolved"]]
    resolved_count = len(request_states) - len(pending)
    blocked_count = sum(1 for state in pending if state["blocked"])
    selected_state = pending[-1] if pending else (request_states[-1] if request_states else None)
    selected_request = selected_state["event"] if selected_state is not None else None
    status, status_reason, open_items = _status_and_open_items(
        request_states,
        pending,
        resolved_count,
        blocked_count,
        selected_request,
        coverage_complete,
    )
    identifier = _event_identifier(selected_request)
    if identifier:
        status_reason = f"{status_reason} 关联标识：{identifier}。"

    return {
        "previous_context": _previous_context(events),
        "current_status": status,
        "status_reason": status_reason,
        "latest_external_request": _event_statement("外部请求", selected_request),
        "latest_internal_commitment": _event_statement("内部将跟进", commitments[-1] if commitments else None),
        "open_items": open_items,
        "confidence": "high" if timestamps_reliable and coverage_complete else "low",
    }


def _status_and_open_items(
    request_states: list[dict[str, object]],
    pending: list[dict[str, object]],
    resolved_count: int,
    blocked_count: int,
    selected_request: object,
    coverage_complete: bool,
) -> tuple[str, str, list[dict[str, str]]]:
    if not coverage_complete:
        reason = "部分会话内容或外部请求因安全限制被省略，需人工复核后再判断状态。"
        status = "unresolved" if request_states else "unknown"
        return status, reason, [_coverage_open_item()]
    if pending:
        status = "partially_resolved" if resolved_count else "unresolved"
        reason = f"已明确完成{resolved_count}项，仍有{len(pending)}项外部请求待处理。"
        if blocked_count:
            reason = f"{reason} 其中{blocked_count}项存在阻塞。"
        return status, reason, [_request_open_item(_event_dict(selected_request))]
    if request_states:
        return "resolved", "所有已识别外部请求均有匹配的明确完成结果。", []
    return "unknown", "未跟踪到外部请求，无法判断事项状态。", []


def _unknown_timeline(coverage_complete: bool) -> dict[str, object]:
    _, status_reason, open_items = _status_and_open_items(
        [], [], 0, 0, None, coverage_complete
    )
    return {
        "previous_context": "未识别可用会话信息。",
        "current_status": "unknown",
        "status_reason": status_reason,
        "latest_external_request": "",
        "latest_internal_commitment": "",
        "open_items": open_items,
        "confidence": "low",
    }


def _request_open_item(event: dict[str, object]) -> dict[str, str]:
    signal_text = str(event["signal_text"])
    return {
        "item": f"处理外部请求：{_excerpt(str(event['display_text']))}",
        "owner_hint": "internal_sales" if _QUOTE_REQUEST_RE.search(signal_text) else "internal_follow_up",
        "due_hint": str(event["due_hint"]),
        "source": "thread",
    }


def _coverage_open_item() -> dict[str, str]:
    return {
        "item": "部分会话内容或外部请求被省略，请人工复核完整会话。",
        "owner_hint": "internal_follow_up",
        "due_hint": "",
        "source": "thread",
    }


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


def _match_text(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0) if match is not None else ""


def _excerpt(text: str, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]
