"""Read one bounded governed-sales policy file without exposing its contents."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from backend.project_layout import ProtectedLocationPolicy

from .sales_message_policy import parse_sales_corpus_policy

_MAX_POLICY_BYTES = 64 * 1024
_ERROR_CODE = "sales_policy_invalid"
_Policy = TypeVar("_Policy")


@dataclass(frozen=True, slots=True)
class _Identity:
    device: int
    inode: int
    mode: int
    size: int
    modified_ns: int


class SalesPolicyFileError(ValueError):
    """One fixed, content-free failure for every policy-file rejection."""

    def __init__(self) -> None:
        self.code = _ERROR_CODE
        super().__init__(self.code)

    def __repr__(self) -> str:
        return "SalesPolicyFileError(code='sales_policy_invalid')"


def read_sales_policy(
    path: Path,
    *,
    project_root: Path,
    parser: Callable[[object], _Policy] = parse_sales_corpus_policy,
) -> _Policy:
    """Read JSON from one absolute path and return the validated policy value."""
    try:
        source = Path(path)
        validator = _location_validator(Path(project_root))
        payload = _read_bounded_checked(source, validator)
        return parser(_decode_json(payload))
    except Exception:
        raise SalesPolicyFileError() from None


def _system_temp_root() -> Path:
    return Path(tempfile.gettempdir())


def _location_validator(project_root: Path) -> Callable[[Path], Path]:
    if not project_root.is_absolute():
        raise ValueError
    protected = ProtectedLocationPolicy.for_repository(project_root)
    temporary_source = _system_temp_root()
    temporary = temporary_source.resolve(strict=False)

    def validate(source: Path) -> Path:
        target = _validate_read_path(source)
        if (
            source != target
            or protected.contains(
                original_path=source,
                resolved_path=target,
            )
            or _inside(source, temporary_source)
            or _inside(target, temporary)
            or _has_onedrive_component(source)
            or _has_onedrive_component(target)
        ):
            raise ValueError
        return target

    return validate


def _read_bounded_checked(
    source: Path,
    validate: Callable[[Path], Path],
) -> bytes:
    descriptor = -1
    try:
        target = validate(source)
        parent_before = _identity(target.parent, directory=True)
        target_before = _identity(target, regular=True)
        _test_race_hook("read_before_open", target)
        descriptor = os.open(target, _read_flags())
        opened = _from_stat(os.fstat(descriptor), regular=True)
        if opened != target_before or not 1 <= opened.size <= _MAX_POLICY_BYTES:
            _invalid()
        payload = _read_limit(descriptor, _MAX_POLICY_BYTES + 1)
        _test_race_hook("read_after_open", target)
        if _from_stat(os.fstat(descriptor), regular=True) != opened:
            _invalid()
        _revalidate(source, target, parent_before, opened, validate)
        if len(payload) != opened.size or len(payload) > _MAX_POLICY_BYTES:
            _invalid()
        return payload
    except SalesPolicyFileError:
        raise
    except Exception:
        _invalid()
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _validate_read_path(source: Path) -> Path:
    try:
        if not source.is_absolute():
            _invalid()
        _reject_reparse_components(source)
        target = source.resolve(strict=True)
        _reject_reparse_components(target)
        return target
    except SalesPolicyFileError:
        raise
    except Exception:
        _invalid()


def _revalidate(
    source: Path,
    target: Path,
    parent_before: _Identity,
    opened: _Identity,
    validate: Callable[[Path], Path],
) -> None:
    if validate(source) != target:
        _invalid()
    parent_after = _identity(target.parent, directory=True)
    if not _same_node(parent_after, parent_before):
        _invalid()
    if _identity(target, regular=True) != opened:
        _invalid()


def _identity(
    path: Path,
    *,
    regular: bool = False,
    directory: bool = False,
) -> _Identity:
    try:
        return _from_stat(os.lstat(path), regular=regular, directory=directory)
    except SalesPolicyFileError:
        raise
    except Exception:
        _invalid()


def _from_stat(
    metadata: object,
    *,
    regular: bool = False,
    directory: bool = False,
) -> _Identity:
    mode = getattr(metadata, "st_mode", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(mode) or attributes & reparse:
        _invalid()
    if regular and not stat.S_ISREG(mode):
        _invalid()
    if directory and not stat.S_ISDIR(mode):
        _invalid()
    return _Identity(
        getattr(metadata, "st_dev", 0),
        getattr(metadata, "st_ino", 0),
        mode,
        getattr(metadata, "st_size", -1),
        getattr(metadata, "st_mtime_ns", -1),
    )


def _reject_reparse_components(path: Path) -> None:
    for component in reversed((path, *path.parents)):
        _from_stat(os.lstat(component))


def _same_node(left: _Identity, right: _Identity) -> bool:
    return (left.device, left.inode, stat.S_IFMT(left.mode)) == (
        right.device,
        right.inode,
        stat.S_IFMT(right.mode),
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


def _read_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _has_onedrive_component(path: Path) -> bool:
    return any(part.casefold().startswith("onedrive") for part in path.parts)


def _decode_json(payload: bytes) -> object:
    return json.loads(
        payload.decode("utf-8", errors="strict"),
        object_pairs_hook=_object_without_duplicates,
        parse_constant=_reject_json_constant,
    )


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> object:
    raise ValueError


def _invalid() -> None:
    raise SalesPolicyFileError()


def _test_race_hook(_stage: str, _target: Path) -> None:
    """No-op seam used to verify descriptor race defenses."""
    return None


__all__ = ["SalesPolicyFileError", "read_sales_policy"]
