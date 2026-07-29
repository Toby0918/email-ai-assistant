"""Exact approved CPython distribution review and held execution window."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .canonical import canonical_json, fail
from .runtime_limits import (
    MAX_RUNTIME_ENTRIES,
    MAX_RUNTIME_FILE_BYTES,
    RuntimeTreeBudget,
    hash_path_bounded,
)
from .runtime_startup_archive import build_startup_archive
from .windows_directory_monitor import WindowsDirectoryChangeGuard
from .windows_file_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    WindowsReadHandleApi,
)
from .windows_publication_io import require_safe_component
from .windows_streams import WindowsStreamApi

_ERROR = "runtime_python_source_invalid"
_SQLITE_BINARIES = ("DLLs/_sqlite3.pyd", "DLLs/sqlite3.dll")

@dataclass(frozen=True, slots=True, repr=False)
class SourceTreeObservation:
    fingerprint: str
    entry_count: int
    total_bytes: int
    executable_sha256: str

class HeldPythonSourceTree:
    """Hold every approved source entry against write/delete until success."""

    __slots__ = (
        "_root",
        "_executable",
        "_api",
        "_streams",
        "_guard",
        "_handles",
        "_expected",
        "_entries",
        "_files",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("HeldPythonSourceTree requires open()")

    @classmethod
    def open(cls, executable: Path, expected: SourceTreeObservation):
        tree = object.__new__(cls)
        tree._root = executable.parent
        tree._executable = executable
        tree._api = WindowsReadHandleApi()
        tree._streams = WindowsStreamApi()
        tree._guard = None
        tree._handles = []
        tree._expected = expected
        tree._entries = ()
        tree._files = []
        try:
            tree._guard = WindowsDirectoryChangeGuard.open(tree._root)
            tree._entries = tree._capture_tree()
            if tree._observation() != expected:
                fail(_ERROR)
            return tree
        except Exception:
            tree.close(active_error=True)
            fail(_ERROR)

    def require_stable(self) -> None:
        try:
            if _scan_source_tree(
                self._root, self._executable
            ) != self._expected:
                fail("runtime_source_changed")
            for handle, observed, path in self._handles:
                self._api.require_stable(handle, observed, path)
        except Exception:
            fail("runtime_source_changed")

    def publish_into(self, tree) -> None:
        directories = [
            tuple(PurePosixPath(item["name"]).parts)
            for item in self._entries
            if item["kind"] == "directory"
        ]
        for parts in sorted(directories, key=lambda value: (len(value), value)):
            tree.ensure_directory(parts)
        for parts, handle, size in self._files:
            self._api.reset(handle)
            tree.create_streamed_file(
                parts,
                _HeldHandleReader(self._api, handle, size),
                size,
            )

    def sqlite_binary_hashes(self) -> tuple[tuple[str, str], ...]:
        files = {
            item["name"]: item["sha256"]
            for item in self._entries if item["kind"] == "file"
        }
        try:
            return tuple((name, files[name]) for name in _SQLITE_BINARIES)
        except KeyError:
            fail(_ERROR)
    def startup_archive(self) -> bytes:
        return build_startup_archive(self._api, self._files)
    def close(self, *, active_error: bool) -> None:
        failed = False
        if self._guard is not None:
            try:
                if not active_error:
                    self._guard.seal_unchanged()
                self._guard.close(active_error=active_error)
            except Exception:
                failed = True
        while self._handles:
            handle, _observed, _path = self._handles.pop()
            try:
                self._api.close(handle)
            except Exception:
                failed = True
        if failed and not active_error:
            fail("runtime_source_changed")

    def _capture_tree(self) -> tuple[dict[str, object], ...]:
        entries = []
        budget = RuntimeTreeBudget()
        stack = [(self._root, ())]
        while stack:
            directory, parts = stack.pop()
            self._open_held(directory, directory=True)
            children = _bounded_children(directory, reverse=True)
            for child in children:
                child_parts = (*parts, child.name)
                entry, descend = self._capture_child(child, child_parts, budget)
                entries.append(entry)
                if descend:
                    stack.append((Path(child.path), child_parts))
        return tuple(sorted(entries, key=lambda item: item["name"]))

    def _capture_child(self, child, parts, budget):
        require_safe_component(child.name)
        _reject_source_startup_member(parts)
        path = Path(child.path)
        if child.is_dir(follow_symlinks=False):
            budget.add_directory(parts)
            return _directory_entry(parts), True
        if not child.is_file(follow_symlinks=False):
            fail(_ERROR)
        handle, _observed = self._open_held(path, directory=False)
        size, digest = self._api.hash_bounded(
            handle, limit=MAX_RUNTIME_FILE_BYTES
        )
        budget.add_file(parts, size)
        self._files.append((parts, handle, size))
        return _file_entry(parts, size, digest), False

    def _open_held(self, path: Path, *, directory: bool):
        handle = self._api.open_existing(path, deny_write=True)
        observed = self._api.observe(handle)
        if not _allowed_observation(observed, directory=directory):
            self._api.close(handle)
            fail(_ERROR)
        self._streams.require_default_only(path)
        self._handles.append((handle, observed, path))
        return handle, observed

    def _observation(self) -> SourceTreeObservation:
        return _observation(self._entries, self._executable.name)

def observe_source_tree(executable: Path) -> SourceTreeObservation:
    return _scan_source_tree(executable.parent, executable)

class _HeldHandleReader:
    __slots__ = ("_api", "_handle", "_remaining")

    def __init__(self, api, handle, size) -> None:
        self._api = api
        self._handle = handle
        self._remaining = size

    def read(self, length: int) -> bytes:
        if self._remaining == 0:
            return b""
        requested = min(length, self._remaining, 64 * 1024)
        block = self._api.read_block(self._handle, length=requested)
        self._remaining -= len(block)
        return block

def _scan_source_tree(root: Path, executable: Path) -> SourceTreeObservation:
    streams = WindowsStreamApi()
    entries = []
    budget = RuntimeTreeBudget()
    stack = [(root, ())]
    streams.require_default_only(root)
    while stack:
        directory, parts = stack.pop()
        children = _bounded_children(directory, reverse=True)
        for child in children:
            child_parts = (*parts, child.name)
            entry, descend = _scan_child(child, child_parts, budget, streams)
            entries.append(entry)
            if descend:
                stack.append((Path(child.path), child_parts))
    entries.sort(key=lambda item: item["name"])
    return _observation(tuple(entries), executable.name)

def _scan_child(child, parts, budget, streams):
    require_safe_component(child.name)
    _reject_source_startup_member(parts)
    path = Path(child.path)
    streams.require_default_only(path)
    metadata = child.stat(follow_symlinks=False)
    if getattr(metadata, "st_file_attributes", 0) & 0x400:
        fail(_ERROR)
    if child.is_dir(follow_symlinks=False):
        budget.add_directory(parts)
        return _directory_entry(parts), True
    if not child.is_file(follow_symlinks=False):
        fail(_ERROR)
    budget.add_file(parts, metadata.st_size)
    digest = hash_path_bounded(path, metadata.st_size)
    return _file_entry(parts, metadata.st_size, digest), False

def _observation(entries, executable_name) -> SourceTreeObservation:
    executable_key = PurePosixPath(executable_name).as_posix()
    matching = [
        item for item in entries
        if item["name"] == executable_key and item["kind"] == "file"
    ]
    if len(matching) != 1:
        fail(_ERROR)
    return SourceTreeObservation(
        fingerprint=hashlib.sha256(
            canonical_json(list(entries), code=_ERROR)
        ).hexdigest(),
        entry_count=len(entries),
        total_bytes=sum(
            item.get("size", 0) for item in entries
        ),
        executable_sha256=matching[0]["sha256"],
    )

def _bounded_children(path: Path, *, reverse: bool = False):
    children = []
    try:
        with os.scandir(path) as iterator:
            for child in iterator:
                children.append(child)
                if len(children) > MAX_RUNTIME_ENTRIES:
                    fail(_ERROR)
    except OSError:
        fail(_ERROR)
    return sorted(
        children, key=lambda item: item.name.casefold(), reverse=reverse
    )


def _allowed_observation(observed, *, directory: bool) -> bool:
    return (
        bool(observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY) == directory
        and not observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        and observed.filesystem_name == "NTFS"
        and observed.fixed_drive
    )


def _reject_source_startup_member(parts) -> None:
    leaf = parts[-1].casefold()
    if (
        leaf in {"sitecustomize.py", "usercustomize.py"}
        or len(parts) == 1
        and leaf in {"python._pth", "python312._pth", "pyvenv.cfg"}
    ):
        fail(_ERROR)


def _directory_entry(parts: tuple[str, ...]) -> dict[str, object]:
    return {"name": _key(parts), "kind": "directory"}


def _file_entry(parts, size, digest) -> dict[str, object]:
    return {
        "name": _key(parts),
        "kind": "file",
        "size": size,
        "sha256": digest,
    }


def _key(parts: tuple[str, ...]) -> str:
    return PurePosixPath(*parts).as_posix()
