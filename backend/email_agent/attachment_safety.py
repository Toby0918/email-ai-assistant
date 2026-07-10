"""Resource guards applied before third-party attachment decoders run."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from zipfile import BadZipFile, LargeZipFile, ZipFile

import pypdf.filters as pypdf_filters


PDF_DECODED_STREAM_MAX_BYTES = 10 * 1024 * 1024
OFFICE_ZIP_MAX_ENTRIES = 256
OFFICE_ZIP_MAX_ENTRY_BYTES = 10 * 1024 * 1024
OFFICE_ZIP_MAX_TOTAL_BYTES = 25 * 1024 * 1024

_PDF_LIMIT_NAMES = (
    "ZLIB_MAX_OUTPUT_LENGTH",
    "LZW_MAX_OUTPUT_LENGTH",
    "RUN_LENGTH_MAX_OUTPUT_LENGTH",
    "JBIG2_MAX_OUTPUT_LENGTH",
    "MAX_DECLARED_STREAM_LENGTH",
    "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
)
_PDF_LIMIT_LOCK = Lock()
_DECODER_FAILURE_LIMITATIONS = {
    "pdf": "PDF content could not be decoded safely.",
    "xlsx": "XLSX workbook content could not be parsed safely.",
    "docx": "DOCX document content could not be parsed safely.",
    "image": "Image content could not be verified safely.",
}


def enforce_pdf_decoder_limits() -> None:
    """Apply the project PDF stream cap process-wide without weakening stricter caps."""
    with _PDF_LIMIT_LOCK:
        for name in _PDF_LIMIT_NAMES:
            current_limit = getattr(pypdf_filters, name, PDF_DECODED_STREAM_MAX_BYTES)
            safe_limit = min(current_limit, PDF_DECODED_STREAM_MAX_BYTES)
            setattr(pypdf_filters, name, safe_limit)


def office_package_limitation(path: Path, attachment_type: str) -> str | None:
    """Return a precise limitation when an Office ZIP package is unsafe to decode."""
    label = attachment_type.upper()
    try:
        with ZipFile(path) as package:
            entries = package.infolist()
    except (BadZipFile, LargeZipFile, OSError):
        return f"{label} package is malformed; attachment content was not parsed."
    if len(entries) > OFFICE_ZIP_MAX_ENTRIES:
        return f"{label} package entry count exceeds the parser limit."

    total_size = 0
    for entry in entries:
        if entry.file_size > OFFICE_ZIP_MAX_ENTRY_BYTES:
            return f"{label} package entry size exceeds the parser limit."
        total_size += entry.file_size
        if total_size > OFFICE_ZIP_MAX_TOTAL_BYTES:
            return f"{label} package total uncompressed size exceeds the parser limit."
    return None


def decoder_failure_limitation(attachment_type: str) -> str:
    """Return a type-specific failure without exception or source details."""
    return _DECODER_FAILURE_LIMITATIONS.get(
        attachment_type,
        "Attachment content could not be parsed safely.",
    )


enforce_pdf_decoder_limits()
