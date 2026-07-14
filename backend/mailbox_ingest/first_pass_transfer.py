"""Bounded partial PEEK transport for first-pass message text."""

from __future__ import annotations

from .bodystructure import TextBodySection
from .text_body_decoder import MAX_ENCODED_TEXT_BYTES


PEEK_CHUNK_BYTES = 64 * 1024
MAX_HEADER_BYTES = 256 * 1024


class FirstPassContentError(ValueError):
    pass


class FirstPassTransportError(ValueError):
    pass


def fetch_first_pass_content(
    session: object,
    uid: int,
    parts: tuple[TextBodySection, ...],
) -> tuple[bytes, tuple[bytes, ...]]:
    _validate_parts(parts)
    header = _fetch_header(session, uid)
    bodies = tuple(_fetch_exact(session, uid, part) for part in parts)
    return header, bodies


def _validate_parts(parts: tuple[TextBodySection, ...]) -> None:
    if not isinstance(parts, tuple) or not all(
        isinstance(part, TextBodySection) for part in parts
    ):
        raise FirstPassContentError("first_pass_content_invalid")
    sizes = [part.size for part in parts]
    if any(type(size) is not int or not 0 <= size <= MAX_ENCODED_TEXT_BYTES for size in sizes):
        raise FirstPassContentError("first_pass_content_invalid")
    if sum(sizes) > MAX_ENCODED_TEXT_BYTES:
        raise FirstPassContentError("first_pass_content_invalid")


def _fetch_header(session: object, uid: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while offset < MAX_HEADER_BYTES:
        count = min(PEEK_CHUNK_BYTES, MAX_HEADER_BYTES - offset)
        chunk = _peek(session, uid, "HEADER", offset, count)
        chunks.append(chunk)
        offset += len(chunk)
        if len(chunk) < count:
            return b"".join(chunks)
    raise FirstPassContentError("first_pass_content_invalid")


def _fetch_exact(
    session: object, uid: int, part: TextBodySection
) -> bytes:
    if part.size == 0:
        return b""
    chunks: list[bytes] = []
    offset = 0
    while offset < part.size:
        count = min(PEEK_CHUNK_BYTES, part.size - offset)
        chunk = _peek(session, uid, part.section, offset, count)
        if not chunk:
            raise FirstPassTransportError("first_pass_transport_failed")
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def _peek(
    session: object, uid: int, section: str, offset: int, count: int
) -> bytes:
    try:
        chunk = session.uid_fetch_peek(
            uid, section, offset=offset, count=count
        )
    except Exception:
        raise FirstPassTransportError("first_pass_transport_failed") from None
    if type(chunk) is not bytes or len(chunk) > count:
        raise FirstPassTransportError("first_pass_transport_failed")
    return chunk


__all__ = [
    "FirstPassContentError",
    "FirstPassTransportError",
    "fetch_first_pass_content",
]
