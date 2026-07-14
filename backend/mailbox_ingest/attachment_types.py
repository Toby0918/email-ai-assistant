"""Shared strict MIME allowlist for the reviewed attachment pass."""

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PNG = "image/png"
JPEG = "image/jpeg"
TIFF = "image/tiff"
SUPPORTED_MIME_TYPES = frozenset({PDF, DOCX, XLSX, PNG, JPEG, TIFF})


__all__ = [
    "DOCX",
    "JPEG",
    "PDF",
    "PNG",
    "SUPPORTED_MIME_TYPES",
    "TIFF",
    "XLSX",
]
