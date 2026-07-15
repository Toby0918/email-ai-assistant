"""Reject authority text that reproduces its deidentified support material."""

from __future__ import annotations

import re

from .errors import PrivateKnowledgeError


def validate_non_verbatim(card_content: object, source_texts: object) -> None:
    content = "\n".join(_collect_strings(card_content))
    if not isinstance(source_texts, (list, tuple)) or not all(
        isinstance(item, str) for item in source_texts
    ):
        raise PrivateKnowledgeError("verbatim_input_invalid")
    for source in source_texts:
        if _shares_latin(content, source) or _shares_han(content, source):
            raise PrivateKnowledgeError("verbatim_overlap")
        normalized_content = re.sub(r"\s|[^\w一-鿿]", "", content.casefold())
        normalized_source = re.sub(r"\s|[^\w一-鿿]", "", source.casefold())
        if _has_shared_window(normalized_content, normalized_source, 24):
            raise PrivateKnowledgeError("verbatim_overlap")


def _collect_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _collect_strings(item)]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in _collect_strings(item)]
    return []


def _shares_latin(left: str, right: str) -> bool:
    left_words = re.findall(r"[a-z0-9]+", left.casefold())
    right_text = " ".join(re.findall(r"[a-z0-9]+", right.casefold()))
    return any(
        " ".join(left_words[index:index + 6]) in right_text
        for index in range(max(0, len(left_words) - 5))
    )


def _shares_han(left: str, right: str) -> bool:
    left_han = "".join(re.findall(r"[一-鿿]", left))
    right_han = "".join(re.findall(r"[一-鿿]", right))
    return _has_shared_window(left_han, right_han, 12)


def _has_shared_window(left: str, right: str, size: int) -> bool:
    if len(left) < size or len(right) < size:
        return False
    return any(
        left[index:index + size] in right
        for index in range(len(left) - size + 1)
    )
