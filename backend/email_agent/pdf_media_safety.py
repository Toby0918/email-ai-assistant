"""Bounded PDF rewrite and active-object audit for request-local media."""

from __future__ import annotations

import io
from collections.abc import Iterator

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject

from .attachment_safety import enforce_pdf_decoder_limits


MAX_PDF_PAGES = 5
MAX_PDF_INPUT_BYTES = 10 * 1024 * 1024
MAX_PDF_OUTPUT_BYTES = 10 * 1024 * 1024

_ERROR_MESSAGE = "PDF could not be prepared safely."
_ACTIVE_PAGE_KEYS = (
    "/Annots", "/AA", "/A", "/Metadata", "/AF", "/B", "/Dur", "/Trans",
    "/PieceInfo", "/PresSteps", "/Thumb", "/LastModified",
)
_ACTIVE_GRAPH_KEYS = frozenset({
    "/Annots", "/AA", "/A", "/Metadata", "/AF", "/OpenAction", "/AcroForm",
    "/Names", "/XFA", "/Collection", "/EmbeddedFiles", "/EF", "/JS",
})
_ACTIVE_TYPE_VALUES = frozenset({
    "/EmbeddedFile", "/Filespec", "/Widget", "/FileAttachment", "/ObjStm", "/XRef",
})
_ACTIVE_ACTION_VALUES = frozenset({
    "/JavaScript", "/Launch", "/SubmitForm", "/ImportData", "/GoToR",
})
_MAX_GRAPH_NODES = 20_000
_MAX_GRAPH_DEPTH = 32


class PdfSanitizationError(ValueError):
    """A fixed, content-free PDF sanitation failure."""


def sanitize_pdf_content(content: bytes | bytearray) -> bytes:
    """Return a fresh bounded PDF with active document surfaces removed."""
    reader: PdfReader | None = None
    try:
        raw = _bounded_pdf(content)
        enforce_pdf_decoder_limits()
        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
            raise PdfSanitizationError(_ERROR_MESSAGE)
        prepared = _rewrite_pages(reader)
        _audit_sanitized_pdf(prepared)
        return prepared
    except PdfSanitizationError:
        raise
    except Exception:
        raise PdfSanitizationError(_ERROR_MESSAGE) from None
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:
                pass


def _bounded_pdf(content: bytes | bytearray) -> bytes:
    if type(content) not in {bytes, bytearray} or not content:
        raise PdfSanitizationError(_ERROR_MESSAGE)
    if len(content) > MAX_PDF_INPUT_BYTES:
        raise PdfSanitizationError(_ERROR_MESSAGE)
    raw = bytes(content)
    if not raw.startswith(b"%PDF-"):
        raise PdfSanitizationError(_ERROR_MESSAGE)
    return raw


def _rewrite_pages(reader: PdfReader) -> bytes:
    writer = PdfWriter()
    try:
        source_root = reader.trailer["/Root"]
        _strip_active_graph(source_root)
        _audit_graph(source_root)
        excluded_keys = tuple(sorted({*_ACTIVE_PAGE_KEYS, *_ACTIVE_GRAPH_KEYS}))
        for source_page in reader.pages:
            writer.add_page(source_page, excluded_keys=excluded_keys)
            _strip_active_graph(writer.pages[-1])
        writer.remove_annotations(None)
        writer.metadata = None
        output = io.BytesIO()
        writer.write(output)
        prepared = output.getvalue()
        if not prepared or len(prepared) > MAX_PDF_OUTPUT_BYTES:
            raise PdfSanitizationError(_ERROR_MESSAGE)
        return prepared
    finally:
        try:
            writer.close()
        except Exception:
            pass


def _strip_active_graph(root: object) -> None:
    for current in _walk_graph(root):
        if isinstance(current, DictionaryObject):
            for key in tuple(current.keys()):
                if str(key) in _ACTIVE_GRAPH_KEYS:
                    current.pop(key, None)


def _audit_graph(root: object) -> None:
    for current in _walk_graph(root):
        if isinstance(current, DictionaryObject):
            _audit_dictionary(current)


def _audit_sanitized_pdf(content: bytes) -> None:
    audit = PdfReader(io.BytesIO(content), strict=True)
    try:
        if audit.is_encrypted or audit.metadata is not None:
            raise PdfSanitizationError(_ERROR_MESSAGE)
        for current in _walk_graph_roots(_serialized_pdf_roots(audit)):
            if isinstance(current, DictionaryObject):
                _audit_dictionary(current)
    finally:
        audit.close()


def _audit_dictionary(value: DictionaryObject) -> None:
    for key, item in value.items():
        key_text = str(key)
        if key_text in _ACTIVE_GRAPH_KEYS:
            raise PdfSanitizationError(_ERROR_MESSAGE)
        if key_text in {"/Type", "/Subtype", "/S"}:
            resolved_item = item.get_object() if isinstance(item, IndirectObject) else item
            if not isinstance(resolved_item, NameObject):
                raise PdfSanitizationError(_ERROR_MESSAGE)
            item_text = str(resolved_item)
            if key_text in {"/Type", "/Subtype"} and item_text in _ACTIVE_TYPE_VALUES:
                raise PdfSanitizationError(_ERROR_MESSAGE)
            if key_text == "/S" and item_text in _ACTIVE_ACTION_VALUES:
                raise PdfSanitizationError(_ERROR_MESSAGE)


def _serialized_pdf_roots(reader: PdfReader) -> tuple[object, ...]:
    roots: list[object] = [reader.trailer]
    identities: set[tuple[int, int]] = set()
    declared_size = reader.trailer.get("/Size")
    if (
        isinstance(declared_size, bool)
        or not isinstance(declared_size, int)
        or not 1 <= declared_size <= _MAX_GRAPH_NODES + 1
        or reader.xref_objStm
    ):
        raise PdfSanitizationError(_ERROR_MESSAGE)
    for generation, entries in reader.xref.items():
        for idnum in entries:
            identity = (idnum, generation)
            if idnum >= declared_size or idnum > _MAX_GRAPH_NODES:
                raise PdfSanitizationError(_ERROR_MESSAGE)
            if idnum > 0 and generation >= 0 and identity not in identities:
                identities.add(identity)
                roots.append(IndirectObject(idnum, generation, reader))
    if len(roots) > _MAX_GRAPH_NODES:
        raise PdfSanitizationError(_ERROR_MESSAGE)
    return tuple(roots)


def _walk_graph(root: object) -> Iterator[object]:
    return _walk_graph_roots((root,))


def _walk_graph_roots(roots: tuple[object, ...]) -> Iterator[object]:
    stack: list[tuple[object, int]] = [(root, 0) for root in roots]
    seen: set[tuple[int, int]] = set()
    seen_containers: set[int] = set()
    nodes = 0
    while stack:
        current, depth = stack.pop()
        if depth > _MAX_GRAPH_DEPTH:
            raise PdfSanitizationError(_ERROR_MESSAGE)
        if isinstance(current, IndirectObject):
            identity = (current.idnum, current.generation)
            if identity in seen:
                continue
            seen.add(identity)
            current = current.get_object()
        if isinstance(current, (DictionaryObject, ArrayObject)):
            container_identity = id(current)
            if container_identity in seen_containers:
                continue
            seen_containers.add(container_identity)
        nodes += 1
        if nodes > _MAX_GRAPH_NODES:
            raise PdfSanitizationError(_ERROR_MESSAGE)
        yield current
        if isinstance(current, DictionaryObject):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, ArrayObject):
            stack.extend((item, depth + 1) for item in current)
