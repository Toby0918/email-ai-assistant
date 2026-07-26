"""Apply exact reviewed repair/recreate choices to synthetic worktrees."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat

from .baseline import LinkedWorktreeBaseline, RepositoryBaseline
from .contract import (
    ReviewedWorktreeChoice,
    SyntheticWorktree,
    WorktreeStrategy,
)
from .errors import RehearsalError
from .git_runner import git_output
from .publication import PublishedRepository, checked_rename
from .synthetic_project import (
    SyntheticProject,
    require_bound_synthetic_scope,
)


@dataclass(frozen=True, slots=True, repr=False)
class PublishedWorktrees:
    paths: tuple[tuple[SyntheticWorktree, Path], ...]
    preserved_originals: tuple[Path, ...]
    preserved_admin: tuple[Path, ...]

    def path(self, worktree: SyntheticWorktree) -> Path:
        matches = tuple(
            path for item, path in self.paths if item is worktree
        )
        if len(matches) != 1:
            raise RehearsalError()
        return matches[0]


def publish_worktrees(
    *,
    project: SyntheticProject,
    repository: PublishedRepository,
    baseline: RepositoryBaseline,
    choices: tuple[ReviewedWorktreeChoice, ...],
) -> PublishedWorktrees:
    """Publish every fixed worktree according to its reviewed choice."""

    require_bound_synthetic_scope(project)
    choice_map = {choice.worktree: choice.strategy for choice in choices}
    if len(choice_map) != len(SyntheticWorktree):
        raise RehearsalError()
    _require_absent_targets(repository)
    published: list[tuple[SyntheticWorktree, Path]] = []
    originals: list[Path] = []
    admin_holds: list[Path] = []
    for strategy in (WorktreeStrategy.REPAIR, WorktreeStrategy.RECREATE):
        for worktree in SyntheticWorktree:
            if choice_map.get(worktree) is not strategy:
                continue
            target = repository.container / "Worktrees" / worktree.value
            item = baseline.linked(worktree)
            if strategy is WorktreeStrategy.REPAIR:
                _repair(
                    project,
                    repository.main,
                    item.path,
                    target,
                )
            else:
                hold = _recreate(
                    project,
                    repository.main,
                    item,
                    target,
                )
                originals.append(item.path)
                admin_holds.append(hold)
            published.append((worktree, target))
    paths = tuple(sorted(published, key=lambda item: item[0].value))
    if len(paths) != len(SyntheticWorktree):
        raise RehearsalError()
    return PublishedWorktrees(
        paths=paths,
        preserved_originals=tuple(originals),
        preserved_admin=tuple(admin_holds),
    )


def repair_worktree_metadata(
    *,
    project: SyntheticProject,
    main: Path,
    worktrees: tuple[Path, ...],
) -> None:
    """Repair only reviewed synthetic paths after a container rename."""

    require_bound_synthetic_scope(project)
    if not worktrees:
        raise RehearsalError()
    git_output(
        project.scope,
        main,
        ("worktree", "repair", "--", *(str(path) for path in worktrees)),
    )


def relocate_published_worktrees(
    published: PublishedWorktrees,
    *,
    source_container: Path,
    rollback_container: Path,
) -> PublishedWorktrees:
    """Project preserved paths through one whole-container rename."""

    def relocate(path: Path) -> Path:
        try:
            relative = path.relative_to(source_container)
        except ValueError:
            return path
        return rollback_container / relative

    return PublishedWorktrees(
        paths=tuple(
            (item, relocate(path)) for item, path in published.paths
        ),
        preserved_originals=published.preserved_originals,
        preserved_admin=tuple(
            relocate(path) for path in published.preserved_admin
        ),
    )


def _repair(
    project: SyntheticProject,
    main: Path,
    source: Path,
    target: Path,
) -> None:
    checked_rename(project, source, target)
    git_output(
        project.scope,
        main,
        ("worktree", "repair", "--", str(target)),
    )


def _recreate(
    project: SyntheticProject,
    main: Path,
    baseline: LinkedWorktreeBaseline,
    target: Path,
) -> Path:
    _require_recreate_target(main, target)
    common = main / ".git"
    admin_root = common / "worktrees"
    preserved_root = common / "worktrees-preserved"
    if not preserved_root.exists():
        preserved_root.mkdir()
    admin_name = baseline.admin_name
    branch_ref = baseline.branch_ref
    original = baseline.path
    if not original.is_dir():
        raise RehearsalError()
    admin = admin_root / admin_name
    hold = preserved_root / admin_name
    _require_admin_matches(admin, original)
    checked_rename(project, admin, hold)
    branch = branch_ref.removeprefix("refs/heads/")
    if not branch or branch == branch_ref:
        raise RehearsalError()
    git_output(
        project.scope,
        main,
        ("worktree", "add", "--force", str(target), branch),
    )
    if not original.is_dir() or not (original / ".git").is_file():
        raise RehearsalError()
    return hold


def _require_absent_targets(repository: PublishedRepository) -> None:
    worktrees_root = repository.container / "Worktrees"
    _require_direct_worktrees_root(repository.container, worktrees_root)
    targets = tuple(
        worktrees_root / item.value for item in SyntheticWorktree
    )
    if any(target.exists() or target.is_symlink() for target in targets):
        raise RehearsalError()


def _require_recreate_target(main: Path, target: Path) -> None:
    container = main.parent
    worktrees_root = container / "Worktrees"
    _require_direct_worktrees_root(container, worktrees_root)
    try:
        resolved_target = target.resolve(strict=False)
        resolved_root = worktrees_root.resolve(strict=True)
    except Exception:
        raise RehearsalError() from None
    if (
        target.parent != worktrees_root
        or resolved_target.parent != resolved_root
        or target.exists()
        or target.is_symlink()
    ):
        raise RehearsalError()


def _require_direct_worktrees_root(container: Path, root: Path) -> None:
    try:
        metadata = root.lstat()
        resolved_container = container.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
    except Exception:
        raise RehearsalError() from None
    reparse_mask = int(
        getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or bool(
            int(getattr(metadata, "st_file_attributes", 0))
            & reparse_mask
        )
        or (hasattr(root, "is_junction") and root.is_junction())
        or resolved_root.parent != resolved_container
        or resolved_root.name != "Worktrees"
    ):
        raise RehearsalError()


def _require_admin_matches(admin: Path, worktree: Path) -> None:
    gitdir = admin / "gitdir"
    value = gitdir.read_text(encoding="utf-8").strip()
    if Path(value).resolve(strict=False) != (
        worktree / ".git"
    ).resolve(strict=True):
        raise RehearsalError()
