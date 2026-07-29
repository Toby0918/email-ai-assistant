"""Caller-owned synthetic sandbox path policy and pathless selections."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .errors import RepositoryTransactionError
from .scope_models import _SyntheticWorktreePaths

_MARKER_BYTES = b"issue56-synthetic-marker-v1"


def validated_scenario_paths(scenario: object) -> dict[str, object]:
    names = (
        "root", "marker", "source", "legacy", "failed_container",
        "journal_root", "admin_preservation", "worktree_preservation",
        "rollback_root", "external_target_parent", "worktrees",
    )
    if any(not hasattr(scenario, name) for name in names):
        _fail()
    paths = {name: getattr(scenario, name) for name in names}
    if type(paths["worktrees"]) is not tuple or len(paths["worktrees"]) != 11:
        _fail()
    root = _existing_directory(paths["root"])
    marker = _existing_file(paths["marker"])
    if marker.read_bytes() != _MARKER_BYTES or not _is_temp_root(root):
        _fail()
    for name in names[2:-1]:
        if name in {"legacy", "failed_container"}:
            _require_descendant(Path(paths[name]), root, allow_absent=True)
        else:
            _require_descendant(Path(paths[name]), root)
    worktrees = tuple(
        _validated_worktree_paths(item, root, index)
        for index, item in enumerate(paths["worktrees"], start=1)
    )
    return {**paths, "root": root, "marker": marker, "worktrees": worktrees}


def role_selections(paths):
    root = paths["root"]
    source = paths["source"]
    values = {
        "projects_parent": root,
        "finance_project": root / "finance-synthetic",
        "project_container": source,
        "repository_root": source,
        "runtimes": source / "Runtimes",
        "local_data": source / "LocalData",
        "runtime_temp": source / "RuntimeTemp",
        "logs": source / "Logs",
        "artifacts": source / "Artifacts",
        "worktrees": source / "Worktrees",
        "config": source / "Config",
        "operator_private": source / "OperatorPrivate",
        "legacy_source": paths["legacy"],
        "failed_container": paths["failed_container"],
    }
    return _path_fingerprint_map("role", values)


def evidence_roles(paths):
    root = paths["root"]
    values = {
        "review_root": root,
        "package_target": root / "package-target",
        "journal_root": paths["journal_root"],
        "git_records_preservation": paths["admin_preservation"],
        "worktree_preservation": paths["worktree_preservation"],
        "rollback_publication": paths["rollback_root"],
    }
    return _path_fingerprint_map("evidence", values)


def rollback_roles(paths):
    values = {
        "failed_container": paths["failed_container"],
        "legacy_main": paths["source"],
        "legacy_git_records": paths["admin_preservation"],
        "legacy_worktrees": paths["worktree_preservation"],
        "legacy_runtime": paths["root"] / "legacy-runtime",
        "legacy_database": paths["root"] / "legacy-database",
    }
    return _path_fingerprint_map("rollback", values)


def normalized_absent_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _validated_worktree_paths(item, root, index):
    if type(item) is not _SyntheticWorktreePaths:
        _fail()
    role = f"worktree_{index:02d}"
    placement = "embedded" if index <= 8 else "external"
    if item.role != role or item.placement != placement:
        _fail()
    _require_descendant(item.original, root)
    _require_descendant(item.target, root, allow_absent=True)
    _require_descendant(item.preservation, root, allow_absent=True)
    if item.target.exists() or item.preservation.exists():
        _fail()
    return item


def _path_fingerprint_map(domain, values):
    return {
        name: _fingerprint(
            f"{domain}-{name}", normalized_absent_path(path)
        )
        for name, path in values.items()
    }


def _existing_directory(value: object) -> Path:
    if not isinstance(value, Path) or not value.is_dir() or value.is_symlink():
        _fail()
    return value.resolve(strict=True)


def _existing_file(value: object) -> Path:
    if not isinstance(value, Path) or not value.is_file() or value.is_symlink():
        _fail()
    return value.resolve(strict=True)


def _require_descendant(path, root, allow_absent=False):
    candidate = Path(os.path.abspath(path))
    if root not in candidate.parents:
        _fail()
    if not allow_absent:
        _existing_directory(candidate)


def _is_temp_root(root: Path) -> bool:
    try:
        temp = Path(tempfile.gettempdir()).resolve(strict=True)
    except OSError:
        return False
    return temp in root.parents and root.name.startswith("issue56-synthetic-")


def _fingerprint(domain: str, *values: str) -> str:
    payload = json.dumps(
        list(values), ensure_ascii=True, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()


def _fail() -> None:
    raise RepositoryTransactionError("repository_scope_invalid") from None
