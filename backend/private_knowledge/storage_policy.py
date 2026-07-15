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
    path = _absolute_root(value)
    _reject_reparse_components(path)
    return path


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
        if not component.exists():
            continue
        try:
            metadata = component.lstat()
        except OSError:
            raise PrivateKnowledgeError("private_storage_path_invalid") from None
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if component.is_symlink() or getattr(metadata, "st_file_attributes", 0) & reparse:
            raise PrivateKnowledgeError("private_storage_path_invalid")


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents
