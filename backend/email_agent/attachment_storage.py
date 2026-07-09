"""Bounded temporary storage for user-confirmed visible attachments."""

from __future__ import annotations

import base64
import binascii
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import AppConfig


SUPPORTED_ATTACHMENT_TYPES = {"image", "pdf", "xlsx", "docx"}
_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class AttachmentInputError(ValueError):
    """Raised when a user-confirmed attachment cannot be safely stored."""


@dataclass(frozen=True)
class StoredAttachment:
    """Internal metadata for a contained temporary attachment file."""

    safe_filename: str
    type: str
    path: Path
    byte_size: int
    expires_at: datetime


def store_attachment_files(files: list[dict[str, object]], config: AppConfig) -> list[StoredAttachment]:
    """Validate and store current-email attachment bytes in the configured temp directory."""
    decoded_files = _decode_and_validate_files(files, config)
    storage_dir = _storage_dir(config)
    expires_at = datetime.now(UTC) + timedelta(hours=config.attachment_retention_hours)
    return [_store_one_attachment(item, storage_dir, expires_at) for item in decoded_files]


def cleanup_expired_attachments(config: AppConfig, now: datetime | None = None) -> int:
    """Delete contained temp files whose expiry timestamp has passed."""
    storage_dir = _storage_dir(config)
    cutoff = (now or datetime.now(UTC)).timestamp()
    removed = 0
    for path in storage_dir.iterdir():
        if not path.is_file() or path.resolve().parent != storage_dir:
            continue
        if path.stat().st_mtime <= cutoff:
            path.unlink()
            removed += 1
    return removed


def _decode_and_validate_files(
    files: list[dict[str, object]], config: AppConfig
) -> list[tuple[str, str, bytes]]:
    if not isinstance(files, list):
        raise AttachmentInputError("Attachment files must be a list.")
    if len(files) > config.attachment_max_files:
        raise AttachmentInputError("Attachment file count exceeds the configured limit.")

    decoded_files: list[tuple[str, str, bytes]] = []
    total_size = 0
    for file_data in files:
        if not isinstance(file_data, dict):
            raise AttachmentInputError("Attachment file entries must be objects.")
        safe_filename = _safe_filename(file_data.get("filename"))
        attachment_type = _attachment_type(file_data.get("type"))
        content = _decode_content(file_data.get("content_base64"))
        byte_size = len(content)
        if byte_size > config.attachment_max_file_bytes:
            raise AttachmentInputError("Attachment file exceeds the configured byte limit.")
        total_size += byte_size
        if total_size > config.attachment_max_total_bytes:
            raise AttachmentInputError("Attachment total exceeds the configured byte limit.")
        decoded_files.append((safe_filename, attachment_type, content))
    return decoded_files


def _store_one_attachment(
    file_data: tuple[str, str, bytes], storage_dir: Path, expires_at: datetime
) -> StoredAttachment:
    safe_filename, attachment_type, content = file_data
    path = (storage_dir / f"{uuid4().hex}_{safe_filename}").resolve()
    if path.parent != storage_dir:
        raise AttachmentInputError("Attachment path is outside the temporary storage directory.")
    with path.open("xb") as file_handle:
        file_handle.write(content)
    os.utime(path, (datetime.now(UTC).timestamp(), expires_at.timestamp()))
    return StoredAttachment(
        safe_filename=safe_filename,
        type=attachment_type,
        path=path,
        byte_size=len(content),
        expires_at=expires_at,
    )


def _storage_dir(config: AppConfig) -> Path:
    storage_dir = Path(config.attachment_temp_dir).resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def _safe_filename(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AttachmentInputError("Attachment filename is required.")
    name = value.replace("\\", "/").rsplit("/", 1)[-1]
    safe_name = _FILENAME_PATTERN.sub("_", name).strip("._")[:120]
    if not safe_name:
        raise AttachmentInputError("Attachment filename is invalid.")
    return safe_name


def _attachment_type(value: Any) -> str:
    if not isinstance(value, str):
        raise AttachmentInputError("Attachment type is required.")
    attachment_type = value.strip().lower()
    if attachment_type not in SUPPORTED_ATTACHMENT_TYPES:
        raise AttachmentInputError("Attachment type is not supported.")
    return attachment_type


def _decode_content(value: Any) -> bytes:
    if not isinstance(value, str) or not value:
        raise AttachmentInputError("Attachment content is required.")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AttachmentInputError("Attachment content is not valid base64.") from exc
