"""Pure, request-local sanitation for model-neutral image and PDF media."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Iterable

from .attachment_storage import StoredAttachment
from .image_media_safety import ImageSanitizationError, sanitize_image_content
from .pdf_media_safety import (
    MAX_PDF_PAGES,
    PdfSanitizationError,
    sanitize_pdf_content,
)


MAX_IMAGE_PIXELS = 25_000_000
MAX_SOURCE_IMAGE_DIMENSION = 16_384
MAX_IMAGE_DIMENSION = 2_048
MAX_IMAGE_FRAMES = 32
MAX_PREPARED_MEDIA_ASSETS = 12
MAX_PREPARED_MEDIA_BYTES = 20 * 1024 * 1024
MAX_ATTACHMENT_MEDIA_INPUT_BYTES = 10 * 1024 * 1024
MAX_SANITIZED_ASSET_BYTES = 10 * 1024 * 1024
_MAX_OPAQUE_ASSET_INDEX = 9_999

_ERROR_MESSAGE = "Media could not be prepared safely."
_SOURCE_ID = re.compile(r"attachment:[0-9]+\Z")
_PROVIDER_FILENAME = re.compile(r"(?:image_[0-9]+\.png|attachment_[0-9]+\.pdf)\Z")
_IMAGE_CONTRACT = ("image/png", "image")
_PDF_CONTRACT = ("application/pdf", "file")


class MediaPreparationError(ValueError):
    """A fixed, content-free failure at the media sanitation boundary."""


@dataclass(frozen=True, slots=True, repr=False)
class PreparedMediaAsset:
    """A provider-neutral media value whose bytes live only for one request."""

    source_id: str
    provider_filename: str
    mime_type: str
    kind: str
    detail: str
    buffer: bytearray

    def __post_init__(self) -> None:
        contract = (self.provider_filename.rsplit(".", 1)[-1], self.mime_type, self.kind)
        if (
            type(self.buffer) is not bytearray
            or not self.buffer
            or len(self.buffer) > MAX_SANITIZED_ASSET_BYTES
            or not _SOURCE_ID.fullmatch(self.source_id)
            or not _PROVIDER_FILENAME.fullmatch(self.provider_filename)
            or contract not in {
                ("png", *_IMAGE_CONTRACT),
                ("pdf", *_PDF_CONTRACT),
            }
            or self.detail != "high"
        ):
            raise ValueError("Prepared media asset is invalid.")

    def wipe(self) -> None:
        """Best-effort overwrite and release of the mutable request buffer."""
        for index in range(len(self.buffer)):
            self.buffer[index] = 0
        self.buffer.clear()


def wipe_prepared_media(assets: Iterable[PreparedMediaAsset]) -> None:
    """Best-effort wipe every request-local asset without exposing failures."""
    for asset in assets:
        try:
            asset.wipe()
        except Exception:
            continue


def sanitize_image_bytes(
    content: bytes | bytearray,
    *,
    declared_mime: str,
    source_id: str,
    asset_index: int,
) -> PreparedMediaAsset:
    """Verify one image, apply orientation, flatten it, and emit metadata-free PNG."""
    try:
        raw = _bounded_binary(content)
        prepared = sanitize_image_content(
            raw,
            declared_mime,
            max_source_dimension=MAX_SOURCE_IMAGE_DIMENSION,
            max_pixels=MAX_IMAGE_PIXELS,
            max_frames=MAX_IMAGE_FRAMES,
            max_output_dimension=MAX_IMAGE_DIMENSION,
            max_output_bytes=MAX_SANITIZED_ASSET_BYTES,
        )
        return PreparedMediaAsset(
            source_id=source_id,
            provider_filename=f"image_{_asset_number(asset_index)}.png",
            mime_type="image/png",
            kind="image",
            detail="high",
            buffer=bytearray(prepared),
        )
    except ImageSanitizationError:
        raise MediaPreparationError(_ERROR_MESSAGE) from None
    except Exception:
        raise MediaPreparationError(_ERROR_MESSAGE) from None


def sanitize_pdf_bytes(
    content: bytes | bytearray,
    *,
    source_id: str,
    asset_index: int,
) -> PreparedMediaAsset:
    """Rewrite a bounded PDF into a new document with active surfaces removed."""
    try:
        prepared = sanitize_pdf_content(content)
        return PreparedMediaAsset(
            source_id=source_id,
            provider_filename=f"attachment_{_asset_number(asset_index)}.pdf",
            mime_type="application/pdf",
            kind="file",
            detail="high",
            buffer=bytearray(prepared),
        )
    except PdfSanitizationError:
        raise MediaPreparationError(_ERROR_MESSAGE) from None
    except Exception:
        raise MediaPreparationError(_ERROR_MESSAGE) from None


def image_mime_for_filename(filename: str) -> str | None:
    """Return the fixed MIME implied by a safe image suffix."""
    suffix = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "tif": "image/tiff",
        "tiff": "image/tiff",
        "webp": "image/webp",
    }.get(suffix)


def prepare_attachment_media(
    items: Sequence[StoredAttachment],
) -> tuple[PreparedMediaAsset, ...]:
    """Prepare a globally bounded tuple while preserving parent attachment indices."""
    from .office_embedded_media import extract_office_media

    accepted: list[PreparedMediaAsset] = []
    total_bytes = 0
    pending: tuple[PreparedMediaAsset, ...] = ()
    try:
        for attachment_index, item in enumerate(items):
            if len(accepted) >= MAX_PREPARED_MEDIA_ASSETS:
                break
            try:
                candidates = _prepare_one_attachment(
                    item, attachment_index, len(accepted), extract_office_media
                )
            except (MediaPreparationError, OSError, ValueError):
                continue
            pending = candidates
            total_bytes, stopped = _accept_candidates(accepted, candidates, total_bytes)
            if stopped:
                return tuple(accepted)
            pending = ()
        return tuple(accepted)
    except Exception:
        wipe_prepared_media(pending)
        wipe_prepared_media(accepted)
        raise


def _prepare_one_attachment(
    item: StoredAttachment,
    attachment_index: int,
    asset_index: int,
    extract_office_media: Callable[..., tuple[PreparedMediaAsset, ...]],
) -> tuple[PreparedMediaAsset, ...]:
    content = _read_stored_content(item)
    source_id = f"attachment:{attachment_index}"
    if item.type == "image":
        mime = image_mime_for_filename(item.safe_filename)
        if mime is None:
            return ()
        return (sanitize_image_bytes(
            content, declared_mime=mime, source_id=source_id, asset_index=asset_index
        ),)
    if item.type == "pdf" and item.safe_filename.casefold().endswith(".pdf"):
        return (sanitize_pdf_bytes(
            content, source_id=source_id, asset_index=asset_index
        ),)
    if item.type in {"docx", "xlsx"} and item.safe_filename.casefold().endswith(
        f".{item.type}"
    ):
        return extract_office_media(
            content,
            attachment_type=item.type,
            source_id=source_id,
            start_index=asset_index,
        )
    return ()


def _accept_candidates(
    accepted: list[PreparedMediaAsset],
    candidates: tuple[PreparedMediaAsset, ...],
    total_bytes: int,
) -> tuple[int, bool]:
    for offset, candidate in enumerate(candidates):
        next_total = total_bytes + len(candidate.buffer)
        if len(accepted) >= MAX_PREPARED_MEDIA_ASSETS or next_total > MAX_PREPARED_MEDIA_BYTES:
            wipe_prepared_media(candidates[offset:])
            return total_bytes, True
        accepted.append(candidate)
        total_bytes = next_total
    return total_bytes, False


def _bounded_binary(content: bytes | bytearray) -> bytes:
    if type(content) not in {bytes, bytearray} or not content:
        raise MediaPreparationError(_ERROR_MESSAGE)
    if len(content) > MAX_ATTACHMENT_MEDIA_INPUT_BYTES:
        raise MediaPreparationError(_ERROR_MESSAGE)
    return bytes(content)


def _read_stored_content(item: StoredAttachment) -> bytes:
    if not isinstance(item, StoredAttachment) or item.byte_size < 1:
        raise MediaPreparationError(_ERROR_MESSAGE)
    if item.byte_size > MAX_ATTACHMENT_MEDIA_INPUT_BYTES:
        raise MediaPreparationError(_ERROR_MESSAGE)
    with item.path.open("rb") as handle:
        content = handle.read(MAX_ATTACHMENT_MEDIA_INPUT_BYTES + 1)
    if len(content) != item.byte_size or len(content) > MAX_ATTACHMENT_MEDIA_INPUT_BYTES:
        raise MediaPreparationError(_ERROR_MESSAGE)
    return content


def _asset_number(value: int) -> int:
    if type(value) is not int or value < 0 or value > _MAX_OPAQUE_ASSET_INDEX:
        raise MediaPreparationError(_ERROR_MESSAGE)
    return value
