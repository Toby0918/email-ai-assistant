"""Internal text, visual, and hybrid source-capability policy."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping, Sequence

from .model_cross_language_grounding import cross_language_claim_is_grounded
from .model_multimodal_claim_safety import multimodal_global_claim_is_safe
from .model_visual_grounding import visual_claim_is_allowed
from .prompt_context import EvidenceSource

_INVALID_SOURCE_REASON = "Evidence source is invalid."
_UNGROUNDED_REASON = "Critical model text is not grounded."
_UNAVAILABLE_ATTACHMENT_REASON = "Attachment evidence is unavailable."


def claimed_source_violation(
    text: str, signatures: frozenset[str], claimed: Sequence[str],
    sources: Mapping[str, EvidenceSource], attachment_owner: str | None,
    signature_reader: Callable[[str], frozenset[str]],
    *, pointer: str, require_text_grounding: bool = False,
) -> str | None:
    if require_text_grounding and not multimodal_global_claim_is_safe(
        text, has_critical_signatures=bool(signatures)):
        return _UNGROUNDED_REASON
    for source_id in claimed:
        source = sources.get(source_id)
        if source is None:
            return _INVALID_SOURCE_REASON
        if signatures and source.kind == "attachment" and not source.parsed:
            return _UNAVAILABLE_ATTACHMENT_REASON
        if source.grounding_mode == "visual":
            if source_id != attachment_owner or not visual_claim_is_allowed(
                text, has_critical_signatures=bool(signatures)
            ):
                return _UNGROUNDED_REASON
            continue
        if source.grounding_mode == "hybrid":
            if _text_claim_is_grounded(
                text, source.grounding_text, pointer=pointer,
                allow_cross_language=require_text_grounding,
                cross_language_text=_cross_language_text(source),
            ):
                if signatures and not signatures.issubset(
                    signature_reader(source.grounding_text)
                ):
                    return _UNGROUNDED_REASON
                continue
            if require_text_grounding:
                return _UNGROUNDED_REASON
            if source_id == attachment_owner and visual_claim_is_allowed(
                text, has_critical_signatures=bool(signatures)
            ):
                continue
            return _UNGROUNDED_REASON
        if require_text_grounding and not _text_claim_is_grounded(
            text, source.grounding_text, pointer=pointer,
            allow_cross_language=True,
            cross_language_text=_cross_language_text(source),
        ):
            return _UNGROUNDED_REASON
        if signatures and not signatures.issubset(
            signature_reader(source.grounding_text)
        ):
            return _UNGROUNDED_REASON
    return None


def _text_claim_is_grounded(
    text: str,
    grounding_text: str,
    *,
    pointer: str,
    allow_cross_language: bool = False,
    cross_language_text: str | None = None,
) -> bool:
    needle = _normalized_phrase(text)
    if bool(needle) and needle in _normalized_phrase(grounding_text):
        return True
    return bool(cross_language_text) and allow_cross_language and cross_language_claim_is_grounded(
        text, cross_language_text, pointer=pointer,
    )


def _cross_language_text(source: EvidenceSource) -> str | None:
    if source.kind != "thread":
        return None
    return source.cross_language_grounding_text


def _normalized_phrase(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split()).strip(" .。")
