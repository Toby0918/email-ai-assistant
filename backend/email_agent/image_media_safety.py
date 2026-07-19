"""Bounded decode and metadata-free re-encode for request-local images."""

from __future__ import annotations

import io
import warnings

from PIL import Image, ImageOps


_ERROR_MESSAGE = "Image could not be prepared safely."
_IMAGE_MAGIC_MIMES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
)


class ImageSanitizationError(ValueError):
    """A fixed, content-free image sanitation failure."""


def sanitize_image_content(
    raw: bytes,
    declared_mime: str,
    *,
    max_source_dimension: int,
    max_pixels: int,
    max_frames: int,
    max_output_dimension: int,
    max_output_bytes: int,
) -> bytes:
    """Verify, flatten, orient, and re-encode one image as a fresh PNG."""
    try:
        if _image_magic_mime(raw) != declared_mime:
            raise ImageSanitizationError(_ERROR_MESSAGE)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            _verify_source(
                raw, declared_mime, max_source_dimension, max_pixels, max_frames
            )
            prepared = _reencode_first_frame(raw, max_output_dimension)
        if not prepared or len(prepared) > max_output_bytes:
            raise ImageSanitizationError(_ERROR_MESSAGE)
        _audit_output(prepared, max_output_dimension, max_pixels)
        return prepared
    except ImageSanitizationError:
        raise
    except Exception:
        raise ImageSanitizationError(_ERROR_MESSAGE) from None


def _verify_source(
    raw: bytes,
    declared_mime: str,
    max_source_dimension: int,
    max_pixels: int,
    max_frames: int,
) -> None:
    with Image.open(io.BytesIO(raw)) as candidate:
        width, height = candidate.size
        invalid = (
            _pillow_format_mime(candidate.format) != declared_mime
            or width <= 0
            or height <= 0
            or width > max_source_dimension
            or height > max_source_dimension
            or width * height > max_pixels
            or int(getattr(candidate, "n_frames", 1)) > max_frames
        )
        if invalid:
            raise ImageSanitizationError(_ERROR_MESSAGE)
        candidate.verify()


def _reencode_first_frame(raw: bytes, max_output_dimension: int) -> bytes:
    with Image.open(io.BytesIO(raw)) as decoded:
        decoded.seek(0)
        oriented = ImageOps.exif_transpose(decoded)
        pixels = oriented.convert("RGBA" if "A" in oriented.getbands() else "RGB")
        pixels.thumbnail(
            (max_output_dimension, max_output_dimension), Image.Resampling.LANCZOS
        )
        clean = Image.frombytes(pixels.mode, pixels.size, pixels.tobytes())
        output = io.BytesIO()
        clean.save(output, format="PNG", optimize=False)
        clean.close()
        if oriented is not decoded:
            oriented.close()
        pixels.close()
        return output.getvalue()


def _audit_output(content: bytes, max_dimension: int, max_pixels: int) -> None:
    with Image.open(io.BytesIO(content)) as image:
        image.verify()
    with Image.open(io.BytesIO(content)) as image:
        invalid = (
            image.format != "PNG"
            or int(getattr(image, "n_frames", 1)) != 1
            or max(image.size) > max_dimension
            or image.width * image.height > max_pixels
            or bool(image.getexif())
            or bool(image.info)
        )
        if invalid:
            raise ImageSanitizationError(_ERROR_MESSAGE)


def _image_magic_mime(content: bytes) -> str | None:
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    for prefix, mime in _IMAGE_MAGIC_MIMES:
        if content.startswith(prefix):
            return mime
    return None


def _pillow_format_mime(value: str | None) -> str | None:
    return {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "GIF": "image/gif",
        "BMP": "image/bmp",
        "TIFF": "image/tiff",
        "WEBP": "image/webp",
    }.get(str(value or "").upper())
