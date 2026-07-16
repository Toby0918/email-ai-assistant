"""Bounded, content-free privacy checks for remote provider output."""

from __future__ import annotations

import json
import math
from collections.abc import Callable


MAX_PROVIDER_OUTPUT_CHARACTERS = 65_536
MAX_PROVIDER_OUTPUT_DEPTH = 32
MAX_PROVIDER_OUTPUT_ITEMS = 4_096
def provider_output_is_private_safe(
    raw: object, contains_private_artifact: Callable[[str], bool],
) -> bool:
    """Reject private-boundary artifacts before any DeepSeek parser sees them."""
    if type(raw) is not str or contains_private_artifact(raw):
        return False
    decoded = _decode_bounded_output(raw)
    return decoded is not None and _decoded_output_is_private_safe(
        decoded, contains_private_artifact,
    )


def provider_output_contains_placeholder(
    raw: object, contains_placeholder: Callable[[str], bool],
) -> bool:
    """Return only whether a bounded provider output echoes a private token."""
    if not _bounded_text(raw):
        return False
    assert isinstance(raw, str)
    if contains_placeholder(raw):
        return True
    decoded = _decode_bounded_output(raw)
    return decoded is not None and _decoded_contains(decoded, contains_placeholder)


def provider_output_contains_private_artifact(
    raw: object, contains_private_artifact: Callable[[str], bool],
) -> bool:
    """Classify a bounded private marker without returning matched content."""
    if not _bounded_text(raw):
        return False
    assert isinstance(raw, str)
    if contains_private_artifact(raw):
        return True
    decoded = _decode_bounded_output(raw)
    return decoded is not None and _decoded_contains(
        decoded, contains_private_artifact,
    )


def _bounded_text(raw: object) -> bool:
    return type(raw) is str and bool(raw) and len(raw) <= MAX_PROVIDER_OUTPUT_CHARACTERS


def _decode_bounded_output(raw: object) -> object | None:
    if not _bounded_text(raw):
        return None
    try:
        return json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except Exception:
        return None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ValueError("nonstandard_json_constant")


def _decoded_output_is_private_safe(
    decoded: object, contains_private_artifact: Callable[[str], bool],
) -> bool:
    items = 0
    stack = [(decoded, 0)]
    while stack:
        value, depth = stack.pop()
        items += 1
        if depth > MAX_PROVIDER_OUTPUT_DEPTH or items > MAX_PROVIDER_OUTPUT_ITEMS:
            return False
        if isinstance(value, dict):
            for key, child in value.items():
                if contains_private_artifact(key):
                    return False
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            if contains_private_artifact(value):
                return False
        elif isinstance(value, float) and not math.isfinite(value):
            return False
        elif value is not None and not isinstance(value, (bool, int, float)):
            return False
    return True


def _decoded_contains(
    decoded: object, predicate: Callable[[str], bool],
) -> bool:
    items = 0
    stack = [(decoded, 0)]
    while stack:
        value, depth = stack.pop()
        items += 1
        if depth > MAX_PROVIDER_OUTPUT_DEPTH or items > MAX_PROVIDER_OUTPUT_ITEMS:
            return False
        if isinstance(value, dict):
            for key, child in value.items():
                if predicate(key):
                    return True
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str) and predicate(value):
            return True
    return False
