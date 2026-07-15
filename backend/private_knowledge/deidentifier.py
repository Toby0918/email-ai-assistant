"""Ephemeral local text deidentification for reviewed source records."""

from __future__ import annotations

from .entity_patterns import AMBIGUOUS_CONTROLS, PATTERNS, iter_context_patterns
from .errors import PrivateKnowledgeError


class DeidentifiedText:
    """Placeholder text with a deliberately non-serializable local resolver."""

    __slots__ = ("_text", "_mapping", "_closed")

    def __init__(self, text: str, mapping: dict[str, str]) -> None:
        self._text = text
        self._mapping = mapping
        self._closed = False

    @property
    def text(self) -> str:
        return self._text

    def resolve(self, placeholder: str) -> str:
        if self._closed or placeholder not in self._mapping:
            raise PrivateKnowledgeError("resolver_unavailable")
        return self._mapping[placeholder]

    def close(self) -> None:
        if not self._closed:
            self._mapping.clear()
            self._closed = True

    def __enter__(self) -> DeidentifiedText:
        if self._closed:
            raise PrivateKnowledgeError("resolver_unavailable")
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _serialization_forbidden(self, *_args: object) -> None:
        raise PrivateKnowledgeError("deidentified_serialization_forbidden")

    __iter__ = _serialization_forbidden
    __copy__ = _serialization_forbidden
    __deepcopy__ = _serialization_forbidden
    __reduce__ = _serialization_forbidden
    __reduce_ex__ = _serialization_forbidden
    __getstate__ = _serialization_forbidden

    def __repr__(self) -> str:
        return "DeidentifiedText(<redacted>)"

    __str__ = __repr__


def deidentify_private_text(text: str, context: object = None) -> DeidentifiedText:
    if not isinstance(text, str) or len(text) > 2_000_000:
        raise PrivateKnowledgeError("input_invalid")
    if AMBIGUOUS_CONTROLS.search(text):
        raise PrivateKnowledgeError("ambiguous_input")
    try:
        patterns = PATTERNS + tuple(iter_context_patterns(context))
    except TypeError:
        raise PrivateKnowledgeError("context_invalid") from None
    spans = _select_spans(text, patterns)
    rendered, mapping = _replace_spans(text, spans)
    return DeidentifiedText(rendered, mapping)


def _select_spans(text: str, patterns: object) -> list[tuple[int, int, str, str]]:
    selected: list[tuple[int, int, str, str]] = []
    occupied: list[tuple[int, int]] = []
    for kind, pattern in patterns:
        for match in pattern.finditer(text):
            start, end = match.span()
            if start == end or any(start < right and end > left for left, right in occupied):
                continue
            selected.append((start, end, kind, match.group(0)))
            occupied.append((start, end))
    return sorted(selected)


def _replace_spans(
    text: str,
    spans: list[tuple[int, int, str, str]],
) -> tuple[str, dict[str, str]]:
    counters: dict[str, int] = {}
    entity_placeholders: dict[tuple[str, str], str] = {}
    mapping: dict[str, str] = {}
    parts: list[str] = []
    cursor = 0
    for start, end, kind, source in spans:
        key = (kind, source.casefold())
        placeholder = entity_placeholders.get(key)
        if placeholder is None:
            counters[kind] = counters.get(kind, 0) + 1
            placeholder = f"<{kind}_{counters[kind]}>"
            entity_placeholders[key] = placeholder
            mapping[placeholder] = source
        parts.extend((text[cursor:start], placeholder))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), mapping
