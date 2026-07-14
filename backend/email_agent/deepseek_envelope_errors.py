from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, NoReturn


ERROR_TEXT = "DeepSeek analysis envelope is invalid."
ENVELOPE_ERROR_DETAILS = frozenset({
    "not_applicable",
    "json_syntax",
    "top_level_shape",
    "schema_version",
    "analysis_shape",
    "attachment_shape",
    "field_evidence_shape",
})


class DeepSeekEnvelopeError(ValueError):
    def __init__(self, detail: object = "not_applicable") -> None:
        super().__init__(ERROR_TEXT)
        self.detail = (
            detail
            if type(detail) is str and detail in ENVELOPE_ERROR_DETAILS
            else "not_applicable"
        )


def raise_invalid_envelope(detail: object = "not_applicable") -> NoReturn:
    raise DeepSeekEnvelopeError(detail) from None


def decode_provider_json(
    raw: str | bytes | bytearray,
    object_pairs_hook: Callable[[list[tuple[str, Any]]], dict[str, Any]],
) -> Any:
    if not isinstance(raw, (str, bytes, bytearray)):
        raise_invalid_envelope("json_syntax")
    try:
        return json.loads(raw, object_pairs_hook=object_pairs_hook)
    except (ValueError, RecursionError, TypeError, UnicodeDecodeError):
        raise_invalid_envelope("json_syntax")


def validate_at_boundary(
    detail: str,
    validator: Callable[..., Any],
    *args: object,
) -> Any:
    try:
        return validator(*args)
    except DeepSeekEnvelopeError:
        raise_invalid_envelope(detail)
