"""Bind sanitized request media to existing attachment evidence sources."""

from __future__ import annotations

from .attachment_model_context import (
    AttachmentAnalysisBundle,
    AttachmentModelCandidate,
    attachment_model_candidate,
)
from .multimodal_media import PreparedMediaAsset


UNTRUSTED_MEDIA_EVIDENCE = (
    "UNTRUSTED_MEDIA: sanitized current-message media has no locally extracted text."
)
OPENAI_VISUAL_MEDIA_PROMPT_EVIDENCE = (
    "sanitized current-message visual media is supplied and has no locally "
    "extracted text."
)


def provider_attachment_candidate(
    candidate: AttachmentModelCandidate | None, provider: str,
) -> AttachmentModelCandidate | None:
    """Expose textless media only to the provider that receives sanitized media."""
    if candidate is None or not candidate.visual_only:
        return candidate
    if provider != "openai":
        return None
    return attachment_model_candidate(
        candidate.source_id, OPENAI_VISUAL_MEDIA_PROMPT_EVIDENCE,
        visual_only=True,
    )


def bind_prepared_media_evidence(
    bundles: tuple[AttachmentAnalysisBundle, ...],
    assets: tuple[PreparedMediaAsset, ...],
) -> tuple[AttachmentAnalysisBundle, ...]:
    """Add one fixed source marker only for successfully sanitized textless media."""
    media_sources = {asset.source_id for asset in assets}
    bound: list[AttachmentAnalysisBundle] = []
    for index, bundle in enumerate(bundles):
        source_id = f"attachment:{index}"
        candidate = bundle.model_candidate
        if candidate is None and source_id in media_sources:
            candidate = attachment_model_candidate(
                source_id, UNTRUSTED_MEDIA_EVIDENCE, visual_only=True,
            )
        bound.append(AttachmentAnalysisBundle(bundle.display_insight, candidate))
    return tuple(bound)
