"""Second-pass retrieval of explicitly reviewed representative attachments."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .attachment_manifest import (
    MAX_CONVERSATION_BYTES,
    MAX_FILE_BYTES,
    AttachmentScanError,
    PreparedAttachment,
    PreparedAttachments,
    ReviewedManifest,
    parse_reviewed_manifest,
    prepare_attachments,
)
from .attachment_security import validate_attachment_content


DEFAULT_CHUNK_SIZE = 1024 * 1024
MAX_PARSED_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class AttachmentReport:
    selected_count: int
    fetched_count: int
    parsed_count: int
    new_blob_count: int
    duplicate_blob_count: int
    semantic_unreviewed_count: int

    def to_counts(self) -> dict[str, int]:
        return {
            "selected": self.selected_count,
            "supported": self.selected_count,
            "unsupported": 0,
            "fetched": self.fetched_count,
            "acquisition_failed": 0,
            "parsed": self.parsed_count,
            "parse_failed": 0,
            "new_blobs": self.new_blob_count,
            "duplicate_blobs": self.duplicate_blob_count,
            "semantic_unreviewed": self.semantic_unreviewed_count,
        }


def fetch_prepared_attachments(
    prepared: PreparedAttachments,
    *,
    session: object,
    vault: object,
    vault_root: Path,
    parser: Callable[[Path, str], bytes],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    clock: Callable[[], int] = lambda: int(time.time()),
    content_token_factory: Callable[[bytes], str],
    find_existing_blob: Callable[[str], str | None],
    bind_blob: Callable[[PreparedAttachment, str, str], object],
) -> AttachmentReport:
    if (
        not isinstance(prepared, PreparedAttachments)
        or type(chunk_size) is not int
        or not 1 <= chunk_size <= DEFAULT_CHUNK_SIZE
        or not callable(content_token_factory)
        or not callable(find_existing_blob)
        or not callable(bind_blob)
    ):
        raise AttachmentScanError("attachment_fetch_invalid")
    _require_manifest_current(prepared, clock)
    root = _prepare_temp_parent(Path(vault_root))
    new_blobs = 0
    duplicate_blobs = 0
    conversation_totals: dict[str, int] = {}
    for item in prepared.items:
        conversation_totals[item.source_record_id] = (
            conversation_totals.get(item.source_record_id, 0) + item.expected_size
        )
        if conversation_totals[item.source_record_id] > MAX_CONVERSATION_BYTES:
            raise AttachmentScanError("attachment_conversation_limit")
        created = _fetch_one(
            item, prepared, session, vault, root, parser, chunk_size, clock,
            content_token_factory, find_existing_blob, bind_blob,
        )
        new_blobs += int(created == "new")
        duplicate_blobs += int(created == "duplicate")
    selected = len(prepared.items)
    return AttachmentReport(
        selected, selected, selected, new_blobs, duplicate_blobs, new_blobs
    )


def _fetch_one(
    item: PreparedAttachment,
    prepared: PreparedAttachments,
    session: object,
    vault: object,
    temp_parent: Path,
    parser: Callable[[Path, str], bytes],
    chunk_size: int,
    clock: Callable[[], int],
    token_factory: Callable[[bytes], str],
    find_blob: Callable[[str], str | None],
    bind_blob: Callable[[PreparedAttachment, str, str], object],
) -> str:
    _require_uidvalidity(session, item)
    temporary: Path | None = None
    try:
        temporary = Path(tempfile.mkdtemp(prefix="attachment-", dir=temp_parent))
        os.chmod(temporary, 0o700)
        if temporary.is_symlink() or temporary.resolve().parent != temp_parent.resolve():
            raise AttachmentScanError("attachment_temp_invalid")
        payload_path = temporary / "payload.bin"
        content = _download(item, session, payload_path, chunk_size)
        validate_attachment_content(content, item.mime_type)
        try:
            parsed = parser(payload_path, item.mime_type)
        except Exception:
            raise AttachmentScanError("attachment_parse_failed") from None
        if type(parsed) is not bytes or len(parsed) > MAX_PARSED_BYTES:
            raise AttachmentScanError("attachment_parse_failed")
        _require_uidvalidity(session, item)
        _require_manifest_current(prepared, clock)
        return _persist_blob(
            item, content, vault, token_factory, find_blob, bind_blob
        )
    finally:
        if temporary is not None:
            try:
                shutil.rmtree(temporary)
            except OSError:
                raise AttachmentScanError("attachment_temp_cleanup_failed") from None


def _download(
    item: PreparedAttachment,
    session: object,
    path: Path,
    chunk_size: int,
) -> bytes:
    if not 1 <= item.expected_size <= MAX_FILE_BYTES:
        raise AttachmentScanError("attachment_file_limit")
    offset = 0
    chunks: list[bytes] = []
    try:
        with path.open("xb") as stream:
            os.chmod(path, 0o600)
            while offset < item.expected_size:
                request_count = min(chunk_size, item.expected_size - offset)
                chunk = session.uid_fetch_peek(
                    item.uid,
                    item.section,
                    offset=offset,
                    count=request_count,
                )
                if (
                    type(chunk) is not bytes
                    or not chunk
                    or len(chunk) > request_count
                    or offset + len(chunk) > item.expected_size
                ):
                    raise AttachmentScanError("attachment_transfer_size_mismatch")
                stream.write(chunk)
                chunks.append(chunk)
                offset += len(chunk)
            stream.flush()
            os.fsync(stream.fileno())
    except AttachmentScanError:
        raise
    except Exception:
        raise AttachmentScanError("attachment_fetch_failed") from None
    content = b"".join(chunks)
    if len(content) != item.expected_size or path.stat().st_size != item.expected_size:
        raise AttachmentScanError("attachment_transfer_size_mismatch")
    return content


def _attachment_record(content: bytes) -> bytes:
    return b"MAILBOX-ATTACHMENT-BLOB-V1\0" + content


def _persist_blob(
    item: PreparedAttachment, content: bytes, vault: object,
    token_factory: Callable[[bytes], str],
    find_blob: Callable[[str], str | None],
    bind_blob: Callable[[PreparedAttachment, str, str], object],
) -> str:
    try:
        with vault.coordinated_mutation():
            content_token = token_factory(content)
            blob_record_id = find_blob(content_token)
            result = vault.put_record_if_absent(
                _attachment_record(content),
                expires_at_utc=item.expires_at_utc,
                extend_expiry_on_duplicate=False,
            )
            if blob_record_id is None:
                blob_record_id = result.record_id
            elif result.record_id != blob_record_id:
                raise ValueError
            binding = bind_blob(item, blob_record_id, content_token)
            status = getattr(binding, "status", None)
            if status not in {"new", "duplicate"}:
                raise ValueError
            extended = vault.put_record_if_absent(
                _attachment_record(content),
                expires_at_utc=item.expires_at_utc,
                extend_expiry_on_duplicate=True,
            )
            if extended.record_id != blob_record_id or extended.created:
                raise ValueError
            return status
    except Exception:
        raise AttachmentScanError("attachment_persist_failed") from None


def _prepare_temp_parent(vault_root: Path) -> Path:
    try:
        root = vault_root.resolve(strict=True)
        if root.is_symlink() or not root.is_dir():
            raise AttachmentScanError("attachment_temp_invalid")
        parent = root / "restricted-temp"
        parent.mkdir(mode=0o700, exist_ok=True)
        if parent.is_symlink() or parent.resolve().parent != root:
            raise AttachmentScanError("attachment_temp_invalid")
        return parent
    except AttachmentScanError:
        raise
    except OSError:
        raise AttachmentScanError("attachment_temp_invalid") from None


def _require_uidvalidity(session: object, item: PreparedAttachment) -> None:
    try:
        actual = session.examine(item.mailbox)
    except Exception:
        raise AttachmentScanError("attachment_uidvalidity_check_failed") from None
    if actual != item.uidvalidity:
        raise AttachmentScanError("attachment_uidvalidity_changed")


def _require_manifest_current(
    prepared: PreparedAttachments,
    clock: Callable[[], int],
) -> None:
    try:
        now = clock()
    except Exception:
        raise AttachmentScanError("attachment_clock_invalid") from None
    if type(now) is not int or now >= prepared.expires_at_utc:
        raise AttachmentScanError("attachment_manifest_expired")


__all__ = [
    "AttachmentReport",
    "AttachmentScanError",
    "fetch_prepared_attachments",
    "parse_reviewed_manifest",
    "prepare_attachments",
]
