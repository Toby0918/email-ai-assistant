"""Fixed names and marker-bound temporary scope for Issue #36."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat
import tempfile

from .contract import SyntheticWorktree
from .errors import RehearsalError


MarkerIdentity = tuple[int, int]
MARKER_NAME = ".issue36-synthetic-scope"
MARKER_VALUE = "issue36-reparenting-rehearsal-v1\n"
SOURCE_NAME = "email_ai_assistant"
LEGACY_NAME = "email_ai_assistant-legacy-source"
TOP_LEVEL_NAMES = (
    "main",
    "Runtimes",
    "LocalData",
    "RuntimeTemp",
    "Logs",
    "Artifacts",
    "Worktrees",
    "Config",
    "OperatorPrivate",
)
REVIEWED_UNTRACKED = "docs/reviewed_note.md"
REVIEWED_DIRTY = ("backend/service.py", REVIEWED_UNTRACKED)
EXCLUDED_PATHS = (
    ".env",
    "signing.pem",
    ".venv/runtime.bin",
    "outputs/build.bin",
    ".idea/workspace.xml",
    ".cache/cache.bin",
    "data/email_analysis.sqlite",
    "runtime/request.tmp",
    "logs/service.log",
    "private/excluded.bin",
)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticProject:
    scope: Path
    marker_identity: MarkerIdentity
    source: Path
    legacy: Path
    staging_container: Path
    evidence_target: Path
    remote: Path
    old_worktrees: tuple[tuple[SyntheticWorktree, Path], ...]
    rollback_container: Path

    def old_worktree(self, worktree: SyntheticWorktree) -> Path:
        matches = tuple(
            path for item, path in self.old_worktrees if item is worktree
        )
        if len(matches) != 1:
            raise RehearsalError()
        return matches[0]


def prepare_synthetic_scope(scope: Path) -> Path:
    root = _require_scope_path(scope)
    if any(root.iterdir()) or not root.name.startswith("issue36-synthetic-"):
        raise RehearsalError()
    marker = root / MARKER_NAME
    with marker.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(MARKER_VALUE)
    return require_synthetic_scope(root)


def require_synthetic_scope(
    scope: Path,
    *,
    marker_identity: MarkerIdentity | None = None,
) -> Path:
    root = _require_scope_path(scope)
    marker = root / MARKER_NAME
    current_identity = _marker_identity(marker)
    if (
        not root.name.startswith("issue36-synthetic-")
        or not marker.is_file()
        or marker.is_symlink()
        or marker.read_text(encoding="utf-8") != MARKER_VALUE
        or _marker_identity(marker) != current_identity
        or (
            marker_identity is not None
            and current_identity != marker_identity
        )
    ):
        raise RehearsalError()
    return root


def capture_marker_identity(scope: Path) -> MarkerIdentity:
    root = require_synthetic_scope(scope)
    return _marker_identity(root / MARKER_NAME)


def _require_scope_path(scope: Path) -> Path:
    configured = Path(scope).absolute()
    if not configured.is_dir():
        raise RehearsalError()
    for component in _path_components(configured):
        if _is_reparse(component):
            raise RehearsalError()
    try:
        root = configured.resolve(strict=True)
        temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
    except Exception:
        raise RehearsalError() from None
    if (
        root != configured
        or temporary_root not in root.parents
        or not root.name.startswith("issue36-synthetic-")
    ):
        raise RehearsalError()
    return root


def _path_components(path: Path) -> tuple[Path, ...]:
    current = Path(path.anchor)
    components: list[Path] = []
    for part in path.parts[1:]:
        current = current / part
        components.append(current)
    return tuple(components)


def _marker_identity(marker: Path) -> MarkerIdentity:
    try:
        metadata = marker.lstat()
    except Exception:
        raise RehearsalError() from None
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or _is_reparse(marker)
    ):
        raise RehearsalError()
    return metadata.st_dev, metadata.st_ino


def _is_reparse(path: Path) -> bool:
    metadata = path.lstat()
    mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return (
        stat.S_ISLNK(metadata.st_mode)
        or bool(int(getattr(metadata, "st_file_attributes", 0)) & mask)
        or (
            path.is_junction()
            if hasattr(path, "is_junction")
            else False
        )
    )
