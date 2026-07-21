"""Private, bounded attachment text projection for remote model requests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .attachment_remote_text import SanitizedModelText, sanitize_remote_text
from .attachment_sentence_boundary import complete_sentence_prefix


MAX_MODEL_CHARACTERS_PER_ATTACHMENT = 8_000
MAX_MODEL_CHARACTERS_TOTAL = 40_000
MAX_MODEL_PARSER_LIMITATIONS = 8
MAX_MODEL_PARSER_LIMITATION_CHARACTERS = 240


@dataclass(frozen=True, slots=True, repr=False)
class AttachmentModelCandidate:
    source_id: str
    text: str
    visual_only: bool = False
    parser_truncated: bool = False
    parser_limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, repr=False)
class AttachmentModelContextItem:
    source_id: str
    text: str
    link_was_present: bool
    truncated: bool
    parser_truncated: bool = False
    parser_limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, repr=False)
class AttachmentAnalysisBundle:
    display_insight: dict[str, object]
    model_candidate: AttachmentModelCandidate | None


def attachment_model_candidate(
    source_id: str,
    value: str,
    *,
    visual_only: bool = False,
    parser_limitations: Iterable[str] = (),
) -> AttachmentModelCandidate | None:
    """Construct a repr-safe candidate only from already-bounded extracted text."""
    limitations = tuple(
        dict.fromkeys(
            str(item).strip()
            for item in parser_limitations
            if str(item).strip()
        )
    )[:MAX_MODEL_PARSER_LIMITATIONS]
    return (
        AttachmentModelCandidate(
            source_id,
            value,
            visual_only,
            bool(limitations),
            limitations,
        )
        if value
        else None
    )


def build_attachment_model_context(
    candidates: Iterable[AttachmentModelCandidate],
) -> tuple[AttachmentModelContextItem, ...]:
    """Sanitize candidates in input order under per-item and aggregate character limits."""
    accepted: list[AttachmentModelContextItem] = []
    remaining = MAX_MODEL_CHARACTERS_TOTAL
    for candidate in candidates:
        if remaining <= 0:
            break
        sanitized = sanitize_remote_text(
            candidate.text,
            min(MAX_MODEL_CHARACTERS_PER_ATTACHMENT, remaining),
        )
        model_text = (
            complete_sentence_prefix(
                sanitized.text,
                final_ascii_period_is_ambiguous=True,
            )
            if sanitized.truncated
            else sanitized.text
        )
        if not model_text:
            continue
        limitations = _sanitize_limitations(candidate.parser_limitations)
        accepted.append(AttachmentModelContextItem(
            candidate.source_id,
            model_text,
            sanitized.link_was_present,
            sanitized.truncated,
            candidate.parser_truncated or bool(limitations),
            limitations,
        ))
        remaining -= len(model_text)
    return tuple(accepted)


def _sanitize_limitations(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        cleaned.text
        for value in values[:MAX_MODEL_PARSER_LIMITATIONS]
        if (
            cleaned := sanitize_remote_text(
                value,
                MAX_MODEL_PARSER_LIMITATION_CHARACTERS,
            )
        ).text
    )


__all__ = [
    "AttachmentAnalysisBundle",
    "AttachmentModelCandidate",
    "AttachmentModelContextItem",
    "MAX_MODEL_CHARACTERS_PER_ATTACHMENT",
    "MAX_MODEL_CHARACTERS_TOTAL",
    "SanitizedModelText",
    "attachment_model_candidate",
    "build_attachment_model_context",
    "sanitize_remote_text",
]
