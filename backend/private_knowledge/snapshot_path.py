"""Fail-closed external path policy for read-only knowledge snapshots."""

from __future__ import annotations

import stat
import tempfile
from pathlib import Path

from .errors import PrivateKnowledgeError


def validate_snapshot_path(
    value: Path,
    *,
    forbidden_roots: tuple[Path, ...] = (),
) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.suffix != ".pksnap":
        raise PrivateKnowledgeError("snapshot_path_invalid")
    try:
        _reject_reparse_components(path)
        resolved = path.resolve(strict=False)
        roots = tuple(Path(root).resolve(strict=False) for root in forbidden_roots)
        temporary = Path(tempfile.gettempdir()).resolve(strict=False)
    except (OSError, RuntimeError):
        raise PrivateKnowledgeError("snapshot_path_invalid") from None
    if (any(resolved == root or root in resolved.parents for root in roots)
            or resolved == temporary or temporary in resolved.parents
            or any(part.casefold().startswith("onedrive") for part in resolved.parts)
            or _inside_raw_vault(resolved)
            or _inside_private_store(resolved)):
        raise PrivateKnowledgeError("snapshot_path_invalid")
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise PrivateKnowledgeError("snapshot_path_invalid")
    return resolved


def _inside_raw_vault(path: Path) -> bool:
    for parent in path.parents:
        if (_marker_exists(parent / "vault-index.sqlite3")
                or _marker_exists(parent / "keys" / "recovery-state.json")):
            return True
    return False


def _inside_private_store(path: Path) -> bool:
    markers = {"candidate-key.pkenv", "authority-keys.pkenv"}
    return any(
        any(_marker_exists(parent / marker) for marker in markers)
        for parent in path.parents
    )


def _reject_reparse_components(path: Path) -> None:
    for component in reversed((path, *path.parents)):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise PrivateKnowledgeError("snapshot_path_invalid") from None
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(metadata.st_mode) or attributes & reparse:
            raise PrivateKnowledgeError("snapshot_path_invalid")


def _marker_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise PrivateKnowledgeError("snapshot_path_invalid") from None
    return True
