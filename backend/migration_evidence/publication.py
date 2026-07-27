"""Atomic no-clobber publication for one complete package file."""

from __future__ import annotations

import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path

from .errors import MigrationEvidenceError
from .path_checks import require_non_reparse_parent


_MAX_PACKAGE_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class _Identity:
    device: int
    inode: int
    mode: int
    size: int
    modified_ns: int
    links: int


def publish_new_package(target: Path, payload: bytes) -> _Identity:
    """Publish bytes exactly once; helper return is the commit point."""

    stage: Path | None = None
    descriptor = -1
    try:
        if type(payload) is not bytes or not payload or len(payload) > _MAX_PACKAGE_BYTES:
            _fail()
        normalized = require_non_reparse_parent(target)
        if normalized != target.absolute():
            _fail()
        target = normalized
        parent_before = _directory_identity(target.parent)
        if _optional_file_identity(target) is not None:
            _fail()
        stage, stage_identity, descriptor = _write_stage(target, payload)
        _revalidate_target(target, parent_before)
        if (
            _file_identity(stage) != stage_identity
            or _descriptor_identity(descriptor) != stage_identity
        ):
            _fail()
        _publish_link(
            stage,
            target,
            descriptor,
            stage_identity,
            parent_before,
        )
    except MigrationEvidenceError:
        raise
    except BaseException:
        _fail()
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException:
                pass
        if stage is not None:
            _unlink_stage_best_effort(stage)
    return stage_identity


def _write_stage(
    target: Path,
    payload: bytes,
) -> tuple[Path, _Identity, int]:
    stage = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    descriptor = -1
    keep = False
    try:
        descriptor = os.open(stage, _write_flags(), 0o600)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        identity = _from_stat(os.fstat(descriptor), regular=True)
        if identity.size != len(payload) or identity.links != 1:
            _fail()
        keep = True
        return stage, identity, descriptor
    finally:
        if descriptor >= 0 and not keep:
            try:
                os.close(descriptor)
            except BaseException:
                pass
        if not keep:
            _unlink_stage_best_effort(stage)


def _publish_link(
    stage: Path,
    target: Path,
    descriptor: int,
    expected: _Identity,
    parent_before: _Identity,
) -> None:
    try:
        _link_open_stage(stage, target, descriptor, parent_before)
    except BaseException:
        if _publication_matches(
            stage,
            target,
            descriptor,
            expected,
            parent_before,
        ):
            return
        raise
    if not _publication_matches(
        stage,
        target,
        descriptor,
        expected,
        parent_before,
    ):
        _fail()


def _link_open_stage(
    stage: Path,
    target: Path,
    descriptor: int,
    parent_before: _Identity,
) -> None:
    if os.name == "nt":
        os.link(stage, target, follow_symlinks=False)
        return
    parent_descriptor = -1
    try:
        parent_descriptor = os.open(
            target.parent,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        if not _same_node(
            _from_stat(os.fstat(parent_descriptor), directory=True),
            parent_before,
        ):
            _fail()
        source = f"/proc/self/fd/{descriptor}"
        os.link(
            source,
            target.name,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=True,
        )
    finally:
        if parent_descriptor >= 0:
            os.close(parent_descriptor)


def _publication_matches(
    stage: Path,
    target: Path,
    descriptor: int,
    expected: _Identity,
    parent_before: _Identity,
) -> bool:
    try:
        if not _same_node(_directory_identity(target.parent), parent_before):
            return False
        opened = _descriptor_identity(descriptor)
        staged = _file_identity(stage)
        published = _file_identity(target)
    except MigrationEvidenceError:
        return False
    return (
        opened == staged == published
        and opened.links == 2
        and _same_content_identity(opened, expected)
    )


def _revalidate_target(target: Path, parent_before: _Identity) -> None:
    if not _same_node(_directory_identity(target.parent), parent_before):
        _fail()
    if _optional_file_identity(target) is not None:
        _fail()


def _same_node(left: _Identity, right: _Identity) -> bool:
    return (
        left.device,
        left.inode,
        stat.S_IFMT(left.mode),
    ) == (
        right.device,
        right.inode,
        stat.S_IFMT(right.mode),
    )


def _same_content_identity(left: _Identity, right: _Identity) -> bool:
    return (
        left.device,
        left.inode,
        left.mode,
        left.size,
        left.modified_ns,
    ) == (
        right.device,
        right.inode,
        right.mode,
        right.size,
        right.modified_ns,
    )


def _directory_identity(path: Path) -> _Identity:
    try:
        return _from_stat(os.lstat(path), directory=True)
    except OSError:
        _fail()


def _file_identity(path: Path) -> _Identity:
    try:
        return _from_stat(os.lstat(path), regular=True)
    except OSError:
        _fail()


def _descriptor_identity(descriptor: int) -> _Identity:
    try:
        return _from_stat(os.fstat(descriptor), regular=True)
    except OSError:
        _fail()


def _optional_file_identity(path: Path) -> _Identity | None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError:
        _fail()
    return _from_stat(metadata, regular=True)


def _from_stat(metadata, *, regular=False, directory=False) -> _Identity:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & reparse:
        _fail()
    if regular and not stat.S_ISREG(metadata.st_mode):
        _fail()
    if directory and not stat.S_ISDIR(metadata.st_mode):
        _fail()
    return _Identity(
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_nlink,
    )


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    written = 0
    while written < len(view):
        count = os.write(descriptor, view[written:])
        if count <= 0:
            _fail()
        written += count


def _write_flags() -> int:
    return (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _unlink_stage_best_effort(stage: Path) -> None:
    try:
        stage.unlink(missing_ok=True)
    except BaseException:
        pass


def _fail() -> None:
    raise MigrationEvidenceError("migration_evidence_create_failed")
