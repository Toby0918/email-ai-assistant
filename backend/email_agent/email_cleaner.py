"""Email body cleaning utilities."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


_SKIPPED_HTML_TAGS = {"script", "style", "blockquote"}


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
    source = _html_to_text(body_html) if body_html else (body_text or "")
    source = _strip_quote_history(source)
    return _normalize_text(source)


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


def _is_quote_history_marker(line: str) -> bool:
    stripped = line.strip()
    lower = stripped.lower()
    return (
        re.fullmatch(r"-{2,}\s*(original message|forwarded message)\s*-{2,}", lower) is not None
        or re.fullmatch(r"-{2,}\s*(原始邮件|转发邮件)\s*-{2,}", stripped) is not None
        or re.fullmatch(r"on .+ wrote:", lower) is not None
        or re.fullmatch(r"在.+写道[:：]?", stripped) is not None
    )
