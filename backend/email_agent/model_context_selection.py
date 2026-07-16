"""Select a bounded current-first model view without changing local timeline rules."""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import getaddresses
from typing import Literal

from backend.exact_fact_patterns import iter_exact_identifiers

from .thread_requests import extract_topics
from .thread_timeline import ThreadSource, TimelineBuild, build_timeline_skeleton


MAX_RELEVANT_HISTORY = 8
MAX_RELEVANT_HISTORY_CHARACTERS = 16_000


@dataclass(frozen=True, slots=True)
class ModelContextSelection:
    timeline: TimelineBuild
    sources: tuple[ThreadSource, ...]
    current_timeline: TimelineBuild
    current_sources: tuple[ThreadSource, ...]
    context_scope: Literal["current_only", "relevant_history"]
    context_limited: bool


def select_model_context(
    *, subject: str, sender: str, recipients: list[str], cc: list[str],
    sent_at: str, clean_body: str, full_timeline: TimelineBuild,
    internal_domains: tuple[str, ...],
) -> ModelContextSelection:
    """Keep the current message first and only a bounded relevant history slice."""
    current_segment = _current_segment(
        subject, sender, recipients, cc, sent_at, clean_body
    )
    current_timeline = build_timeline_skeleton([current_segment], internal_domains)
    current_sources = current_timeline.sources
    available = tuple(
        source for source in full_timeline.sources
        if not _duplicates_current(source, current_segment)
    )
    relevant = _select_history(
        available, subject=subject, sender=sender, recipients=recipients, cc=cc,
        clean_body=clean_body, internal_domains=internal_domains,
    )
    if not relevant:
        return ModelContextSelection(
            current_timeline, current_sources, current_timeline, current_sources,
            "current_only", bool(available),
        )
    timeline = build_timeline_skeleton(
        [*_segments(relevant), current_segment], internal_domains
    )
    current_matches = tuple(
        source for source in timeline.sources
        if _duplicates_current(source, current_segment)
    )
    if len(current_matches) != 1:
        return ModelContextSelection(
            current_timeline, current_sources, current_timeline, current_sources,
            "current_only", True,
        )
    current_source = current_matches[0]
    history_sources = tuple(
        source for source in timeline.sources if source is not current_source
    )
    return ModelContextSelection(
        timeline, (current_source, *history_sources),
        current_timeline, current_sources, "relevant_history",
        len(relevant) < len(available),
    )


def _select_history(
    sources: tuple[ThreadSource, ...], *, subject: str, sender: str,
    recipients: list[str], cc: list[str], clean_body: str,
    internal_domains: tuple[str, ...],
) -> tuple[ThreadSource, ...]:
    current_text = f"{subject}\n{clean_body}"
    identifiers = _identifiers(current_text)
    topics = frozenset(extract_topics(current_text))
    participants = _participants((sender, *recipients, *cc), internal_domains)
    candidates = [
        source for source in sources
        if _is_relevant(
            source, identifiers, topics, participants, internal_domains,
        )
    ]
    selected: list[ThreadSource] = []
    used = 0
    for source in reversed(candidates):
        size = len(source.subject) + len(source.body)
        if (
            len(selected) >= MAX_RELEVANT_HISTORY
            or used + size > MAX_RELEVANT_HISTORY_CHARACTERS
        ):
            continue
        selected.append(source)
        used += size
    return tuple(reversed(selected))


def _is_relevant(
    source: ThreadSource, identifiers: frozenset[str], topics: frozenset[str],
    participants: frozenset[str], internal_domains: tuple[str, ...],
) -> bool:
    text = f"{source.subject}\n{source.body}"
    return bool(
        identifiers.intersection(_identifiers(text))
        or topics.intersection(extract_topics(text))
        or participants.intersection(
            _participants((source.sender, source.recipient), internal_domains)
        )
    )


def _identifiers(text: str) -> frozenset[str]:
    return frozenset(value.casefold() for _label, value in iter_exact_identifiers(text))


def _participants(
    values: tuple[str, ...], internal_domains: tuple[str, ...],
) -> frozenset[str]:
    internal = {domain.strip().casefold() for domain in internal_domains}
    result: set[str] = set()
    for value in values:
        for _name, address in getaddresses([value]):
            candidate = address.strip().casefold()
            domain = candidate.rpartition("@")[2]
            if candidate and domain and domain not in internal:
                result.add(candidate)
    return frozenset(result)


def _duplicates_current(source: ThreadSource, current: dict[str, object]) -> bool:
    return (
        source.subject.strip() == str(current["subject"]).strip()
        and source.body.strip() == str(current["body_text"]).strip()
        and source.sender.strip().casefold() == str(current["from"]).strip().casefold()
    )


def _current_segment(
    subject: str, sender: str, recipients: list[str], cc: list[str],
    sent_at: str, clean_body: str,
) -> dict[str, object]:
    return {
        "position": 1_000_000,
        "from": sender,
        "to": ", ".join((*recipients, *cc)),
        "sent_at": sent_at,
        "subject": subject,
        "body_text": clean_body,
    }


def _segments(sources: tuple[ThreadSource, ...]) -> list[dict[str, object]]:
    return [
        {
            "position": index,
            "from": source.sender,
            "to": source.recipient,
            "sent_at": source.timestamp_text,
            "subject": source.subject,
            "body_text": source.body,
        }
        for index, source in enumerate(sources)
    ]
