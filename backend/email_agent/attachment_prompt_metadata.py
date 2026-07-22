"""Fixed provenance metadata for private attachment prompt sources."""

from __future__ import annotations

from .attachment_model_context import AttachmentModelContextItem


def attachment_projection_metadata(
    item: AttachmentModelContextItem,
) -> dict[str, object]:
    """Expose bounded parser/model completeness signals without public persistence."""
    return {
        "parser_truncated": bool(item.parser_truncated),
        "model_text_truncated": bool(item.truncated),
        "parser_limitations": list(item.parser_limitations),
    }
