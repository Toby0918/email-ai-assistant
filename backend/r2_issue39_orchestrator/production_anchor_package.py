"""Deterministic retained restart-anchor package construction."""

from __future__ import annotations

import io
import stat
import sys
import zipfile
from pathlib import Path


def build_restart_anchor():
    current = Path(sys.argv[0])
    if current.suffix.casefold() == ".pyz" and current.is_file():
        return _held_bytes(current, 16 * 1024 * 1024)
    repository = Path(__file__).resolve().parents[2]
    files = tuple(sorted((repository / "backend").rglob("*.py")))
    if not 1 <= len(files) <= 1_024:
        raise ValueError
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        _zip_entry(
            archive,
            "__main__.py",
            b"from backend.r2_issue39_orchestrator.cli import main\nmain()\n",
        )
        for path in files:
            _add_source(archive, repository, path)
    payload = output.getvalue()
    if not 1 <= len(payload) <= 16 * 1024 * 1024:
        raise ValueError
    return payload


def _add_source(archive, repository, path):
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & 0x400
        or path.is_symlink()
    ):
        raise ValueError
    payload = _held_bytes(path, 256 * 1024)
    if len(payload) != metadata.st_size or len(payload) > 256 * 1024:
        raise ValueError
    _zip_entry(archive, path.relative_to(repository).as_posix(), payload)


def _held_bytes(path, maximum):
    from backend.cutover_managed_activation.windows_file_handles import (
        WindowsReadHandleApi,
    )

    api = WindowsReadHandleApi()
    handle = api.open_existing(path, deny_write=True)
    try:
        observed = api.observe(handle)
        payload = api.read_bounded(handle, limit=maximum)
        if not payload:
            raise ValueError
        api.require_stable(handle, observed, path)
        return payload
    finally:
        api.close(handle)


def _zip_entry(archive, name, payload):
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100600 << 16
    archive.writestr(info, payload)
