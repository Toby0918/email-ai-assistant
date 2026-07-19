"""Build a bounded thread prompt and its body-only grounding projection."""

from __future__ import annotations

from collections.abc import Callable

from .thread_timeline import ThreadSource


def build_thread_prompt_material(
    source: ThreadSource,
    limit: int,
    sanitize: Callable[[object, int], str],
) -> tuple[str, str | None]:
    """Return provider text plus only the exact body substring actually sent."""
    safe_limit = max(0, int(limit))
    metadata = "\n".join(
        f"{label} = {_single_line(value, safe_limit, sanitize)}"
        for label, value in (
            ("subject", source.subject), ("from", source.sender),
            ("to", source.recipient), ("sent_at", source.timestamp_text),
        )
    )
    body_prefix = "\nbody = "
    if len(metadata) + len(body_prefix) > safe_limit:
        return sanitize(metadata, safe_limit), None
    body_limit = safe_limit - len(metadata) - len(body_prefix)
    body = sanitize(source.body, body_limit)
    return metadata + body_prefix + body, body or None


def _single_line(
    value: object, limit: int, sanitize: Callable[[object, int], str],
) -> str:
    return " ".join(sanitize(value, limit).split())[:limit]
