"""Bounded, display-safe parsing for supported temporary attachments."""

from __future__ import annotations

import multiprocessing
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.context import BaseContext
from typing import Any

from docx import Document
from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader

try:
    import pytesseract
except ImportError:  # pragma: no cover - dependency is pinned but OCR remains optional.
    pytesseract = None

from .attachment_storage import StoredAttachment
from .attachment_model_context import AttachmentAnalysisBundle
from .attachment_docx import (
    MAX_DOCX_CELLS_PER_ROW,
    MAX_DOCX_ROWS_PER_TABLE,
    parse_docx_bundle,
    parse_pdf_bundle,
    parse_xlsx_bundle,
)
from .attachment_safety import (
    decoder_failure_limitation,
)
from .attachment_text import (
    MAX_EXTRACTED_CHARACTERS,
    MAX_KEY_FACT_CHARACTERS,
    MAX_KEY_FACTS,
    TextBudget,
    character_limitations as _character_limitations,
    extension_limitation as _extension_limitation_for,
    metadata_only as _metadata_only,
    text_insight as _text_insight,
    valid_worker_bundle as _valid_worker_bundle,
)

MAX_OCR_CHARACTERS = 2_000
MAX_IMAGE_PIXELS = 25_000_000
OCR_TIMEOUT_SECONDS = 5
_TIMEOUT_LIMITATION = "Attachment parsing timed out; content was not parsed."
_WORKER_FAILURE_LIMITATION = "Attachment content could not be parsed in the isolated worker."
_POLL_INTERVAL_SECONDS = 0.05
_JOIN_TIMEOUT_SECONDS = 0.2

_ALLOWED_SUFFIXES = {
    "pdf": {".pdf"},
    "xlsx": {".xlsx"},
    "docx": {".docx"},
    "image": {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"},
}

def parse_attachments(items: list[StoredAttachment]) -> list[dict[str, object]]:
    """Return bounded, de-identified insights for stored current-email attachments."""
    return [bundle.display_insight for bundle in parse_attachment_bundles_compat(items)]

def parse_attachment_bundles_compat(items: list[StoredAttachment]) -> list[AttachmentAnalysisBundle]:
    """Build synchronous in-process bundles for display-only compatibility callers."""
    return [_parse_one_bundle(item, f"attachment:{index}") for index, item in enumerate(items)]

def parse_attachment_bundles(
    items: list[StoredAttachment],
    *,
    deadline: float,
    clock: Callable[[], float] = time.monotonic,
    mp_context: BaseContext | None = None,
) -> list[AttachmentAnalysisBundle]:
    """Parse sequentially in spawned workers under one absolute deadline."""
    context = mp_context or multiprocessing.get_context("spawn")
    results: list[AttachmentAnalysisBundle] = []
    for index, item in enumerate(items):
        if clock() >= deadline:
            results.extend(_metadata_only(remaining, _TIMEOUT_LIMITATION) for remaining in items[index:])
            break
        bundle, timed_out = _parse_in_worker(
            item,
            source_id=f"attachment:{index}",
            deadline=deadline,
            clock=clock,
            context=context,
        )
        results.append(bundle)
        if timed_out:
            results.extend(_metadata_only(remaining, _TIMEOUT_LIMITATION) for remaining in items[index + 1:])
            break
    return results


def _attachment_worker(
    item: StoredAttachment,
    source_id: str,
    deadline: float,
    send_connection: Connection,
) -> None:
    try:
        send_connection.send(_parse_one_bundle(item, source_id, deadline=deadline))
    except Exception:
        return
    finally:
        send_connection.close()


def _parse_in_worker(
    item: StoredAttachment,
    *,
    source_id: str,
    deadline: float,
    clock: Callable[[], float],
    context: BaseContext,
) -> tuple[AttachmentAnalysisBundle, bool]:
    try:
        receive_connection, send_connection = context.Pipe(duplex=False)
    except Exception:
        return _metadata_only(item, _WORKER_FAILURE_LIMITATION), False
    process = None
    started = False
    try:
        try:
            process = context.Process(
                target=_attachment_worker,
                args=(item, source_id, deadline, send_connection),
            )
            process.start()
            started = True
            send_connection.close()
        except Exception:
            return _metadata_only(item, _WORKER_FAILURE_LIMITATION), False
        message, timed_out = _receive_message(process, receive_connection, deadline, clock)
        if timed_out:
            _stop_process(process)
            return _metadata_only(item, _TIMEOUT_LIMITATION), True
        _finish_process(process)
        if clock() >= deadline:
            return _metadata_only(item, _TIMEOUT_LIMITATION), True
        if _valid_worker_bundle(message, item, source_id):
            return message, False
        return _metadata_only(item, _WORKER_FAILURE_LIMITATION), False
    finally:
        if not send_connection.closed:
            send_connection.close()
        if started and process is not None and process.is_alive():
            _stop_process(process)
        receive_connection.close()


def _receive_message(
    process: Any,
    receive_connection: Connection,
    deadline: float,
    clock: Callable[[], float],
) -> tuple[object | None, bool]:
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            return None, True
        try:
            if receive_connection.poll(min(_POLL_INTERVAL_SECONDS, remaining)):
                if clock() >= deadline:
                    return None, True
                return receive_connection.recv(), False
        except Exception:
            return None, False
        if not process.is_alive():
            return None, False


def _finish_process(process: Any) -> None:
    process.join(_JOIN_TIMEOUT_SECONDS)
    if process.is_alive():
        _stop_process(process)


def _stop_process(process: Any) -> None:
    try:
        process.terminate()
    except Exception:
        pass
    try:
        process.join(_JOIN_TIMEOUT_SECONDS)
    except Exception:
        pass
    try:
        alive = process.is_alive()
    except Exception:
        alive = False
    if alive:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.join(_JOIN_TIMEOUT_SECONDS)
        except Exception:
            pass


def _parse_one_bundle(
    item: StoredAttachment,
    source_id: str,
    *,
    deadline: float | None = None,
) -> AttachmentAnalysisBundle:
    if deadline is not None and time.monotonic() >= deadline:
        return _metadata_only(item, _TIMEOUT_LIMITATION)
    extension_limitation = _extension_limitation(item)
    if extension_limitation:
        return _metadata_only(item, extension_limitation)

    parsers: dict[str, Callable[[StoredAttachment, str], AttachmentAnalysisBundle]] = {
        "pdf": _parse_pdf,
        "xlsx": _parse_xlsx,
        "docx": _parse_docx,
    }
    if item.type == "image":
        try:
            return _parse_image(item, source_id, deadline=deadline)
        except Exception:
            return _metadata_only(item, decoder_failure_limitation(item.type))
    parser = parsers.get(item.type)
    if parser is None:
        return _metadata_only(item, "Unsupported attachment type.")
    try:
        return parser(item, source_id)
    except Exception:
        return _metadata_only(item, decoder_failure_limitation(item.type))

def _parse_pdf(item: StoredAttachment, source_id: str) -> AttachmentAnalysisBundle:
    return parse_pdf_bundle(item, source_id, PdfReader, _text_insight)

def _parse_xlsx(item: StoredAttachment, source_id: str) -> AttachmentAnalysisBundle:
    return parse_xlsx_bundle(item, source_id, load_workbook, _text_insight)

def _parse_docx(item: StoredAttachment, source_id: str) -> AttachmentAnalysisBundle:
    return parse_docx_bundle(item, source_id, Document, _text_insight)

def _parse_image(
    item: StoredAttachment,
    source_id: str,
    *,
    deadline: float | None = None,
) -> AttachmentAnalysisBundle:
    with Image.open(item.path) as image:
        width, height = image.size
        image.verify()
    dimensions = f"Image dimensions: {width} x {height}."
    if width * height > MAX_IMAGE_PIXELS:
        return _metadata_only(item, "Image pixel limit exceeded; OCR was not attempted.", [dimensions])
    if pytesseract is None:
        return _metadata_only(item, "OCR is unavailable; image metadata only.", [dimensions])
    ocr_timeout = OCR_TIMEOUT_SECONDS
    if deadline is not None:
        ocr_timeout = max(0, min(5, deadline - time.monotonic() - 1))
        if ocr_timeout <= 0:
            return _metadata_only(item, _TIMEOUT_LIMITATION, [dimensions])
    try:
        with Image.open(item.path) as image:
            collector = TextBudget()
            collector.add(
                pytesseract.image_to_string(image, timeout=ocr_timeout),
                MAX_OCR_CHARACTERS,
            )
    except Exception:
        return _metadata_only(item, "OCR could not be completed; image metadata only.", [dimensions])
    if not collector.text:
        return _metadata_only(item, "OCR returned no readable text; image metadata only.", [dimensions])
    return _text_insight(
        item,
        source_id,
        collector.text,
        _character_limitations(collector),
        "Image OCR",
        [dimensions],
        fact_text=collector.fact_text,
    )

def _extension_limitation(item: StoredAttachment) -> str | None:
    return _extension_limitation_for(item, _ALLOWED_SUFFIXES)
