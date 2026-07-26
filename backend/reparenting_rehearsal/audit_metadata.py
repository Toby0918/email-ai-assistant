"""Content-free identities for synthetic ContainerAudit evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path
import stat

from .contract import SyntheticWorktree
from .errors import RehearsalError
from .synthetic_scope import TOP_LEVEL_NAMES


VOLUME_ID = hashlib.sha256(
    b"issue36-synthetic-audit-volume"
).hexdigest()
CONTAINER_ACL = hashlib.sha256(
    b"issue36-synthetic-container-acl"
).hexdigest()
OPERATOR_ACL = hashlib.sha256(
    b"issue36-synthetic-operator-acl"
).hexdigest()


def path_identity(path: Path, *, directory: bool) -> str:
    metadata = path.lstat()
    expected = (
        stat.S_ISDIR(metadata.st_mode)
        if directory
        else stat.S_ISREG(metadata.st_mode)
    )
    if not expected or path.is_symlink():
        raise RehearsalError()
    kind = "directory" if directory else "file"
    return hashlib.sha256(
        f"{metadata.st_dev}:{metadata.st_ino}:{kind}".encode("ascii")
    ).hexdigest()


def approval_id(worktree: SyntheticWorktree) -> str:
    return hashlib.sha256(
        f"issue36-{worktree.value}".encode("ascii")
    ).hexdigest()


def top_level_roots(container: Path) -> dict[str, Path]:
    return {name: container / name for name in TOP_LEVEL_NAMES}


def pinned_runtime(container: Path) -> Path:
    return (
        container
        / "Runtimes"
        / "python-3.12.13-sqlite-3.50.4"
    )


def audited_paths(
    container: Path,
    main: Path,
    worktrees: tuple[Path, ...],
) -> tuple[tuple[Path, bool], ...]:
    roots = top_level_roots(container)
    pinned = pinned_runtime(container)
    return (
        (container, True),
        *((roots[name], True) for name in TOP_LEVEL_NAMES),
        (main / ".git", True),
        *((path, True) for path in worktrees),
        (pinned, True),
        (pinned / "python.exe", False),
    )


def require_empty(path: Path) -> None:
    if any(path.iterdir()):
        raise RehearsalError()
