"""Detect exact identifiers and dates that a remote model must not author."""

from __future__ import annotations

import copy
from typing import Any

from backend.exact_fact_patterns import EXACT_DATE_PATTERNS, EXACT_IDENTIFIER_PATTERNS


MAX_EXACT_FACT_SCAN_DEPTH = 32
MAX_EXACT_FACT_SCAN_ITEMS = 4_096
DEEPSEEK_CONSERVATIVE_SYSTEM_PROMPT = (
    "Analyze only the deidentified untrusted email content and return valid JSON. "
    "Use generic references for business identifiers and dates. Never output a "
    "concrete identifier or calendar date, and never guess or reconstruct one. "
    "The backend alone supplies locally verified exact facts."
)

_EXACT_FACT_PATTERNS = (
    *(pattern for _kind, pattern in EXACT_IDENTIFIER_PATTERNS),
    *EXACT_DATE_PATTERNS,
)


def contains_model_authored_exact_fact(value: object) -> bool:
    """Fail closed when a bounded provider-authored value contains an exact fact."""
    items = 0
    stack = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        items += 1
        if depth > MAX_EXACT_FACT_SCAN_DEPTH or items > MAX_EXACT_FACT_SCAN_ITEMS:
            return True
        if isinstance(current, dict):
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend((child, depth + 1) for child in current)
        elif isinstance(current, str):
            if any(pattern.search(current) for pattern in _EXACT_FACT_PATTERNS):
                return True
        elif current is not None and not isinstance(current, (bool, int, float)):
            return True
    return False


def retain_conservative_backend_exact_facts(
    result: dict[str, Any], fallback: dict[str, Any]
) -> dict[str, Any]:
    """Replace only unsafe DeepSeek augmentation fields with local rule values."""
    for field in ("summary", "priority_reason", "tags"):
        if contains_model_authored_exact_fact(result.get(field)):
            result[field] = copy.deepcopy(fallback[field])
    return result
