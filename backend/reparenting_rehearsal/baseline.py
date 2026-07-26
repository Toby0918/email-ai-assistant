"""Capture content-free topology plus approved source hashes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import stat

from .contract import SyntheticWorktree
from .errors import RehearsalError
from .git_runner import git_output
from .synthetic_project import (
    EXCLUDED_PATHS,
    REVIEWED_UNTRACKED,
    SyntheticProject,
)


@dataclass(frozen=True, slots=True, repr=False)
class ObjectIdentity:
    device: int
    inode: int


@dataclass(frozen=True, slots=True, repr=False)
class ApprovedFile:
    relative_path: str
    sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class ExcludedObject:
    relative_path: str
    identity: ObjectIdentity
    size_bytes: int
    modified_ns: int


@dataclass(frozen=True, slots=True, repr=False)
class LinkedWorktreeBaseline:
    worktree: SyntheticWorktree
    path: Path
    branch_ref: str
    head_oid: str
    common_identity: ObjectIdentity
    directory_identity: ObjectIdentity
    admin_name: str


@dataclass(frozen=True, slots=True, repr=False)
class RepositoryBaseline:
    review: object
    source_identity: ObjectIdentity
    common_identity: ObjectIdentity
    tracked_files: tuple[ApprovedFile, ...]
    reviewed_untracked: ApprovedFile
    index_sha256: str
    status_sha256: str
    linked_worktrees: tuple[LinkedWorktreeBaseline, ...]
    excluded_objects: tuple[ExcludedObject, ...]

    def linked(
        self,
        worktree: SyntheticWorktree,
    ) -> LinkedWorktreeBaseline:
        matches = tuple(
            item for item in self.linked_worktrees
            if item.worktree is worktree
        )
        if len(matches) != 1:
            raise RehearsalError()
        return matches[0]


def capture_repository_baseline(
    project: SyntheticProject,
    review: object,
) -> RepositoryBaseline:
    """Capture all state #36 must compare after reparenting."""

    common = _common_directory(project, project.source)
    tracked_paths = _tracked_paths(project, project.source)
    tracked_files = tuple(
        _approved_file(project.source, relative)
        for relative in tracked_paths
    )
    linked = tuple(
        _linked_baseline(project, review, item, path, common)
        for item, path in project.old_worktrees
    )
    return RepositoryBaseline(
        review=review,
        source_identity=_directory_identity(project.source),
        common_identity=_directory_identity(common),
        tracked_files=tracked_files,
        reviewed_untracked=_approved_file(
            project.source,
            REVIEWED_UNTRACKED,
        ),
        index_sha256=_git_state_hash(
            project,
            project.source,
            ("ls-files", "--stage", "-z"),
        ),
        status_sha256=_git_state_hash(
            project,
            project.source,
            ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        ),
        linked_worktrees=linked,
        excluded_objects=tuple(
            _excluded_object(project.source, relative)
            for relative in EXCLUDED_PATHS
        ),
    )


def current_index_hash(project: SyntheticProject, repository: Path) -> str:
    return _git_state_hash(
        project,
        repository,
        ("ls-files", "--stage", "-z"),
    )


def current_status_hash(project: SyntheticProject, repository: Path) -> str:
    return _git_state_hash(
        project,
        repository,
        ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
    )


def current_file_hash(repository: Path, relative: str) -> str:
    return _approved_file(repository, relative).sha256


def current_common_identity(
    project: SyntheticProject,
    repository: Path,
) -> ObjectIdentity:
    return _directory_identity(_common_directory(project, repository))


def current_branch(project: SyntheticProject, repository: Path) -> str:
    value = git_output(
        project.scope,
        repository,
        ("symbolic-ref", "HEAD"),
    ).strip()
    if not value.startswith("refs/heads/"):
        raise RehearsalError()
    return value


def current_head(project: SyntheticProject, repository: Path) -> str:
    value = git_output(
        project.scope,
        repository,
        ("rev-parse", "HEAD"),
    ).strip()
    if len(value) != 40:
        raise RehearsalError()
    return value


def current_excluded_object(
    legacy: Path,
    relative: str,
) -> ExcludedObject:
    return _excluded_object(legacy, relative)


def require_source_hashes(root: Path, baseline: RepositoryBaseline) -> None:
    for item in (*baseline.tracked_files, baseline.reviewed_untracked):
        if current_file_hash(root, item.relative_path) != item.sha256:
            raise RehearsalError()


def require_excluded_objects(
    root: Path,
    baseline: RepositoryBaseline,
) -> None:
    for expected in baseline.excluded_objects:
        if current_excluded_object(
            root,
            expected.relative_path,
        ) != expected:
            raise RehearsalError()


def directory_identity(path: Path) -> ObjectIdentity:
    return _directory_identity(path)


def _tracked_paths(
    project: SyntheticProject,
    repository: Path,
) -> tuple[str, ...]:
    output = git_output(
        project.scope,
        repository,
        ("ls-files", "-z"),
    )
    paths = tuple(sorted(item for item in output.split("\x00") if item))
    if not paths or len(paths) != len(set(paths)):
        raise RehearsalError()
    return paths


def _linked_baseline(
    project: SyntheticProject,
    review: object,
    worktree: SyntheticWorktree,
    path: Path,
    common: Path,
) -> LinkedWorktreeBaseline:
    worktrees = getattr(review, "worktrees", ())
    matches = tuple(item for item in worktrees if item.path == path)
    if len(matches) != 1:
        raise RehearsalError()
    git_file = path / ".git"
    admin = _linked_admin_path(git_file, common)
    return LinkedWorktreeBaseline(
        worktree=worktree,
        path=path,
        branch_ref=current_branch(project, path),
        head_oid=current_head(project, path),
        common_identity=current_common_identity(project, path),
        directory_identity=_directory_identity(path),
        admin_name=admin.name,
    )


def _linked_admin_path(git_file: Path, common: Path) -> Path:
    value = git_file.read_text(encoding="utf-8").strip()
    prefix = "gitdir: "
    if not value.startswith(prefix):
        raise RehearsalError()
    admin = Path(value[len(prefix):]).resolve(strict=True)
    root = (common / "worktrees").resolve(strict=True)
    if admin.parent != root or not admin.is_dir():
        raise RehearsalError()
    return admin


def _common_directory(
    project: SyntheticProject,
    repository: Path,
) -> Path:
    value = git_output(
        project.scope,
        repository,
        ("rev-parse", "--path-format=absolute", "--git-common-dir"),
    ).strip()
    common = Path(value).resolve(strict=True)
    if project.scope not in common.parents:
        raise RehearsalError()
    return common


def _approved_file(root: Path, relative: str) -> ApprovedFile:
    path = root / relative
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise RehearsalError()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ApprovedFile(relative, digest)


def _excluded_object(root: Path, relative: str) -> ExcludedObject:
    path = root / relative
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise RehearsalError()
    return ExcludedObject(
        relative_path=relative,
        identity=ObjectIdentity(metadata.st_dev, metadata.st_ino),
        size_bytes=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
    )


def _directory_identity(path: Path) -> ObjectIdentity:
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or path.is_symlink():
        raise RehearsalError()
    return ObjectIdentity(metadata.st_dev, metadata.st_ino)


def _git_state_hash(
    project: SyntheticProject,
    repository: Path,
    arguments: tuple[str, ...],
) -> str:
    output = git_output(project.scope, repository, arguments)
    return hashlib.sha256(output.encode("utf-8")).hexdigest()
