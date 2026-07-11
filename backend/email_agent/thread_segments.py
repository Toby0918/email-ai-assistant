"""Bound and order untrusted visible conversation segments."""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from .email_cleaner import clean_thread_segment_text_with_coverage


MAX_THREAD_SEGMENTS = 50
MAX_METADATA_CHARS = 512
MAX_POSITION_CHARS = 9
MAX_POSITION = 1_000_000

_EMAIL_TEXT = r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
_HEADER_FROM_RE = re.compile(
    rf"(?:^|\n)\s*(?:from|发件人)\s*[:：][^\n]*?(?P<email>{_EMAIL_TEXT})",
    re.IGNORECASE,
)


def normalize_and_order_segments(
    segments: object,
) -> tuple[list[dict[str, object]], bool, bool]:
    segment_count_complete = not isinstance(segments, list) or len(segments) <= MAX_THREAD_SEGMENTS
    normalized, text_coverage_complete = _normalize_segments(segments)
    ordered, timestamps_reliable = _order_segments(normalized)
    return ordered, timestamps_reliable, segment_count_complete and text_coverage_complete


def _normalize_segments(segments: object) -> tuple[list[dict[str, object]], bool]:
    if not isinstance(segments, list):
        return [], True

    normalized: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, str, int]] = set()
    coverage_complete = True
    for index, raw_segment in enumerate(segments[:MAX_THREAD_SEGMENTS]):
        segment, segment_complete = _normalize_segment(raw_segment, index)
        coverage_complete = coverage_complete and segment_complete
        if segment is None:
            continue
        if segment["position"] is not None:
            fingerprint = _fingerprint(segment)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
        normalized.append(segment)
    return normalized, coverage_complete


def _normalize_segment(
    raw_segment: object, index: int
) -> tuple[dict[str, object] | None, bool]:
    if not isinstance(raw_segment, dict):
        return None, True

    raw_text = raw_segment.get("body_text")
    raw_html = raw_segment.get("body_html")
    body, text_complete = clean_thread_segment_text_with_coverage(
        body_text=raw_text if isinstance(raw_text, str) else None,
        body_html=raw_html if isinstance(raw_html, str) else None,
    )
    subject, subject_complete = _bounded_field_with_coverage(raw_segment, "subject")
    header, header_complete = _bounded_field_with_coverage(raw_segment, "header_text")
    sender_field, sender_complete = _bounded_field_with_coverage(raw_segment, "from")
    metadata_complete = subject_complete and header_complete and sender_complete
    if not body and not subject:
        return None, text_complete and metadata_complete

    sender = sender_field or _sender_from_header(header)
    sent_at = _bounded_field(raw_segment, "sent_at")
    timestamp_text = _bounded_field(raw_segment, "timestamp_text")
    return {
        "body": body,
        "subject": subject,
        "sender": sender,
        "recipient": _bounded_field(raw_segment, "to"),
        "timestamp_text": sent_at or timestamp_text,
        "position": _position_value(raw_segment.get("position")),
        "index": index,
    }, text_complete and metadata_complete


def _fingerprint(segment: dict[str, object]) -> tuple[str, str, str, str, str, int]:
    return (
        str(segment["sender"]).lower(),
        str(segment["recipient"]).lower(),
        str(segment["timestamp_text"]),
        str(segment["subject"]).lower(),
        str(segment["body"]),
        int(segment["position"]),
    )


def _order_segments(segments: list[dict[str, object]]) -> tuple[list[dict[str, object]], bool]:
    for segment in segments:
        segment["timestamp"] = _parse_timestamp(segment["timestamp_text"])
    timestamps_reliable = bool(segments) and all(_is_aware(segment["timestamp"]) for segment in segments)
    if timestamps_reliable:
        return sorted(segments, key=lambda item: (item["timestamp"], item["index"])), True
    if segments and all(segment["position"] is not None for segment in segments):
        return sorted(segments, key=lambda item: (item["position"], item["index"])), False
    return segments, False


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        try:
            return parsedate_to_datetime(candidate)
        except (TypeError, ValueError):
            return None


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _bounded_field(segment: dict[object, object], field: str, limit: int = MAX_METADATA_CHARS) -> str:
    return _bounded_field_with_coverage(segment, field, limit)[0]


def _bounded_field_with_coverage(
    segment: dict[object, object], field: str, limit: int = MAX_METADATA_CHARS
) -> tuple[str, bool]:
    value = segment.get(field)
    if not isinstance(value, str):
        return "", True
    return value[:limit].strip(), len(value) <= limit


def _sender_from_header(header: str) -> str:
    match = _HEADER_FROM_RE.search(header)
    return match.group("email") if match is not None else ""


def _position_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= MAX_POSITION else None
    if not isinstance(value, str):
        return None
    candidate = value[:MAX_POSITION_CHARS].strip()
    if len(value) > MAX_POSITION_CHARS or not candidate.isascii() or not candidate.isdigit():
        return None
    parsed = int(candidate)
    return parsed if parsed <= MAX_POSITION else None
