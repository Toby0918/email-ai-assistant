"""Deterministic reconstruction of the visible current-email conversation."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .email_cleaner import clean_thread_segment_text


_ADDRESS_RE = re.compile(r"[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)
_REQUEST_RE = re.compile(
    r"\b(rfq|quote|quotation|please|could you|need|confirm|provide|request)\b|请|麻烦|需要|报价|询价|确认|提供",
    re.IGNORECASE,
)
_COMMITMENT_RE = re.compile(r"\b(will|plan|expect|arrange|follow up)\b|将|计划|预计|尽快|安排", re.IGNORECASE)
_OUTCOME_RE = re.compile(
    r"\b(resolved|completed|closed|has been sent|delivered)\b|已(?:解决|完成|关闭|发送|处理完成)",
    re.IGNORECASE,
)
_BLOCKER_RE = re.compile(r"\b(blocked|pending|unable|missing)\b|无法|缺少|待确认|阻塞", re.IGNORECASE)
_QUOTE_REQUEST_RE = re.compile(r"\b(rfq|quote|quotation)\b|报价|询价", re.IGNORECASE)
_DATE_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)|\d{1,2}月\d{1,2}日(?:前)?|(?:周[一二三四五六日天]|明天)(?:前)?")
_IDENTIFIER_RE = re.compile(r"\b(?:RFQ|PO|SO)[#:-]?[A-Z0-9-]{2,}\b|(?:订单号|编号)\s*[:：#-]?\s*[A-Z0-9-]{2,}", re.IGNORECASE)
_TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S")


def build_conversation_timeline(
    segments: list[dict[str, str]], internal_domains: tuple[str, ...]
) -> dict[str, object]:
    """Summarize only the supplied visible thread segments into seven fields."""
    normalized = _deduplicate_and_clean(segments)
    ordered, timestamps_reliable = _order_segments(normalized)
    events = [_extract_event(segment, _normalize_domains(internal_domains)) for segment in ordered]
    return _summarize_progress(events, timestamps_reliable)


def _deduplicate_and_clean(segments: object) -> list[dict[str, object]]:
    if not isinstance(segments, list):
        return []

    normalized: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for index, raw_segment in enumerate(segments):
        if not isinstance(raw_segment, dict):
            continue
        body_text = _string_value(raw_segment, "body_text")
        body_html = _string_value(raw_segment, "body_html")
        body = clean_thread_segment_text(body_text=body_text, body_html=body_html)
        if not body:
            continue
        sender = _string_value(raw_segment, "from")
        recipient = _string_value(raw_segment, "to")
        timestamp_text = _string_value(raw_segment, "sent_at") or _string_value(raw_segment, "timestamp_text")
        subject = _string_value(raw_segment, "subject")
        fingerprint = (sender.lower(), recipient.lower(), timestamp_text, subject.lower(), body)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        normalized.append(
            {
                "body": body,
                "sender": sender,
                "timestamp_text": timestamp_text,
                "position": _position_value(raw_segment.get("position"), index),
                "index": index,
            }
        )
    return normalized


def _order_segments(segments: list[dict[str, object]]) -> tuple[list[dict[str, object]], bool]:
    for segment in segments:
        segment["timestamp"] = _parse_timestamp(segment["timestamp_text"])
    timestamps_reliable = bool(segments) and all(segment["timestamp"] is not None for segment in segments)
    if timestamps_reliable:
        return sorted(segments, key=lambda segment: (segment["timestamp"], segment["position"], segment["index"])), True
    return sorted(segments, key=lambda segment: (segment["position"], segment["index"])), False


def _extract_event(segment: dict[str, object], internal_domains: tuple[str, ...]) -> dict[str, object]:
    body = str(segment["body"])
    role = _participant_role(str(segment["sender"]), internal_domains)
    return {
        "body": body,
        "role": role,
        "request": role == "external" and _REQUEST_RE.search(body) is not None,
        "commitment": role == "internal" and _COMMITMENT_RE.search(body) is not None,
        "outcome": _OUTCOME_RE.search(body) is not None,
        "blocker": _BLOCKER_RE.search(body) is not None,
        "due_hint": _match_text(_DATE_RE, body),
        "identifier": _match_text(_IDENTIFIER_RE, body),
    }


def _summarize_progress(events: list[dict[str, object]], timestamps_reliable: bool) -> dict[str, object]:
    if not events:
        return _unknown_timeline()

    requests = [event for event in events if event["request"]]
    commitments = [event for event in events if event["commitment"]]
    blockers = [event for event in events if event["blocker"]]
    outcomes = [event for event in events if event["outcome"]]
    latest_request_index = _latest_request_index(events)
    latest_request = events[latest_request_index] if latest_request_index is not None else None
    latest_outcome = outcomes[-1] if outcomes else None
    status, status_reason, open_items = _status_and_open_items(
        events,
        latest_request,
        latest_request_index,
        latest_outcome,
        outcomes,
        blockers,
        commitments,
    )

    identifier = _latest_identifier(events)
    if identifier:
        status_reason = f"{status_reason} 关联标识：{identifier}。"

    return {
        "previous_context": _previous_context(events),
        "current_status": status,
        "status_reason": status_reason,
        "latest_external_request": _event_statement("外部请求", latest_request),
        "latest_internal_commitment": _event_statement("内部将跟进", commitments[-1] if commitments else None),
        "open_items": open_items,
        "confidence": "high" if timestamps_reliable else "low",
    }


def _status_and_open_items(
    events: list[dict[str, object]],
    latest_request: dict[str, object] | None,
    latest_request_index: int | None,
    latest_outcome: dict[str, object] | None,
    outcomes: list[dict[str, object]],
    blockers: list[dict[str, object]],
    commitments: list[dict[str, object]],
) -> tuple[str, str, list[dict[str, str]]]:
    unresolved_request = (
        latest_request
        if latest_request_index is not None and not _outcome_after(events, latest_request_index)
        else None
    )

    if unresolved_request is not None:
        status = "partially_resolved" if outcomes else "unresolved"
        status_reason = "最新外部请求尚未见到明确完成结果。"
        open_items = [_request_open_item(unresolved_request)]
    elif latest_outcome is not None:
        status = "resolved"
        status_reason = "已识别明确完成结果，未见后续外部请求。"
        open_items = []
    elif blockers:
        status = "unresolved"
        status_reason = "发现待澄清阻塞问题，尚无明确完成结果。"
        open_items = [_blocker_open_item(blockers[-1])]
    elif commitments:
        status = "unresolved"
        status_reason = "已识别内部跟进承诺，尚无明确完成结果。"
        open_items = []
    else:
        status = "unknown"
        status_reason = "未识别明确请求、承诺或完成结果。"
        open_items = []
    return status, status_reason, open_items


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
    body = str(event["body"])
    return {
        "item": f"处理外部请求：{_excerpt(body)}",
        "owner_hint": "internal_sales" if _QUOTE_REQUEST_RE.search(body) else "internal_follow_up",
        "due_hint": str(event["due_hint"]),
        "source": "thread",
    }


def _blocker_open_item(event: dict[str, object]) -> dict[str, str]:
    return {
        "item": f"澄清阻塞问题：{_excerpt(str(event['body']))}",
        "owner_hint": "internal_follow_up",
        "due_hint": str(event["due_hint"]),
        "source": "thread",
    }


def _previous_context(events: list[dict[str, object]]) -> str:
    roles: list[str] = []
    if any(event["role"] == "external" for event in events):
        roles.append("外部请求")
    if any(event["role"] == "internal" for event in events):
        roles.append("内部跟进")
    detail = "和".join(roles) if roles else "会话往来"
    return f"已整理{len(events)}条可用会话，包含{detail}。"


def _latest_request_index(events: list[dict[str, object]]) -> int | None:
    for index in range(len(events) - 1, -1, -1):
        if events[index]["request"]:
            return index
    return None


def _outcome_after(events: list[dict[str, object]], request_index: int) -> bool:
    return any(event["outcome"] for event in events[request_index + 1 :])


def _event_statement(label: str, event: dict[str, object] | None) -> str:
    return f"{label}：{_excerpt(str(event['body']))}" if event is not None else ""


def _latest_identifier(events: list[dict[str, object]]) -> str:
    for event in reversed(events):
        identifier = str(event["identifier"])
        if identifier:
            return identifier
    return ""


def _participant_role(sender: str, internal_domains: tuple[str, ...]) -> str:
    match = _ADDRESS_RE.search(sender)
    if match is None:
        return "unknown"
    return "internal" if match.group(1).lower() in internal_domains else "external"


def _normalize_domains(internal_domains: object) -> tuple[str, ...]:
    if not isinstance(internal_domains, tuple):
        return ()
    return tuple(domain.strip().lower() for domain in internal_domains if isinstance(domain, str) and domain.strip())


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        return _normalize_timestamp(datetime.fromisoformat(candidate))
    except ValueError:
        for timestamp_format in _TIMESTAMP_FORMATS:
            try:
                return _normalize_timestamp(datetime.strptime(candidate, timestamp_format))
            except ValueError:
                continue
    return None


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _string_value(segment: dict[object, object], field: str) -> str:
    value = segment.get(field)
    return value.strip() if isinstance(value, str) else ""


def _position_value(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return default


def _match_text(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0) if match is not None else ""


def _excerpt(text: str, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]
