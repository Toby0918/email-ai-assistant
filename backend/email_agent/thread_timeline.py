"""Deterministic reconstruction of the visible current-email conversation."""

from __future__ import annotations

import re

from .thread_requests import (
    extract_identifiers,
    extract_request_atoms,
    extract_topics,
    track_request_states,
)
from .thread_segments import normalize_and_order_segments


_MAX_SIGNAL_CHARS = 2_600
_ADDRESS_RE = re.compile(
    r"[A-Z0-9._%+-]+@(?P<domain>[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)
_COMMITMENT_RE = re.compile(
    r"\b(will|plan|expect|arrange|follow up)\b|将|计划|预计|尽快|安排",
    re.IGNORECASE,
)
_OUTCOME_RE = re.compile(
    r"\b(resolved|completed|closed|has been sent|delivered)\b|已(?:解决|完成|关闭|发送|处理完成)",
    re.IGNORECASE,
)
_BLOCKER_RE = re.compile(
    r"\b(blocked|pending|unable|missing)\b|无法|缺少|待确认|阻塞",
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
    ordered, timestamps_reliable = normalize_and_order_segments(segments)
    domains = _normalize_domains(internal_domains)
    events = [_extract_event(segment, domains) for segment in ordered]
    return _summarize_progress(events, timestamps_reliable)


def _extract_event(segment: dict[str, object], internal_domains: tuple[str, ...]) -> dict[str, object]:
    subject = str(segment["subject"])
    body = str(segment["body"])
    signal_text = _combine_text(subject, body, "\n")[:_MAX_SIGNAL_CHARS]
    role = _participant_role(str(segment["sender"]), internal_domains)
    due_hint = _match_text(_DATE_RE, signal_text)
    return {
        "display_text": _combine_text(subject, body, "；"),
        "signal_text": signal_text,
        "role": role,
        "request_atoms": extract_request_atoms(signal_text, due_hint) if role == "external" else (),
        "commitment": role == "internal" and _COMMITMENT_RE.search(signal_text) is not None,
        "outcome": _OUTCOME_RE.search(signal_text) is not None,
        "blocker": _BLOCKER_RE.search(signal_text) is not None,
        "due_hint": due_hint,
        "identifiers": extract_identifiers(signal_text),
        "topics": extract_topics(signal_text),
    }


def _summarize_progress(events: list[dict[str, object]], timestamps_reliable: bool) -> dict[str, object]:
    if not events:
        return _unknown_timeline()

    commitments = [event for event in events if event["commitment"]]
    request_states = track_request_states(events)
    pending = [state for state in request_states if not state["resolved"]]
    resolved_count = len(request_states) - len(pending)
    selected_state = pending[-1] if pending else (request_states[-1] if request_states else None)
    selected_request = selected_state["event"] if selected_state is not None else None
    status, status_reason, open_items = _status_and_open_items(
        request_states,
        pending,
        resolved_count,
        selected_request,
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
        "confidence": "high" if timestamps_reliable else "low",
    }


def _status_and_open_items(
    request_states: list[dict[str, object]],
    pending: list[dict[str, object]],
    resolved_count: int,
    selected_request: object,
) -> tuple[str, str, list[dict[str, str]]]:
    if pending:
        status = "partially_resolved" if resolved_count else "unresolved"
        reason = f"已明确完成{resolved_count}项，仍有{len(pending)}项外部请求待处理。"
        return status, reason, [_request_open_item(_event_dict(selected_request))]
    if request_states:
        return "resolved", "所有已识别外部请求均有匹配的明确完成结果。", []
    return "unknown", "未跟踪到外部请求，无法判断事项状态。", []


def _unknown_timeline() -> dict[str, object]:
    return {
        "previous_context": "未识别可用会话信息。",
        "current_status": "unknown",
        "status_reason": "未识别可用会话内容。",
        "latest_external_request": "",
        "latest_internal_commitment": "",
        "open_items": [],
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


def _participant_role(sender: str, internal_domains: tuple[str, ...]) -> str:
    match = _ADDRESS_RE.search(sender)
    if match is None:
        return "unknown"
    return "internal" if match.group("domain").lower() in internal_domains else "external"


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
