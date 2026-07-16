"""Bounded descriptor reads with fail-closed path identity checks."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import PrivateKnowledgeError


@dataclass(frozen=True, slots=True)
class _Identity:
    device: int
    inode: int
    mode: int
    size: int
    modified_ns: int


def read_bounded_checked(
    original: Path,
    maximum: int,
    validate: Callable[[Path], Path],
    hook: Callable[[str, Path], None],
    *,
    error_code: str,
) -> bytes:
    """Read one stable regular file or raise only the supplied fixed code."""
    descriptor = -1
    try:
        if type(maximum) is not int or maximum <= 0:
            _unavailable(error_code)
        source = Path(original)
        target = validate(source)
        parent_before = _identity(target.parent, directory=True, error_code=error_code)
        target_before = _identity(target, regular=True, error_code=error_code)
        hook("read_before_open", target)
        descriptor = os.open(target, _read_flags())
        opened = _from_stat(os.fstat(descriptor), regular=True, error_code=error_code)
        if opened != target_before or not 1 <= opened.size <= maximum:
            _unavailable(error_code)
        payload = _read_limit(descriptor, maximum + 1, error_code)
        hook("read_after_open", target)
        if _from_stat(
            os.fstat(descriptor), regular=True, error_code=error_code
        ) != opened:
            _unavailable(error_code)
        _revalidate(
            source, target, parent_before, opened, validate, error_code
        )
        if len(payload) != opened.size or len(payload) > maximum:
            _unavailable(error_code)
        return payload
    except PrivateKnowledgeError as error:
        if error.code == error_code:
            raise
        _unavailable(error_code)
    except Exception:
        _unavailable(error_code)
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def validate_read_path(path: Path, *, error_code: str) -> Path:
    """Resolve an absolute non-reparse path for descriptor identity checks."""
    try:
        original = Path(path)
        if not original.is_absolute():
            _unavailable(error_code)
        _reject_reparse_components(original, error_code)
        resolved = original.resolve(strict=True)
        _reject_reparse_components(resolved, error_code)
        return resolved
    except PrivateKnowledgeError:
        raise
    except Exception:
        _unavailable(error_code)


def _revalidate(
    original: Path,
    target: Path,
    parent_before: _Identity,
    opened: _Identity,
    validate: Callable[[Path], Path],
    error_code: str,
) -> None:
    if validate(original) != target:
        _unavailable(error_code)
    parent_after = _identity(target.parent, directory=True, error_code=error_code)
    if not _same_node(parent_after, parent_before):
        _unavailable(error_code)
    if _identity(target, regular=True, error_code=error_code) != opened:
        _unavailable(error_code)


def _identity(
    path: Path,
    *,
    regular: bool = False,
    directory: bool = False,
    error_code: str,
) -> _Identity:
    try:
        metadata = os.lstat(path)
    except OSError:
        _unavailable(error_code)
    return _from_stat(
        metadata, regular=regular, directory=directory, error_code=error_code
    )


def _from_stat(
    metadata: object,
    *,
    regular: bool = False,
    directory: bool = False,
    error_code: str,
) -> _Identity:
    mode = getattr(metadata, "st_mode", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(mode) or attributes & reparse:
        _unavailable(error_code)
    if regular and not stat.S_ISREG(mode):
        _unavailable(error_code)
    if directory and not stat.S_ISDIR(mode):
        _unavailable(error_code)
    return _Identity(
        getattr(metadata, "st_dev", 0),
        getattr(metadata, "st_ino", 0),
        mode,
        getattr(metadata, "st_size", -1),
        getattr(metadata, "st_mtime_ns", -1),
    )


def _reject_reparse_components(path: Path, error_code: str) -> None:
    for component in reversed((path, *path.parents)):
        try:
            metadata = os.lstat(component)
        except OSError:
            _unavailable(error_code)
        _from_stat(metadata, error_code=error_code)


def _same_node(left: _Identity, right: _Identity) -> bool:
    return (
        left.device, left.inode, stat.S_IFMT(left.mode)
    ) == (
        right.device, right.inode, stat.S_IFMT(right.mode)
    )


def _read_limit(descriptor: int, limit: int, error_code: str) -> bytes:
    chunks: list[bytes] = []
    remaining = limit
    while remaining:
        try:
            chunk = os.read(descriptor, min(65_536, remaining))
        except OSError:
            _unavailable(error_code)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _unavailable(error_code: str) -> None:
    raise PrivateKnowledgeError(error_code)
