"""Complete fixed repository-content manifest review for Issue #75."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from backend.cutover_repository_transaction.windows_identity import (
    directory_identity,
    file_identity,
)
from backend.r2_main_publication.windows_dacl import capture_tree

from .canonical import fingerprint
from .contracts import RepositoryContentManifestV1, build_manifest
from .git_bridge import ignored_files, tracked_files, untracked_files

_FORBIDDEN_APPROVED_PREFIXES = frozenset(
    {"private", "runtime", "database", "logs", "cache"}
)
_WORKTREE_ROOT = ".synthetic-worktrees"


@dataclass(frozen=True, slots=True, repr=False)
class ManifestMove:
    relative: str = field(repr=False)
    category: str
    directory: bool
    identity_fingerprint: str = field(repr=False)
    selection_fingerprint: str = field(repr=False)
    complete_subtree: bool
    acl_compatible: bool

    def contract_mapping(self) -> dict[str, object]:
        return {
            "relative_fingerprint": _relative_fingerprint(self.relative),
            "category": self.category,
            "directory": self.directory,
            "identity_fingerprint": self.identity_fingerprint,
            "selection_fingerprint": self.selection_fingerprint,
            "complete_subtree": self.complete_subtree,
            "acl_compatible": self.acl_compatible,
        }


@dataclass(frozen=True, slots=True, repr=False)
class ResidueItem:
    relative: str = field(repr=False)
    identity_fingerprint: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class BoundRepositoryManifest:
    contract: RepositoryContentManifestV1
    source: Path = field(repr=False)
    moves: tuple[ManifestMove, ...] = field(repr=False)
    skeletons: tuple[str, ...] = field(repr=False)
    residue: tuple[ResidueItem, ...] = field(repr=False)


def review_manifest(scope, approved_untracked: tuple[str, ...]):
    source = Path(scope.review.scenario.source)
    approved = _approved_paths(approved_untracked)
    tracked = set(tracked_files(scope.review.git_runner, source))
    untracked = set(untracked_files(scope.review.git_runner, source))
    ignored = {
        item for item in ignored_files(scope.review.git_runner, source)
        if not _under_worktree_root(item)
    }
    if untracked != approved or tracked & approved or ignored & approved:
        raise ValueError("repository_manifest_review_invalid")
    _require_safe_paths(source, tracked | approved | ignored)
    capture_tree(source)
    moves, skeletons = _build_moves(source, tracked, approved, ignored)
    manifest = build_manifest(
        items=moves,
        skeleton_count=len(skeletons),
        residue_count=len(ignored),
    )
    return BoundRepositoryManifest(
        contract=manifest,
        source=source,
        moves=moves,
        skeletons=skeletons,
        residue=tuple(
            ResidueItem(relative, file_identity(source / relative))
            for relative in sorted(ignored, key=str.casefold)
        ),
    )


def _build_moves(source, tracked, approved, ignored):
    selected = tracked | approved
    whole = _whole_directories(source, selected, ignored)
    skeletons = _skeletons(selected, whole)
    values = [_move(source, ".git", "git", True, True)]
    values.extend(
        _move(source, relative, "tracked", True, True)
        for relative in whole
    )
    for relative in sorted(selected, key=str.casefold):
        if any(_is_beneath(relative, directory) for directory in whole):
            continue
        category = "approved_untracked" if relative in approved else "tracked"
        values.append(_move(source, relative, category, False, False))
    return tuple(values), skeletons


def _move(source, relative, category, directory, complete):
    path = source / Path(relative)
    identity = directory_identity(path) if directory else file_identity(path)
    body = {
        "relative": _relative_fingerprint(relative),
        "category": category,
        "directory": directory,
        "identity": identity,
        "complete_subtree": complete,
        "acl_compatible": True,
    }
    return ManifestMove(
        relative=relative,
        category=category,
        directory=directory,
        identity_fingerprint=identity,
        selection_fingerprint=fingerprint("repository-manifest-selection-v1", body),
        complete_subtree=complete,
        acl_compatible=True,
    )


def _whole_directories(source, selected, ignored) -> tuple[str, ...]:
    candidates = sorted(
        {
            PurePosixPath(item).parts[0]
            for item in selected
            if len(PurePosixPath(item).parts) > 1
        },
        key=str.casefold,
    )
    values = []
    for directory in candidates:
        leaves = _leaf_files(source / directory, source)
        if leaves and leaves <= selected and not any(
            _is_beneath(item, directory) for item in ignored
        ):
            values.append(directory)
    return tuple(values)


def _skeletons(selected, whole) -> tuple[str, ...]:
    values = set()
    for relative in selected:
        if any(_is_beneath(relative, directory) for directory in whole):
            continue
        parent = PurePosixPath(relative).parent
        while str(parent) != ".":
            values.add(parent.as_posix())
            parent = parent.parent
    return tuple(sorted(values, key=lambda item: (item.count("/"), item.casefold())))


def _leaf_files(path: Path, source: Path) -> set[str]:
    result = set()
    for root, directories, files in os.walk(path, followlinks=False):
        directories.sort(key=str.casefold)
        for name in sorted(files, key=str.casefold):
            result.add((Path(root) / name).relative_to(source).as_posix())
    return result


def _approved_paths(values: object) -> set[str]:
    if type(values) is not tuple or len(values) > 100:
        raise ValueError("repository_manifest_review_invalid")
    result = set()
    for value in values:
        _validate_relative(value)
        first = PurePosixPath(value).parts[0].casefold()
        if first in _FORBIDDEN_APPROVED_PREFIXES or value.casefold() == ".git":
            raise ValueError("repository_manifest_review_invalid")
        result.add(value)
    if len(result) != len(values):
        raise ValueError("repository_manifest_review_invalid")
    return result


def _require_safe_paths(source: Path, values: set[str]) -> None:
    for relative in values:
        _validate_relative(relative)
        path = source / Path(relative)
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ValueError("repository_manifest_review_invalid") from None
        if source not in resolved.parents:
            raise ValueError("repository_manifest_review_invalid")


def _validate_relative(value: object) -> None:
    if type(value) is not str or not value or "\\" in value:
        raise ValueError("repository_manifest_review_invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("repository_manifest_review_invalid")


def _is_beneath(relative: str, directory: str) -> bool:
    parts = PurePosixPath(relative).parts
    return len(parts) > 1 and parts[0].casefold() == directory.casefold()


def _under_worktree_root(relative: str) -> bool:
    return PurePosixPath(relative).parts[0].casefold() == _WORKTREE_ROOT.casefold()


def _relative_fingerprint(relative: str) -> str:
    return hashlib.sha256(relative.casefold().encode("utf-8")).hexdigest()
