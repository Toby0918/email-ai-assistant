"""Held, no-reparse, exact Runtime subtree construction window."""

from __future__ import annotations

import hashlib
import os
from io import BytesIO
from pathlib import Path, PurePosixPath

from .canonical import canonical_json, fail
from .errors import ManagedActivationError
from .runtime_limits import (
    MAX_RUNTIME_ENTRIES,
    MAX_RUNTIME_FILE_BYTES,
    RuntimeTreeBudget,
    hash_path_bounded,
)
from .windows_file_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    WindowsReadHandleApi,
)
from .windows_publication_io import (
    WindowsCreateOnlyApi,
    require_safe_component,
)
from .windows_streams import WindowsStreamApi

_ERROR = "runtime_tree_invalid"


class RuntimeTreeWindow:
    """Hold every approved Runtime entry and create additions by parent handle."""

    __slots__ = (
        "_target",
        "_read_api",
        "_create_api",
        "_stream_api",
        "_handles",
        "_directories",
        "_entries",
        "_budget",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("RuntimeTreeWindow requires open()")

    @classmethod
    def open(cls, target: Path):
        window = object.__new__(cls)
        window._target = target
        window._read_api = WindowsReadHandleApi()
        window._create_api = WindowsCreateOnlyApi()
        window._stream_api = WindowsStreamApi()
        window._handles = []
        window._directories = {}
        window._entries = {}
        window._budget = RuntimeTreeBudget()
        try:
            window._capture_directory(target, ())
            window.verify_exact()
            return window
        except Exception:
            window.close(active_error=True)
            fail(_ERROR)

    def _capture_directory(self, path: Path, parts: tuple[str, ...]) -> None:
        handle = self._open_held(path, directory=True)
        self._directories[parts] = handle
        if parts:
            self._budget.add_directory(parts)
            self._entries[_key(parts)] = _directory_entry(parts)
        children = _bounded_children(path)
        for child in children:
            require_safe_component(child.name)
            child_parts = (*parts, child.name)
            child_path = Path(child.path)
            if child.is_dir(follow_symlinks=False):
                self._capture_directory(child_path, child_parts)
            elif child.is_file(follow_symlinks=False):
                self._capture_file(child_path, child_parts)
            else:
                fail(_ERROR)

    def _capture_file(self, path: Path, parts: tuple[str, ...]) -> None:
        handle = self._open_held(path, directory=False)
        expected = self._read_api.observe(handle)
        try:
            size = path.stat(follow_symlinks=False).st_size
        except OSError:
            fail(_ERROR)
        self._budget.add_file(parts, size)
        digest = hash_path_bounded(path, size)
        self._read_api.require_stable(handle, expected, path)
        self._entries[_key(parts)] = _file_entry(parts, size, digest)

    def _open_held(self, path: Path, *, directory: bool) -> int:
        handle = self._read_api.open_existing(path, deny_write=True)
        self._handles.append(handle)
        observed = self._read_api.observe(handle)
        if not _allowed_observation(observed, directory=directory):
            fail(_ERROR)
        self._stream_api.require_default_only(path)
        return handle

    def ensure_directory(self, parts: tuple[str, ...]) -> int:
        current: tuple[str, ...] = ()
        for part in parts:
            require_safe_component(part)
            next_parts = (*current, part)
            if next_parts not in self._directories:
                self._create_directory(current, next_parts)
            current = next_parts
        return self._directories[current]

    def _create_directory(
        self, parent_parts: tuple[str, ...], parts: tuple[str, ...]
    ) -> None:
        parent = self._directories[parent_parts]
        self._budget.add_directory(parts)
        handle = self._create_api.create_directory(parent, parts[-1])
        self._handles.append(handle)
        observed = self._read_api.observe(handle)
        if not _allowed_observation(observed, directory=True):
            fail(_ERROR)
        self._directories[parts] = handle
        self._entries[_key(parts)] = _directory_entry(parts)

    def create_file(self, parts: tuple[str, ...], payload: bytes) -> None:
        self.create_streamed_file(parts, BytesIO(payload), len(payload))

    def create_streamed_file(
        self, parts: tuple[str, ...], source, expected_size: int
    ) -> None:
        try:
            self._create_streamed_file(parts, source, expected_size)
        except ManagedActivationError:
            fail(_ERROR)
        except Exception:
            fail(_ERROR)

    def _create_streamed_file(self, parts, source, expected_size) -> None:
        if not parts or _key(parts) in self._entries:
            fail(_ERROR)
        parent = self.ensure_directory(parts[:-1])
        require_safe_component(parts[-1])
        self._budget.add_file(parts, expected_size)
        handle = self._create_api.create_file(parent, parts[-1])
        self._handles.append(handle)
        digest = hashlib.sha256()
        remaining = expected_size
        while remaining:
            block = source.read(min(64 * 1024, remaining))
            if (
                type(block) is not bytes
                or not block
                or len(block) > remaining
            ):
                fail(_ERROR)
            self._create_api.write_all(handle, block)
            digest.update(block)
            remaining -= len(block)
        if source.read(1) != b"":
            fail(_ERROR)
        self._create_api.flush(handle)
        observed_size, observed_hash = self._create_api.hash_all(
            handle, limit=MAX_RUNTIME_FILE_BYTES
        )
        if (
            observed_size != expected_size
            or observed_hash != digest.hexdigest()
        ):
            fail(_ERROR)
        observed = self._read_api.observe(handle)
        if not _allowed_observation(observed, directory=False):
            fail(_ERROR)
        path = self._target.joinpath(*parts)
        self._stream_api.require_default_only(path)
        self._entries[_key(parts)] = _file_entry(
            parts, expected_size, observed_hash
        )
        self._downgrade_created_file(
            handle, path, expected_size, observed_hash
        )

    def _downgrade_created_file(
        self, handle, path, expected_size, expected_hash
    ) -> None:
        self._read_api.close(handle)
        if not self._handles or self._handles[-1] != handle:
            fail(_ERROR)
        self._handles.pop()
        read_handle = self._open_held(path, directory=False)
        size, digest = self._read_api.hash_bounded(
            read_handle, limit=MAX_RUNTIME_FILE_BYTES
        )
        if size != expected_size or digest != expected_hash:
            fail(_ERROR)

    def verify_exact(self) -> str:
        self._stream_api.require_default_only(self._target)
        actual = _scan_tree(self._target, self._stream_api)
        expected = tuple(self._entries[key] for key in sorted(self._entries))
        if actual != expected:
            fail(_ERROR)
        return hashlib.sha256(
            canonical_json(list(expected), code=_ERROR)
        ).hexdigest()

    def close(self, *, active_error: bool) -> None:
        failed = False
        while self._handles:
            try:
                self._read_api.close(self._handles.pop())
            except Exception:
                failed = True
        if failed and not active_error:
            fail(_ERROR)


def _scan_tree(target: Path, stream_api: WindowsStreamApi):
    entries = []
    budget = RuntimeTreeBudget()
    stack = [(target, ())]
    stream_api.require_default_only(target)
    while stack:
        directory, parts = stack.pop()
        children = _bounded_children(directory, reverse=True)
        for child in children:
            child_parts = (*parts, child.name)
            require_safe_component(child.name)
            path = Path(child.path)
            stream_api.require_default_only(path)
            metadata = child.stat(follow_symlinks=False)
            if getattr(metadata, "st_file_attributes", 0) & 0x400:
                fail(_ERROR)
            if child.is_dir(follow_symlinks=False):
                budget.add_directory(child_parts)
                entries.append(_directory_entry(child_parts))
                stack.append((path, child_parts))
            elif child.is_file(follow_symlinks=False):
                budget.add_file(child_parts, metadata.st_size)
                entries.append(
                    _file_entry(
                        child_parts,
                        metadata.st_size,
                        hash_path_bounded(path, metadata.st_size),
                    )
                )
            else:
                fail(_ERROR)
    return tuple(sorted(entries, key=lambda item: item["name"]))


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
        children,
        key=lambda item: item.name.casefold(),
        reverse=reverse,
    )


def _allowed_observation(observed, *, directory: bool) -> bool:
    is_directory = bool(observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY)
    return (
        is_directory == directory
        and not observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        and observed.filesystem_name == "NTFS"
        and observed.fixed_drive
    )


def _directory_entry(parts: tuple[str, ...]) -> dict[str, object]:
    return {"name": _key(parts), "kind": "directory"}


def _file_entry(
    parts: tuple[str, ...], size: int, digest: str
) -> dict[str, object]:
    return {
        "name": _key(parts),
        "kind": "file",
        "size": size,
        "sha256": digest,
    }


def _key(parts: tuple[str, ...]) -> str:
    return PurePosixPath(*parts).as_posix()
