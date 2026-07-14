"""Magic and active-content checks for representative attachments."""

from __future__ import annotations

import io
import zipfile

from .attachment_manifest import AttachmentScanError
from .attachment_types import (
    DOCX,
    JPEG,
    PDF,
    PNG,
    SUPPORTED_MIME_TYPES,
    TIFF,
    XLSX,
)


def validate_attachment_content(content: bytes, mime_type: str) -> None:
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise AttachmentScanError("attachment_type_unsupported")
    if mime_type == PDF:
        _validate_pdf(content)
    elif mime_type in {DOCX, XLSX}:
        _validate_ooxml(content, mime_type)
    elif mime_type == PNG and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AttachmentScanError("attachment_magic_mismatch")
    elif mime_type == JPEG and not content.startswith(b"\xff\xd8\xff"):
        raise AttachmentScanError("attachment_magic_mismatch")
    elif mime_type == TIFF and not content.startswith((b"II*\x00", b"MM\x00*")):
        raise AttachmentScanError("attachment_magic_mismatch")


def _validate_pdf(content: bytes) -> None:
    if not content.startswith(b"%PDF-"):
        raise AttachmentScanError("attachment_magic_mismatch")
    normalized = content.lower()
    forbidden = (b"/javascript", b"/js", b"/launch", b"/embeddedfiles")
    if any(marker in normalized for marker in forbidden):
        raise AttachmentScanError("attachment_active_content")


def _validate_ooxml(content: bytes, mime_type: str) -> None:
    if not content.startswith(b"PK\x03\x04"):
        raise AttachmentScanError("attachment_magic_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > 10_000:
                raise AttachmentScanError("attachment_active_content")
            total = 0
            names: set[str] = set()
            for info in infos:
                normalized = info.filename.replace("\\", "/").lower()
                if (
                    normalized.startswith("/")
                    or "../" in normalized
                    or normalized in names
                    or info.file_size > 20 * 1024 * 1024
                ):
                    raise AttachmentScanError("attachment_active_content")
                names.add(normalized)
                total += info.file_size
                if total > 50 * 1024 * 1024:
                    raise AttachmentScanError("attachment_active_content")
                if any(
                    marker in normalized
                    for marker in ("vbaproject.bin", "oleobject", "embeddings/")
                ):
                    raise AttachmentScanError("attachment_active_content")
                if normalized.endswith((".rels", "[content_types].xml")):
                    data = archive.read(info)
                    lowered = data.lower()
                    if (
                        b'targetmode="external"' in lowered
                        or b"macroenabled" in lowered
                        or b"vnd.ms-office.vba" in lowered
                    ):
                        raise AttachmentScanError("attachment_active_content")
            required = "word/document.xml" if mime_type == DOCX else "xl/workbook.xml"
            if "[content_types].xml" not in names or required not in names:
                raise AttachmentScanError("attachment_magic_mismatch")
    except AttachmentScanError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, KeyError):
        raise AttachmentScanError("attachment_magic_mismatch") from None


__all__ = ["SUPPORTED_MIME_TYPES", "validate_attachment_content"]
