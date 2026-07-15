"""Fail-closed external path and private-store separation policy."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .errors import PrivateEvaluationError


_OTHER_STORE_SUFFIXES = frozenset({
    ".pkauth", ".pkcand", ".pkimpt", ".pksnap", ".pkkey", ".pkstage",
    ".pkevalstage",
})
_OTHER_STORE_MARKERS = frozenset({
    "authority-keys.pkenv", "candidate-key.pkenv", "snapshot-key.pkenv",
    "candidate-store.pkcand", "candidate-import.pkimpt",
})
_MAX_DESCENDANT_ENTRIES = 4_096
_MAX_DESCENDANT_DEPTH = 16


def _validate_external_dataset_path(value: Path) -> Path:
    return _validate_external_private_path(value, ".pkeval")


def _validate_external_private_path(value: Path, suffix: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.suffix != suffix:
        _unavailable()
    try:
        _reject_reparse(path)
        resolved = path.resolve(strict=False)
        _reject_reparse(resolved)
    except (OSError, RuntimeError):
        _unavailable()
    project = Path(__file__).resolve().parents[2]
    temporary = Path(tempfile.gettempdir()).resolve()
    forbidden = (project, temporary)
    if (
        any(resolved == root or root in resolved.parents for root in forbidden)
        or any(part.casefold().startswith("onedrive") for part in (*path.parts, *resolved.parts))
        or (resolved.exists() and not resolved.is_file())
        or _inside_raw_vault(resolved)
        or _overlaps_other_store(resolved)
        or (suffix == ".pkevalstage" and _overlaps_evaluation_dataset(resolved))
    ):
        _unavailable()
    return resolved


def _reject_reparse(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            _unavailable()
        if _is_reparse(metadata):
            _unavailable()


def _inside_raw_vault(path: Path) -> bool:
    parents = (path.parent, *path.parents)
    try:
        if any(
            _regular_marker(parent / "vault-index.sqlite3")
            or _regular_marker(parent / "keys" / "recovery-state.json")
            for parent in parents
        ):
            return True
        return _descendant_has_marker(path.parent, _is_raw_marker)
    except OSError:
        _unavailable()


def _overlaps_other_store(path: Path) -> bool:
    try:
        for parent in (path.parent, *path.parents):
            for entry in _entries(parent):
                if entry != path and _is_private_marker(entry):
                    return True
        return _descendant_has_marker(path.parent, _is_private_marker)
    except OSError:
        _unavailable()


def _overlaps_evaluation_dataset(path: Path) -> bool:
    try:
        for parent in (path.parent, *path.parents):
            for entry in _entries(parent):
                if entry != path and _is_evaluation_dataset(entry):
                    return True
        return _descendant_has_marker(path.parent, _is_evaluation_dataset)
    except OSError:
        _unavailable()


def _descendant_has_marker(root: Path, predicate) -> bool:
    stack: list[tuple[Path, int]] = [(root, 0)]
    seen = 0
    while stack:
        directory, depth = stack.pop()
        if depth > _MAX_DESCENDANT_DEPTH:
            _unavailable()
        with os.scandir(directory) as entries:
            for entry in entries:
                seen += 1
                if seen > _MAX_DESCENDANT_ENTRIES:
                    _unavailable()
                metadata = entry.stat(follow_symlinks=False)
                if entry.is_symlink() or _is_reparse(metadata):
                    _unavailable()
                candidate = Path(entry.path)
                if predicate(candidate):
                    return True
                if stat.S_ISDIR(metadata.st_mode):
                    stack.append((candidate, depth + 1))
    return False


def _entries(parent: Path) -> tuple[Path, ...]:
    try:
        return tuple(parent.iterdir()) if parent.exists() else ()
    except OSError:
        _unavailable()


def _regular_marker(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    if _is_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
        _unavailable()
    return True


def _is_raw_marker(path: Path) -> bool:
    return path.name.casefold() == "vault-index.sqlite3" or (
        path.name.casefold() == "recovery-state.json"
        and path.parent.name.casefold() == "keys"
    )


def _is_private_marker(path: Path) -> bool:
    return (
        path.suffix.casefold() in _OTHER_STORE_SUFFIXES
        or path.name.casefold() in _OTHER_STORE_MARKERS
    )


def _is_evaluation_dataset(path: Path) -> bool:
    if path.suffix.casefold() != ".pkeval":
        return False
    metadata = path.lstat()
    if _is_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
        _unavailable()
    return True


def _is_reparse(metadata: os.stat_result) -> bool:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & reparse
    )


def _unavailable() -> None:
    raise PrivateEvaluationError("dataset_unavailable")
