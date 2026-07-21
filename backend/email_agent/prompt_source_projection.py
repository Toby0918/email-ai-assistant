"""Small JSON projections for source-labelled provider context."""

from __future__ import annotations


def thread_prompt_source(
    source_id: str,
    text: str,
    position: int,
) -> dict[str, object]:
    item: dict[str, object] = {
        "source_id": source_id,
        "kind": "thread",
        "public_source": "thread",
        "text": text,
        "message_role": "current" if position == 0 else "history",
    }
    if position > 0:
        item["history_position"] = position - 1
    return item


def attachment_prompt_source(
    source_id: str,
    public_source: str,
    text: str,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "kind": "attachment",
        "public_source": public_source,
        "text": text,
    }
