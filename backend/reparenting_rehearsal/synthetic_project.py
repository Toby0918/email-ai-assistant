"""Build the fixed temporary project used by Issue #36."""

from __future__ import annotations

from pathlib import Path

from .contract import SyntheticWorktree
from .errors import RehearsalError
from .git_runner import git_output
from .synthetic_scope import (
    capture_marker_identity,
    EXCLUDED_PATHS,
    LEGACY_NAME,
    REVIEWED_DIRTY,
    REVIEWED_UNTRACKED,
    SOURCE_NAME,
    TOP_LEVEL_NAMES,
    SyntheticProject,
    prepare_synthetic_scope,
    require_synthetic_scope,
)


def build_synthetic_project(scope: Path) -> SyntheticProject:
    """Create one deterministic synthetic topology without cloning."""

    root = prepare_synthetic_scope(scope)
    project = SyntheticProject(
        scope=root,
        marker_identity=capture_marker_identity(root),
        source=root / SOURCE_NAME,
        legacy=root / LEGACY_NAME,
        staging_container=root / "staging-container",
        evidence_target=(
            root / "evidence" / "rehearsal.migration-evidence.zip"
        ),
        remote=root / "synthetic-remote.git",
        old_worktrees=tuple(
            (item, root / "legacy-worktrees" / item.value)
            for item in SyntheticWorktree
        ),
        rollback_container=root / "rollback-container",
    )
    _create_directories(project)
    _initialize_repository(project)
    _create_dirty_and_excluded_state(project)
    _create_staging_container(project)
    require_synthetic_project(project)
    return project


def require_synthetic_project(project: SyntheticProject) -> None:
    if type(project) is not SyntheticProject:
        raise RehearsalError()
    root = require_bound_synthetic_scope(project)
    required = (
        project.source,
        project.staging_container,
        project.evidence_target.parent,
        project.remote,
        *(path for _, path in project.old_worktrees),
    )
    try:
        escaped = any(
            root not in path.resolve(strict=True).parents
            for path in required
        )
    except Exception:
        raise RehearsalError() from None
    if escaped:
        raise RehearsalError()
    require_synthetic_remote(project, repository=project.source)


def require_synthetic_remote(
    project: SyntheticProject,
    *,
    repository: Path,
) -> None:
    root = require_bound_synthetic_scope(project)
    try:
        selected_repository = repository.resolve(strict=True)
        remote_path = project.remote.resolve(strict=True)
    except Exception:
        raise RehearsalError() from None
    if (
        root not in selected_repository.parents
        or root not in remote_path.parents
        or project.remote.is_symlink()
        or (
            hasattr(project.remote, "is_junction")
            and project.remote.is_junction()
        )
    ):
        raise RehearsalError()
    remote_value = git_output(
        root,
        selected_repository,
        ("config", "--get", "remote.origin.url"),
    ).strip()
    try:
        remote = Path(remote_value).resolve(strict=True)
    except Exception:
        raise RehearsalError() from None
    if remote != remote_path:
        raise RehearsalError()


def require_bound_synthetic_scope(project: SyntheticProject) -> Path:
    if type(project) is not SyntheticProject:
        raise RehearsalError()
    return require_synthetic_scope(
        project.scope,
        marker_identity=project.marker_identity,
    )


def _create_directories(project: SyntheticProject) -> None:
    for path in (
        project.source,
        project.evidence_target.parent,
        project.old_worktree(SyntheticWorktree.ALPHA).parent,
        project.scope / "process-temp",
    ):
        path.mkdir()


def _initialize_repository(project: SyntheticProject) -> None:
    _initialize_empty_repository(project)
    _configure_remote_baseline(project)
    _commit_ahead_and_add_worktrees(project)


def _initialize_empty_repository(project: SyntheticProject) -> None:
    git_output(
        project.scope,
        project.scope,
        ("init", "--bare", str(project.remote)),
    )
    git_output(
        project.scope,
        project.scope,
        ("init", "--initial-branch=master", str(project.source)),
    )
    git_output(
        project.scope,
        project.source,
        ("config", "user.name", "Synthetic Rehearsal"),
    )
    git_output(
        project.scope,
        project.source,
        ("config", "user.email", "rehearsal@example.test"),
    )
    _write_tracked_sources(project.source)
    git_output(
        project.scope,
        project.source,
        ("add", ".gitignore", "README.md", "backend/service.py"),
    )
    git_output(
        project.scope,
        project.source,
        ("commit", "-m", "initial synthetic state"),
    )


def _configure_remote_baseline(project: SyntheticProject) -> None:
    initial = _head(project)
    git_output(
        project.scope,
        project.source,
        ("remote", "add", "origin", str(project.remote)),
    )
    git_output(
        project.scope,
        project.source,
        ("update-ref", "refs/remotes/origin/master", initial),
    )
    git_output(
        project.scope,
        project.source,
        ("config", "branch.master.remote", "origin"),
    )
    git_output(
        project.scope,
        project.source,
        ("config", "branch.master.merge", "refs/heads/master"),
    )


def _commit_ahead_and_add_worktrees(project: SyntheticProject) -> None:
    _write_new(project.source / "local.md", "local ahead commit\n")
    git_output(project.scope, project.source, ("add", "local.md"))
    git_output(
        project.scope,
        project.source,
        ("commit", "-m", "local synthetic commit"),
    )
    for item, path in project.old_worktrees:
        git_output(
            project.scope,
            project.source,
            (
                "worktree",
                "add",
                "-b",
                f"synthetic-{item.value}",
                str(path),
                "HEAD",
            ),
        )


def _write_tracked_sources(source: Path) -> None:
    _write_new(
        source / ".gitignore",
        "\n".join(
            (
                ".env",
                "*.pem",
                ".venv/",
                "outputs/",
                ".idea/",
                ".cache/",
                "*.sqlite",
                "runtime/",
                "logs/",
                "private/",
                "",
            )
        ),
    )
    _write_new(source / "README.md", "# Synthetic project\n")
    _write_new(
        source / "backend" / "service.py",
        "def state():\n    return 'initial'\n",
    )


def _create_dirty_and_excluded_state(project: SyntheticProject) -> None:
    service = project.source / "backend" / "service.py"
    service.write_text(
        "def state():\n    return 'staged'\n",
        encoding="utf-8",
    )
    git_output(
        project.scope,
        project.source,
        ("add", "backend/service.py"),
    )
    service.write_text(
        "def state():\n    return 'worktree'\n",
        encoding="utf-8",
    )
    _write_new(
        project.source / REVIEWED_UNTRACKED,
        "reviewed synthetic source\n",
    )
    for index, relative in enumerate(EXCLUDED_PATHS):
        _write_new(
            project.source / relative,
            f"excluded synthetic canary {index}\n",
        )


def _create_staging_container(project: SyntheticProject) -> None:
    project.staging_container.mkdir()
    for name in TOP_LEVEL_NAMES:
        (project.staging_container / name).mkdir()
    runtime = (
        project.staging_container
        / "Runtimes"
        / "python-3.12.13-sqlite-3.50.4"
    )
    runtime.mkdir()
    _write_new(runtime / "python.exe", "")


def _write_new(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def _head(project: SyntheticProject) -> str:
    value = git_output(
        project.scope,
        project.source,
        ("rev-parse", "HEAD"),
    ).strip()
    if len(value) != 40:
        raise RehearsalError()
    return value
