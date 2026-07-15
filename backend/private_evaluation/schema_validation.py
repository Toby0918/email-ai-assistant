"""Bounded primitive validators for private evaluation schema values."""

from __future__ import annotations

import re
import uuid
from typing import Any

from backend.private_knowledge.residual_scanner import scan_residuals

from .errors import PrivateEvaluationError


_UUID_TEXT = re.compile(
    r"(?i)(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}(?![0-9a-f])"
)


def safe_text_tuple(value: object, maximum: int, characters: int) -> tuple[str, ...]:
    return tuple(safe_text(item, characters) for item in list_value(value, maximum))


def enum_tuple(value: object, allowed: frozenset[str], maximum: int) -> tuple[str, ...]:
    result = tuple(enum_value(item, allowed) for item in list_value(value, maximum))
    if len(result) != len(set(result)):
        invalid()
    return result


def safe_text(value: object, maximum: int) -> str:
    text = text_value(value, maximum)
    if "\x00" in text or _UUID_TEXT.search(text) or scan_residuals(text):
        invalid()
    return text


def mapping(value: object, fields: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        invalid()
    return value


def list_value(value: object, maximum: int) -> list[object]:
    if type(value) is not list or len(value) > maximum:
        invalid()
    return value


def text_value(value: object, maximum: int) -> str:
    if type(value) is not str or not value:
        invalid()
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        invalid()
    if len(encoded) > maximum:
        invalid()
    return value


def enum_value(value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        invalid()
    return value


def positive_int(value: object) -> int:
    if type(value) is not int or value <= 0:
        invalid()
    return value


def uuid4_value(value: object) -> str:
    if type(value) is not str:
        invalid()
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        invalid()
    if str(parsed) != value or parsed.version != 4:
        invalid()
    return value


def invalid() -> None:
    raise PrivateEvaluationError("dataset_schema_invalid")
