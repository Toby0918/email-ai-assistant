"""Checked no-clobber publications for the synthetic topology."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat

from .baseline import RepositoryBaseline, directory_identity
from .errors import RehearsalError
from .synthetic_project import (
    SyntheticProject,
    require_bound_synthetic_scope,
)


@dataclass(frozen=True, slots=True, repr=False)
class PublishedRepository:
    container: Path
    legacy: Path
    main: Path


def publish_legacy_source(project: SyntheticProject) -> None:
    checked_rename(project, project.source, project.legacy)


def publish_container(project: SyntheticProject) -> None:
    checked_rename(
        project,
        project.staging_container,
        project.source,
    )


def publish_main_repository(
    project: SyntheticProject,
    baseline: RepositoryBaseline,
) -> PublishedRepository:
    main = project.source / "main"
    legacy = project.legacy
    if not main.is_dir() or any(main.iterdir()):
        raise RehearsalError()
    checked_rename(project, legacy / ".git", main / ".git")
    approved = (
        *baseline.tracked_files,
        baseline.reviewed_untracked,
    )
    for item in approved:
        source = legacy / item.relative_path
        target = main / item.relative_path
        _create_checked_parents(project, main, target.parent)
        checked_rename(project, source, target)
    return PublishedRepository(
        container=project.source,
        legacy=legacy,
        main=main,
    )


def restore_after_legacy_failure(project: SyntheticProject) -> None:
    if project.source.exists() or not project.legacy.is_dir():
        raise RehearsalError()
    checked_rename(project, project.legacy, project.source)


def restore_after_container_failure(project: SyntheticProject) -> None:
    if (
        not project.source.is_dir()
        or not project.legacy.is_dir()
        or project.rollback_container.exists()
    ):
        raise RehearsalError()
    checked_rename(
        project,
        project.source,
        project.rollback_container,
    )
    checked_rename(project, project.legacy, project.source)


def preserve_repository_for_rollback(
    project: SyntheticProject,
    repository: PublishedRepository,
) -> PublishedRepository:
    """Move a published topology to its only preserved rollback path."""

    if (
        repository.container != project.source
        or repository.legacy != project.legacy
        or repository.main != project.source / "main"
        or project.rollback_container.exists()
    ):
        raise RehearsalError()
    identity = directory_identity(repository.container)
    checked_rename(
        project,
        repository.container,
        project.rollback_container,
    )
    if directory_identity(project.rollback_container) != identity:
        raise RehearsalError()
    return PublishedRepository(
        container=project.rollback_container,
        legacy=project.legacy,
        main=project.rollback_container / "main",
    )


def checked_rename(
    project: SyntheticProject,
    source: Path,
    target: Path,
) -> None:
    require_bound_synthetic_scope(project)
    root = project.scope.resolve(strict=True)
    source_parent = source.parent.resolve(strict=True)
    target_parent = target.parent.resolve(strict=True)
    if (
        root not in source_parent.parents
        and source_parent != root
    ) or (
        root not in target_parent.parents
        and target_parent != root
    ):
        raise RehearsalError()
    if target.exists() or target.is_symlink():
        raise RehearsalError()
    metadata = source.lstat()
    if stat.S_ISLNK(metadata.st_mode) or _reparse(metadata):
        raise RehearsalError()
    try:
        source.rename(target)
    except Exception:
        raise RehearsalError() from None
    if source.exists() or not target.exists():
        raise RehearsalError()


def _create_checked_parents(
    project: SyntheticProject,
    main: Path,
    parent: Path,
) -> None:
    try:
        relative = parent.relative_to(main)
    except ValueError:
        raise RehearsalError() from None
    current = main
    for part in relative.parts:
        if part in ("", ".", ".."):
            raise RehearsalError()
        current = current / part
        if current.exists():
            metadata = current.lstat()
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or _reparse(metadata)
            ):
                raise RehearsalError()
        else:
            current.mkdir()
        if project.scope not in current.resolve(strict=True).parents:
            raise RehearsalError()


def _reparse(metadata: object) -> bool:
    mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(
        int(getattr(metadata, "st_file_attributes", 0)) & mask
    )
