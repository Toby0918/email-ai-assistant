"""Resource guards applied before third-party attachment decoders run."""

from __future__ import annotations

from pathlib import Path
from pathlib import PurePosixPath
import stat
from threading import Lock
from zipfile import (
    BadZipFile,
    LargeZipFile,
    ZIP_DEFLATED,
    ZIP_STORED,
    ZipFile,
    ZipInfo,
)

import pypdf.filters as pypdf_filters


PDF_DECODED_STREAM_MAX_BYTES = 10 * 1024 * 1024
OFFICE_ZIP_MAX_ENTRIES = 256
OFFICE_ZIP_MAX_INPUT_BYTES = 10 * 1024 * 1024
OFFICE_ZIP_MAX_ENTRY_BYTES = 10 * 1024 * 1024
OFFICE_ZIP_MAX_TOTAL_BYTES = 25 * 1024 * 1024
OFFICE_ZIP_MAX_COMPRESSION_RATIO = 100
OFFICE_ZIP_MAX_NAME_BYTES = 240

_PDF_LIMIT_NAMES = (
    "ZLIB_MAX_OUTPUT_LENGTH",
    "LZW_MAX_OUTPUT_LENGTH",
    "RUN_LENGTH_MAX_OUTPUT_LENGTH",
    "JBIG2_MAX_OUTPUT_LENGTH",
    "MAX_DECLARED_STREAM_LENGTH",
    "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
)
_PDF_LIMIT_LOCK = Lock()
_ZIP_LOCAL_HEADER_BYTES = 30
_ZIP_LOCAL_HEADER_SIGNATURE = b"PK\x03\x04"
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
        if office_package_input_exceeds_limit(path.stat().st_size):
            return f"{label} package compressed size exceeds the parser limit."
        with ZipFile(path, allowZip64=False) as package:
            return _inspect_office_package(package, attachment_type, label)
    except (BadZipFile, LargeZipFile, OSError):
        return f"{label} package is malformed; attachment content was not parsed."


def _inspect_office_package(
    package: ZipFile, attachment_type: str, label: str
) -> str | None:
    entries = package.infolist()
    if len(entries) > OFFICE_ZIP_MAX_ENTRIES:
        return f"{label} package entry count exceeds the parser limit."
    total_size = 0
    for entry in entries:
        if entry.file_size > OFFICE_ZIP_MAX_ENTRY_BYTES:
            return f"{label} package entry size exceeds the parser limit."
        total_size += entry.file_size
        if total_size > OFFICE_ZIP_MAX_TOTAL_BYTES:
            return f"{label} package total uncompressed size exceeds the parser limit."
    names: set[str] = set()
    for entry in entries:
        if (
            not office_zip_entry_header_is_safe(package, entry)
            or _unsafe_office_entry(entry, names)
        ):
            return f"{label} package is unsafe; attachment content was not parsed."
        names.add(entry.filename.casefold())
    required_root = "word/document.xml" if attachment_type == "docx" else "xl/workbook.xml"
    if "[content_types].xml" not in names or required_root.casefold() not in names:
        return f"{label} package structure is invalid; attachment content was not parsed."
    return None


def office_package_input_exceeds_limit(byte_size: int) -> bool:
    """Apply one fixed compressed-package cap before any ZIP decoder opens."""
    return type(byte_size) is not int or byte_size < 0 or byte_size > OFFICE_ZIP_MAX_INPUT_BYTES


def office_zip_entry_header_is_safe(package: ZipFile, entry: ZipInfo) -> bool:
    """Require matching, unencrypted central and local general-purpose flags."""
    handle = package.fp
    if handle is None or type(entry.header_offset) is not int or entry.header_offset < 0:
        return False
    original_position: int | None = None
    safe = False
    try:
        original_position = handle.tell()
        handle.seek(0, 2)
        archive_size = handle.tell()
        if entry.header_offset > archive_size - _ZIP_LOCAL_HEADER_BYTES:
            return False
        handle.seek(entry.header_offset)
        header = handle.read(_ZIP_LOCAL_HEADER_BYTES)
        if len(header) != _ZIP_LOCAL_HEADER_BYTES:
            return False
        local_flags = int.from_bytes(header[6:8], "little")
        variable_size = int.from_bytes(header[26:28], "little") + int.from_bytes(
            header[28:30], "little"
        )
        safe = bool(
            header[:4] == _ZIP_LOCAL_HEADER_SIGNATURE
            and entry.header_offset + _ZIP_LOCAL_HEADER_BYTES + variable_size <= archive_size
            and local_flags == entry.flag_bits
            and not (local_flags & 0x1)
        )
    except (OSError, ValueError, AttributeError, OverflowError):
        safe = False
    finally:
        if original_position is not None:
            try:
                handle.seek(original_position)
            except (OSError, ValueError):
                safe = False
    return safe


def _unsafe_office_entry(entry: object, names: set[str]) -> bool:
    name = entry.orig_filename
    trimmed = name[:-1] if name.endswith("/") else name
    parts = trimmed.split("/")
    ratio_unsafe = (
        entry.file_size > 0
        and (
            entry.compress_size <= 0
            or entry.file_size > entry.compress_size * OFFICE_ZIP_MAX_COMPRESSION_RATIO
        )
    )
    mode = stat.S_IFMT(entry.external_attr >> 16)
    return bool(
        not trimmed
        or entry.orig_filename != entry.filename
        or len(name.encode("utf-8")) > OFFICE_ZIP_MAX_NAME_BYTES
        or "\\" in name
        or name.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
        or any(":" in part for part in parts)
        or any(any(ord(character) < 32 or ord(character) == 127 for character in part) for part in parts)
        or PurePosixPath(trimmed).is_absolute()
        or entry.filename.casefold() in names
        or entry.flag_bits & 0x1
        or mode == stat.S_IFLNK
        or entry.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
        or ratio_unsafe
    )


def decoder_failure_limitation(attachment_type: str) -> str:
    """Return a type-specific failure without exception or source details."""
    return _DECODER_FAILURE_LIMITATIONS.get(
        attachment_type,
        "Attachment content could not be parsed safely.",
    )


enforce_pdf_decoder_limits()
