"""Bounded extraction of supported embedded Office package images."""

from __future__ import annotations

import io
import stat
from pathlib import PurePosixPath
from zipfile import BadZipFile, LargeZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from . import attachment_safety
from .multimodal_media import (
    MediaPreparationError,
    PreparedMediaAsset,
    image_mime_for_filename,
    sanitize_image_bytes,
    wipe_prepared_media,
)


MAX_OFFICE_PACKAGE_ENTRIES = 256
MAX_OFFICE_ENTRY_BYTES = 10 * 1024 * 1024
MAX_OFFICE_TOTAL_BYTES = 25 * 1024 * 1024
MAX_OFFICE_COMPRESSION_RATIO = 100
MAX_OFFICE_MEDIA_COUNT = 8
MAX_OFFICE_MEDIA_ENTRY_BYTES = 5 * 1024 * 1024
MAX_OFFICE_MEDIA_TOTAL_BYTES = 10 * 1024 * 1024
MAX_OFFICE_ENTRY_NAME_BYTES = 240

_ERROR_MESSAGE = "Office media could not be prepared safely."
_MEDIA_PREFIX = {"docx": "word/media/", "xlsx": "xl/media/"}


def extract_office_media(
    content: bytes | bytearray,
    *,
    attachment_type: str,
    source_id: str,
    start_index: int,
) -> tuple[PreparedMediaAsset, ...]:
    """Return sanitized images from one bounded DOCX or XLSX package."""
    prefix = _MEDIA_PREFIX.get(attachment_type)
    if prefix is None or type(content) not in {bytes, bytearray} or not content:
        raise MediaPreparationError(_ERROR_MESSAGE)
    assets: list[PreparedMediaAsset] = []
    try:
        if attachment_safety.office_package_input_exceeds_limit(len(content)):
            raise MediaPreparationError(_ERROR_MESSAGE)
        raw = bytes(content)
        if not raw.startswith(b"PK\x03\x04"):
            raise MediaPreparationError(_ERROR_MESSAGE)
        with ZipFile(io.BytesIO(raw), mode="r", allowZip64=False) as package:
            return _extract_package_media(
                package, attachment_type, prefix, source_id, start_index, assets
            )
    except MediaPreparationError:
        wipe_prepared_media(assets)
        raise
    except (BadZipFile, LargeZipFile, RuntimeError, OSError, EOFError, ValueError):
        wipe_prepared_media(assets)
        raise MediaPreparationError(_ERROR_MESSAGE) from None
    except Exception:
        wipe_prepared_media(assets)
        raise


def _extract_package_media(
    package: ZipFile,
    attachment_type: str,
    prefix: str,
    source_id: str,
    start_index: int,
    assets: list[PreparedMediaAsset],
) -> tuple[PreparedMediaAsset, ...]:
    entries = package.infolist()
    _validate_package(package, entries, attachment_type)
    media_entries = _media_entries(entries, prefix)
    if len(media_entries) > MAX_OFFICE_MEDIA_COUNT:
        raise MediaPreparationError(_ERROR_MESSAGE)
    total_media = 0
    for entry in media_entries:
        total_media += entry.file_size
        if (
            entry.file_size > MAX_OFFICE_MEDIA_ENTRY_BYTES
            or total_media > MAX_OFFICE_MEDIA_TOTAL_BYTES
        ):
            raise MediaPreparationError(_ERROR_MESSAGE)
        payload = package.read(entry)
        if len(payload) != entry.file_size:
            raise MediaPreparationError(_ERROR_MESSAGE)
        mime = image_mime_for_filename(entry.filename)
        if mime is None:
            continue
        asset = sanitize_image_bytes(
            payload,
            declared_mime=mime,
            source_id=source_id,
            asset_index=start_index + len(assets),
        )
        if sum(len(item.buffer) for item in assets) + len(asset.buffer) > MAX_OFFICE_MEDIA_TOTAL_BYTES:
            asset.wipe()
            raise MediaPreparationError(_ERROR_MESSAGE)
        assets.append(asset)
    return tuple(assets)


def _validate_package(
    package: ZipFile, entries: list[ZipInfo], attachment_type: str
) -> None:
    if len(entries) > MAX_OFFICE_PACKAGE_ENTRIES:
        raise MediaPreparationError(_ERROR_MESSAGE)
    total_size = 0
    names: set[str] = set()
    for entry in entries:
        _validate_entry_name(entry)
        normalized_name = entry.filename.casefold()
        if normalized_name in names:
            raise MediaPreparationError(_ERROR_MESSAGE)
        names.add(normalized_name)
        if (
            not attachment_safety.office_zip_entry_header_is_safe(package, entry)
            or entry.flag_bits & 0x1
            or _is_symlink(entry)
            or entry.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
        ):
            raise MediaPreparationError(_ERROR_MESSAGE)
        if entry.file_size > MAX_OFFICE_ENTRY_BYTES:
            raise MediaPreparationError(_ERROR_MESSAGE)
        total_size += entry.file_size
        if total_size > MAX_OFFICE_TOTAL_BYTES:
            raise MediaPreparationError(_ERROR_MESSAGE)
        if entry.file_size:
            if entry.compress_size <= 0:
                raise MediaPreparationError(_ERROR_MESSAGE)
            if entry.file_size > entry.compress_size * MAX_OFFICE_COMPRESSION_RATIO:
                raise MediaPreparationError(_ERROR_MESSAGE)
    required_root = "word/document.xml" if attachment_type == "docx" else "xl/workbook.xml"
    if "[Content_Types].xml".casefold() not in names or required_root.casefold() not in names:
        raise MediaPreparationError(_ERROR_MESSAGE)


def _validate_entry_name(entry: ZipInfo) -> None:
    name = entry.orig_filename
    trimmed = name[:-1] if name.endswith("/") else name
    raw_parts = trimmed.split("/")
    if (
        not trimmed
        or entry.orig_filename != entry.filename
        or len(name.encode("utf-8")) > MAX_OFFICE_ENTRY_NAME_BYTES
        or "\\" in name
        or name.startswith("/")
        or any(part in {"", ".", ".."} for part in raw_parts)
        or any(":" in part for part in raw_parts)
        or any(any(ord(character) < 32 or ord(character) == 127 for character in part) for part in raw_parts)
        or PurePosixPath(trimmed).is_absolute()
    ):
        raise MediaPreparationError(_ERROR_MESSAGE)


def _media_entries(entries: list[ZipInfo], prefix: str) -> list[ZipInfo]:
    accepted: list[ZipInfo] = []
    for entry in entries:
        if entry.is_dir() or not entry.filename.startswith(prefix):
            continue
        remainder = entry.filename[len(prefix):]
        if not remainder or "/" in remainder:
            raise MediaPreparationError(_ERROR_MESSAGE)
        if image_mime_for_filename(remainder) is not None:
            accepted.append(entry)
    return accepted


def _is_symlink(entry: ZipInfo) -> bool:
    return stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK
