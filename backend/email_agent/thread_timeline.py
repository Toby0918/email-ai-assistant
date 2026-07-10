"""Deterministic reconstruction of the visible current-email conversation."""

from __future__ import annotations

import re

from .thread_segments import normalize_and_order_segments


_MAX_SIGNAL_CHARS = 2_600
_ADDRESS_RE = re.compile(
    r"[A-Z0-9._%+-]+@(?P<domain>[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)
_REQUEST_RE = re.compile(
    r"\b(rfq|quote|quotation|please|could you|need|confirm|provide|request)\b|请|麻烦|需要|报价|询价|确认|提供",
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
_IDENTIFIER_RE = re.compile(
    r"(?<![A-Z0-9])(?:RFQ|PO|SO)[#:-]?[A-Z0-9-]{2,}(?![A-Z0-9-])|"
    r"(?:订单号|编号)\s*[:：#-]?\s*[A-Z0-9-]{2,}",
    re.IGNORECASE,
)
_TOPIC_PATTERNS = (
    ("quotation", re.compile(r"\b(rfq|quote|quotation|pricing)\b|报价|询价|价格", re.IGNORECASE)),
    ("certificate", re.compile(r"\b(certificate|certification)\b|证书|认证", re.IGNORECASE)),
    ("shipment", re.compile(r"\b(shipment|delivery|eta|dispatch)\b|交期|发货|出货", re.IGNORECASE)),
    ("sample", re.compile(r"\bsample\b|样品", re.IGNORECASE)),
    ("quantity", re.compile(r"\b(quantity|qty)\b|数量", re.IGNORECASE)),
    ("invoice", re.compile(r"\binvoice\b|发票", re.IGNORECASE)),
    ("payment", re.compile(r"\bpayment\b|付款|支付", re.IGNORECASE)),
    ("contract", re.compile(r"\bcontract\b|合同", re.IGNORECASE)),
    ("order", re.compile(r"\border\b|订单", re.IGNORECASE)),
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
    return {
        "display_text": _combine_text(subject, body, "；"),
        "signal_text": signal_text,
        "role": role,
        "request": role == "external" and _REQUEST_RE.search(signal_text) is not None,
        "commitment": role == "internal" and _COMMITMENT_RE.search(signal_text) is not None,
        "outcome": _OUTCOME_RE.search(signal_text) is not None,
        "blocker": _BLOCKER_RE.search(signal_text) is not None,
        "due_hint": _match_text(_DATE_RE, signal_text),
        "identifiers": _extract_identifiers(signal_text),
        "topics": _extract_topics(signal_text),
    }


def _summarize_progress(events: list[dict[str, object]], timestamps_reliable: bool) -> dict[str, object]:
    if not events:
        return _unknown_timeline()

    commitments = [event for event in events if event["commitment"]]
    blockers = [event for event in events if event["blocker"]]
    outcomes = [event for event in events if event["outcome"]]
    request_states = _track_requests(events)
    pending = [state for state in request_states if not state["resolved"]]
    resolved_count = len(request_states) - len(pending)
    selected_state = pending[-1] if pending else (request_states[-1] if request_states else None)
    selected_request = selected_state["event"] if selected_state is not None else None
    status, status_reason, open_items = _status_and_open_items(
        request_states,
        pending,
        resolved_count,
        selected_request,
        outcomes,
        blockers,
        commitments,
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
    outcomes: list[dict[str, object]],
    blockers: list[dict[str, object]],
    commitments: list[dict[str, object]],
) -> tuple[str, str, list[dict[str, str]]]:
    if pending:
        status = "partially_resolved" if resolved_count else "unresolved"
        reason = f"已明确完成{resolved_count}项，仍有{len(pending)}项外部请求待处理。"
        return status, reason, [_request_open_item(_event_dict(selected_request))]
    if request_states:
        return "resolved", "所有已识别外部请求均有匹配的明确完成结果。", []
    if outcomes:
        return "resolved", "已识别明确完成结果，未发现待处理外部请求。", []
    if blockers:
        return "unresolved", "发现待澄清阻塞问题，尚无明确完成结果。", [_blocker_open_item(blockers[-1])]
    if commitments:
        return "unresolved", "已识别内部跟进承诺，尚无明确完成结果。", []
    return "unknown", "未识别明确请求、承诺或完成结果。", []


def _track_requests(events: list[dict[str, object]]) -> list[dict[str, object]]:
    states: list[dict[str, object]] = []
    for event in events:
        if event["outcome"]:
            matching_index = _matching_request_index(states, event)
            if matching_index is not None:
                states[matching_index]["resolved"] = True
        if event["request"]:
            states.append({"event": event, "resolved": False})
    return states


def _matching_request_index(
    states: list[dict[str, object]], outcome: dict[str, object]
) -> int | None:
    candidates = [index for index, state in enumerate(states) if not state["resolved"]]
    outcome_identifiers = set(outcome["identifiers"])
    if outcome_identifiers:
        matches = [
            index
            for index in candidates
            if outcome_identifiers.intersection(_event_dict(states[index]["event"])["identifiers"])
        ]
        return matches[0] if len(matches) == 1 else None
    outcome_topics = set(outcome["topics"])
    if not outcome_topics:
        return None
    matches = [
        index
        for index in candidates
        if outcome_topics.intersection(_event_dict(states[index]["event"])["topics"])
    ]
    return matches[0] if len(matches) == 1 else None


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


def _blocker_open_item(event: dict[str, object]) -> dict[str, str]:
    return {
        "item": f"澄清阻塞问题：{_excerpt(str(event['display_text']))}",
        "owner_hint": "internal_follow_up",
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


def _extract_identifiers(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).upper() for match in _IDENTIFIER_RE.finditer(text))


def _extract_topics(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in _TOPIC_PATTERNS if pattern.search(text))


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
