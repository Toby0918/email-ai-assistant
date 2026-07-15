"""Bounded descriptor I/O with fail-closed path identity checks."""

from __future__ import annotations

import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import PrivateEvaluationError


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
) -> bytes:
    descriptor = -1
    try:
        target = validate(original)
        parent_before = _identity(target.parent, directory=True)
        target_before = _identity(target, regular=True)
        hook("read_before_open", target)
        descriptor = os.open(target, _read_flags())
        opened = _from_stat(os.fstat(descriptor), regular=True)
        if opened != target_before:
            _unavailable()
        if opened.size > maximum:
            raise PrivateEvaluationError("dataset_decrypt_invalid")
        payload = _read_limit(descriptor, maximum + 1)
        hook("read_after_open", target)
        if _from_stat(os.fstat(descriptor), regular=True) != opened:
            _unavailable()
        _revalidate(original, target, parent_before, opened, validate)
        if len(payload) > maximum:
            raise PrivateEvaluationError("dataset_decrypt_invalid")
        return payload
    except PrivateEvaluationError:
        raise
    except Exception:
        _unavailable()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def replace_bounded_checked(
    original: Path, payload: bytes, maximum: int,
    validate: Callable[[Path], Path], hook: Callable[[str, Path], None],
    *, require_absent: bool = False,
) -> None:
    stage: Path | None = None
    try:
        if type(payload) is not bytes or len(payload) > maximum:
            _unavailable()
        target = validate(original)
        parent_before = _identity(target.parent, directory=True)
        target_before = _optional_identity(target)
        if require_absent and target_before is not None:
            _unavailable()
        stage, stage_opened = _write_stage(target, payload)
        hook("write_before_replace", target)
        _revalidate(original, target, parent_before, target_before, validate)
        if _identity(stage, regular=True) != stage_opened:
            _unavailable()
        if require_absent:
            try:
                _publish_new(stage, target, stage_opened)
                return
            except BaseException:
                if _optional_identity(target) == stage_opened:
                    return
                raise
        os.replace(stage, target)
        stage = None
        hook("write_after_replace", target)
        _revalidate(original, target, parent_before, stage_opened, validate)
        _sync_directory(target.parent)
    except PrivateEvaluationError:
        raise
    except Exception:
        _unavailable()
    finally:
        if stage is not None:
            _unlink_stage_best_effort(stage)


def _publish_new(stage: Path, target: Path, expected: _Identity) -> None:
    try:
        os.link(stage, target, follow_symlinks=False)
    except BaseException:
        if _optional_identity(target) == expected:
            return
        raise


def _unlink_stage_best_effort(stage: Path) -> None:
    try:
        stage.unlink(missing_ok=True)
    except BaseException:
        pass


def _write_stage(target: Path, payload: bytes) -> tuple[Path, _Identity]:
    stage = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    descriptor = -1
    keep = False
    try:
        descriptor = os.open(stage, _write_flags(), 0o600)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        opened = _from_stat(os.fstat(descriptor), regular=True)
        if opened.size != len(payload):
            _unavailable()
        os.close(descriptor)
        descriptor = -1
        keep = True
        return stage, opened
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if not keep:
            try:
                stage.unlink(missing_ok=True)
            except OSError:
                pass


def _revalidate(original, target, parent_before, target_before, validate) -> None:
    if validate(original) != target:
        _unavailable()
    if not _same_node(_identity(target.parent, directory=True), parent_before):
        _unavailable()
    if _optional_identity(target) != target_before:
        _unavailable()


def _same_node(left: _Identity, right: _Identity) -> bool:
    return (
        left.device, left.inode, stat.S_IFMT(left.mode)
    ) == (
        right.device, right.inode, stat.S_IFMT(right.mode)
    )


def _identity(path: Path, *, regular: bool = False, directory: bool = False) -> _Identity:
    try:
        metadata = os.lstat(path)
    except OSError:
        _unavailable()
    return _from_stat(metadata, regular=regular, directory=directory)


def _optional_identity(path: Path) -> _Identity | None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError:
        _unavailable()
    return _from_stat(metadata, regular=True)


def _from_stat(metadata, *, regular=False, directory=False) -> _Identity:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & reparse:
        _unavailable()
    if regular and not stat.S_ISREG(metadata.st_mode):
        _unavailable()
    if directory and not stat.S_ISDIR(metadata.st_mode):
        _unavailable()
    return _Identity(
        metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size,
        metadata.st_mtime_ns,
    )


def _read_limit(descriptor: int, limit: int) -> bytes:
    chunks: list[bytes] = []
    remaining = limit
    while remaining:
        chunk = os.read(descriptor, min(65_536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    written = 0
    while written < len(view):
        count = os.write(descriptor, view[written:])
        if count <= 0:
            _unavailable()
        written += count


def _read_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _write_flags() -> int:
    return (
        os.O_WRONLY | os.O_CREAT | os.O_EXCL
        | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _unavailable() -> None:
    raise PrivateEvaluationError("dataset_unavailable")
