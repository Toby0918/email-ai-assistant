"""Deterministic immutable startup package built from held CPython files."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from .canonical import fail

_ERROR = "runtime_python_source_invalid"
_MAX_FILES = 256
_MAX_SOURCE_BYTES = 4 * 1024 * 1024
_MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
_REQUIRED = {
    "encodings/__init__.py",
    "encodings/aliases.py",
    "encodings/utf_8.py",
}


def build_startup_archive(api, files) -> bytes:
    selected = _select_encoding_files(files)
    output = BytesIO()
    try:
        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_STORED
        ) as archive:
            for name, handle, size in selected:
                _write_member(api, archive, output, name, handle, size)
        payload = output.getvalue()
    except (OSError, RuntimeError, zipfile.BadZipFile):
        fail(_ERROR)
    if not 1 <= len(payload) <= _MAX_ARCHIVE_BYTES:
        fail(_ERROR)
    return payload


def _select_encoding_files(files):
    selected = [
        (
            PurePosixPath(*parts[1:]).as_posix(),
            handle,
            size,
        )
        for parts, handle, size in files
        if len(parts) >= 3 and parts[:2] == ("Lib", "encodings")
    ]
    selected.sort(key=lambda item: item[0].casefold())
    names = [item[0] for item in selected]
    if (
        not _REQUIRED.issubset(names)
        or not 1 <= len(selected) <= _MAX_FILES
        or len(set(name.casefold() for name in names)) != len(names)
        or sum(item[2] for item in selected) > _MAX_SOURCE_BYTES
    ):
        fail(_ERROR)
    return tuple(selected)


def _write_member(api, archive, output, name, handle, size) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 0
    info.external_attr = 0
    api.reset(handle)
    remaining = size
    with archive.open(info, "w", force_zip64=False) as destination:
        while remaining:
            block = api.read_block(
                handle, length=min(64 * 1024, remaining)
            )
            if not block or len(block) > remaining:
                fail(_ERROR)
            destination.write(block)
            remaining -= len(block)
            if output.tell() > _MAX_ARCHIVE_BYTES:
                fail(_ERROR)
