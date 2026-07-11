"""Email body cleaning utilities."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


_SKIPPED_HTML_TAGS = {"script", "style", "blockquote"}
DEFAULT_THREAD_SEGMENT_MAX_CHARS = 2_000
DEFAULT_THREAD_SOURCE_MAX_CHARS = 20_000


# Reduce HTML to plain text before prompt construction to limit markup influence.
class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name in _SKIPPED_HTML_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag_name in {"br", "p", "div", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name in _SKIPPED_HTML_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag_name in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


def clean_email_body(body_text: str | None = None, body_html: str | None = None) -> str:
    text_source = body_text if isinstance(body_text, str) else ""
    html_source = body_html if isinstance(body_html, str) else ""
    source = _html_to_text(html_source) if html_source else text_source
    source = _strip_quote_history(source)
    return _normalize_text(source)


def clean_thread_segment_text(
    body_text: str | None = None,
    body_html: str | None = None,
    max_chars: int = DEFAULT_THREAD_SEGMENT_MAX_CHARS,
) -> str:
    """Return bounded current-message text for deterministic thread processing."""
    cleaned, _ = clean_thread_segment_text_with_coverage(body_text, body_html, max_chars)
    return cleaned


def clean_thread_segment_text_with_coverage(
    body_text: str | None = None,
    body_html: str | None = None,
    max_chars: int = DEFAULT_THREAD_SEGMENT_MAX_CHARS,
) -> tuple[str, bool]:
    """Return bounded text and whether no supplied source text was omitted."""
    bounded_text, text_complete = _bound_thread_source(body_text)
    bounded_html, html_complete = _bound_thread_source(body_html)
    cleaned = _strip_thread_noise(clean_email_body(body_text=bounded_text, body_html=bounded_html))
    if not isinstance(max_chars, int):
        max_chars = DEFAULT_THREAD_SEGMENT_MAX_CHARS
    limit = max(min(max_chars, DEFAULT_THREAD_SEGMENT_MAX_CHARS), 0)
    coverage_complete = text_complete and html_complete and len(cleaned) <= limit
    return cleaned[:limit], coverage_complete


def _bound_thread_source(value: str | None) -> tuple[str, bool]:
    if not isinstance(value, str):
        return "", True
    return value[:DEFAULT_THREAD_SOURCE_MAX_CHARS], len(value) <= DEFAULT_THREAD_SOURCE_MAX_CHARS


def _html_to_text(body_html: str | None) -> str:
    parser = _TextExtractor()
    parser.feed(body_html or "")
    parser.close()
    return unescape(" ".join(parser.parts))


def _normalize_text(text: str) -> str:
    normalized = text.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _strip_quote_history(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if _is_quote_history_marker(line):
            break
        lines.append(line)
    return "\n".join(lines)


def _strip_thread_noise(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if line.strip() == "--":
            break
        without_banner = re.sub(r"^\s*\[(?:external email|外部邮件)\]\s*", "", line, flags=re.IGNORECASE)
        if without_banner.strip():
            lines.append(without_banner)
    return _normalize_text("\n".join(lines))


def _is_quote_history_marker(line: str) -> bool:
    stripped = line.strip()
    lower = stripped.lower()
    return (
        stripped.startswith(">")
        or re.fullmatch(r"-{2,}\s*(original message|forwarded message)\s*-{2,}", lower) is not None
        or re.fullmatch(r"-{2,}\s*(原始邮件|转发邮件)\s*-{2,}", stripped) is not None
        or re.fullmatch(r"on .+ wrote:", lower) is not None
        or re.fullmatch(r"在.+写道[:：]?", stripped) is not None
    )
