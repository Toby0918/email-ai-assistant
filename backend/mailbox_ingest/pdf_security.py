"""Conservative PDF structure and active-content validation."""

from __future__ import annotations

import io
import re

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject


MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_GRAPH_NODES = 20_000
MAX_GRAPH_DEPTH = 32
_PDF_NAME = re.compile(rb"/([^\x00\t\n\f\r ()<>\[\]{}/%]+)")
_DANGEROUS_NAMES = frozenset(
    {
        b"aa", b"embeddedfile", b"embeddedfiles", b"encrypt", b"filespec",
        b"javascript", b"js", b"launch", b"objstm", b"openaction",
    }
)


class PdfSafetyError(ValueError):
    def __init__(self, code: str = "attachment_active_content") -> None:
        self.code = code
        super().__init__(code)


def validate_safe_pdf(content: bytes) -> None:
    if (
        type(content) is not bytes
        or not 1 <= len(content) <= MAX_PDF_BYTES
        or not content.startswith(b"%PDF-")
    ):
        raise PdfSafetyError("attachment_magic_mismatch")
    _reject_raw_names(content)
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise PdfSafetyError()
        page_count = len(reader.pages)
        if not 1 <= page_count <= MAX_PDF_PAGES:
            raise PdfSafetyError("attachment_magic_mismatch")
        _inspect_graph(reader.trailer)
    except PdfSafetyError:
        raise
    except Exception:
        raise PdfSafetyError("attachment_magic_mismatch") from None


def _reject_raw_names(content: bytes) -> None:
    for match in _PDF_NAME.finditer(content):
        if _decode_name(match.group(1)).lower() in _DANGEROUS_NAMES:
            raise PdfSafetyError()


def _decode_name(value: bytes) -> bytes:
    decoded = bytearray()
    offset = 0
    while offset < len(value):
        if value[offset] != 0x23:
            decoded.append(value[offset])
            offset += 1
            continue
        if offset + 2 >= len(value):
            raise PdfSafetyError()
        pair = value[offset + 1:offset + 3]
        if re.fullmatch(rb"[0-9A-Fa-f]{2}", pair) is None:
            raise PdfSafetyError()
        decoded.append(int(pair, 16))
        offset += 3
    return bytes(decoded)


def _inspect_graph(root: object) -> None:
    stack: list[tuple[object, int]] = [(root, 0)]
    seen_indirect: set[tuple[int, int]] = set()
    seen_objects: set[int] = set()
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_GRAPH_NODES or depth > MAX_GRAPH_DEPTH:
            raise PdfSafetyError()
        if isinstance(value, IndirectObject):
            identity = (value.idnum, value.generation)
            if identity not in seen_indirect:
                seen_indirect.add(identity)
                stack.append((value.get_object(), depth + 1))
            continue
        if isinstance(value, NameObject):
            _reject_parsed_name(str(value))
            continue
        if isinstance(value, DictionaryObject):
            if id(value) in seen_objects:
                continue
            seen_objects.add(id(value))
            for key, item in value.items():
                _reject_parsed_name(str(key))
                stack.append((item, depth + 1))
            continue
        if isinstance(value, ArrayObject):
            stack.extend((item, depth + 1) for item in value)


def _reject_parsed_name(value: str) -> None:
    if value.startswith("/") and value[1:].encode("latin-1").lower() in _DANGEROUS_NAMES:
        raise PdfSafetyError()


__all__ = ["PdfSafetyError", "validate_safe_pdf"]
