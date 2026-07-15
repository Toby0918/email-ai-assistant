"""External path policy shared by private authority and staging stores."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .errors import PrivateKnowledgeError


def validate_stage_storage(
    candidate_root: Path,
    vault_root: Path,
    project_root: Path,
) -> None:
    candidate = _external_root(candidate_root)
    vault = _absolute_root(vault_root)
    project = _absolute_root(project_root)
    forbidden = [project, Path(tempfile.gettempdir()).resolve()]
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        forbidden.append(Path(one_drive).resolve())
    if (any(candidate == root or root in candidate.parents for root in forbidden)
            or _overlaps(candidate, vault)
            or any(part.casefold().startswith("onedrive") for part in candidate.parts)):
        raise PrivateKnowledgeError("private_storage_path_invalid")


def validate_private_storage(project_root: Path, *paths: Path) -> None:
    resolved = tuple(_external_root(path) for path in paths)
    project = _absolute_root(project_root)
    forbidden = [project, Path(tempfile.gettempdir()).resolve()]
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        forbidden.append(Path(one_drive).resolve())
    for path in resolved:
        if (any(path == root or root in path.parents for root in forbidden)
                or any(part.casefold().startswith("onedrive") for part in path.parts)):
            raise PrivateKnowledgeError("private_storage_path_invalid")
    for index, path in enumerate(resolved):
        if any(_overlaps(path, other) for other in resolved[index + 1:]):
            raise PrivateKnowledgeError("key_namespace_not_separate")


def _external_root(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise PrivateKnowledgeError("private_storage_path_invalid")
    try:
        _reject_reparse_components(path)
        if _inside_raw_vault(path):
            raise PrivateKnowledgeError("private_storage_path_invalid")
        resolved = path.resolve(strict=False)
        if _inside_raw_vault(resolved):
            raise PrivateKnowledgeError("private_storage_path_invalid")
        return resolved
    except (OSError, RuntimeError):
        raise PrivateKnowledgeError("private_storage_path_invalid") from None


def _absolute_root(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise PrivateKnowledgeError("private_storage_path_invalid")
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError):
        raise PrivateKnowledgeError("private_storage_path_invalid") from None


def _reject_reparse_components(path: Path) -> None:
    for component in reversed((path, *path.parents)):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise PrivateKnowledgeError("private_storage_path_invalid") from None
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & reparse):
            raise PrivateKnowledgeError("private_storage_path_invalid")


def _inside_raw_vault(path: Path) -> bool:
    for parent in (path, *path.parents):
        if (_marker_exists(parent / "vault-index.sqlite3")
                or _marker_exists(parent / "keys" / "recovery-state.json")):
            return True
    return False


def _marker_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise PrivateKnowledgeError("private_storage_path_invalid") from None
    return True


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents
