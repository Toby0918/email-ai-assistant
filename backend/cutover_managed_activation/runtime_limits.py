"""Fixed resource ceilings and streaming hash accounting for Runtime trees."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .canonical import fail

MAX_RUNTIME_ENTRIES = 50_000
MAX_RUNTIME_BYTES = 1024 * 1024 * 1024
MAX_RUNTIME_FILE_BYTES = 256 * 1024 * 1024
MAX_RUNTIME_PATH_BYTES = 4096
MAX_RUNTIME_DEPTH = 64
_ERROR = "runtime_tree_invalid"


class RuntimeTreeBudget:
    """Bound entries and bytes before a Runtime path is read or created."""

    __slots__ = ("_entries", "_bytes", "_max_entries", "_max_bytes")

    def __init__(
        self,
        *,
        max_entries: int = MAX_RUNTIME_ENTRIES,
        max_bytes: int = MAX_RUNTIME_BYTES,
    ) -> None:
        if (
            type(max_entries) is not int
            or type(max_bytes) is not int
            or max_entries <= 0
            or max_bytes <= 0
        ):
            fail(_ERROR)
        self._entries = 0
        self._bytes = 0
        self._max_entries = max_entries
        self._max_bytes = max_bytes

    def add_directory(self, parts: tuple[str, ...]) -> None:
        self._add(parts, 0)

    def add_file(self, parts: tuple[str, ...], size: int) -> None:
        if (
            type(size) is not int
            or size < 0
            or size > MAX_RUNTIME_FILE_BYTES
        ):
            fail(_ERROR)
        self._add(parts, size)

    def _add(self, parts: tuple[str, ...], size: int) -> None:
        if (
            not parts
            or len(parts) > MAX_RUNTIME_DEPTH
            or len("/".join(parts).encode("utf-8")) > MAX_RUNTIME_PATH_BYTES
            or self._entries + 1 > self._max_entries
            or self._bytes + size > self._max_bytes
        ):
            fail(_ERROR)
        self._entries += 1
        self._bytes += size


def hash_path_bounded(path: Path, expected_size: int) -> str:
    if (
        type(expected_size) is not int
        or expected_size < 0
        or expected_size > MAX_RUNTIME_FILE_BYTES
    ):
        fail(_ERROR)
    digest = hashlib.sha256()
    remaining = expected_size
    try:
        with path.open("rb") as input_file:
            while remaining:
                block = input_file.read(min(64 * 1024, remaining))
                if not block:
                    fail(_ERROR)
                digest.update(block)
                remaining -= len(block)
            if input_file.read(1):
                fail(_ERROR)
    except OSError:
        fail(_ERROR)
    return digest.hexdigest()
