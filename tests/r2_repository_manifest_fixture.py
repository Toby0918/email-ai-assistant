"""Complete synthetic repository/eleven-worktree fixture for Issue #75."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.cutover_repository_transaction.synthetic_scope import (
    _SyntheticWorktreePaths,
)
from tests.cutover_repository_transaction_fixtures import (
    SyntheticRepositoryScenario,
)


def build_manifest_repository_scenario(
    directory: Path | None = None,
    *,
    shared_root: Path | None = None,
    shared_source: Path | None = None,
) -> SyntheticRepositoryScenario:
    owner = None
    if shared_root is None:
        owner = tempfile.TemporaryDirectory(
            prefix="issue56-synthetic-manifest-",
            dir=str(directory) if directory is not None else None,
        )
        root = Path(owner.name).resolve(strict=True)
        source = root / "Container"
    else:
        root = shared_root
        source = shared_source
        if source != root / "Container" or not source.is_dir():
            raise ValueError("shared repository container invalid")
    marker = root / ".codex-cutover-mutation-test-sandbox"
    marker.write_bytes(b"issue56-synthetic-marker-v1")
    parents = _prepare_parents(root)
    _run(root, "init", "-b", "master", str(source))
    _run(source, "config", "user.name", "Synthetic Operator")
    _run(source, "config", "user.email", "synthetic@example.test")
    _build_manifest_content(source)
    additions = (
        (".",)
        if shared_root is not None
        else (".gitignore", "README.md", "whole-selected", "mixed/selected.txt")
    )
    _run(source, "add", *additions)
    _run(source, "commit", "-m", "synthetic manifest baseline")
    _exclude_worktree_roots(source)
    worktrees = _create_worktrees(root, source, parents)
    (source / "approved-note.txt").write_text(
        "synthetic approved untracked\n", "utf-8"
    )
    _build_residue(source)
    return SyntheticRepositoryScenario(
        owner=owner,
        root=root,
        marker=marker,
        source=source,
        legacy=(
            root / "RepositoryLegacyAnchorV1"
            if shared_root is not None
            else root / "LegacySourceAnchorV1"
        ),
        failed_container=root / "FailedContainerV1",
        journal_root=parents["journal"],
        admin_preservation=parents["admin"],
        worktree_preservation=parents["physical"],
        rollback_root=parents["rollback"],
        external_target_parent=parents["external_target"],
        worktrees=worktrees,
    )


def _prepare_parents(root: Path) -> dict[str, Path]:
    values = {
        "admin": root / "preservation" / "admin",
        "physical": root / "preservation" / "physical",
        "rollback": root / "rollback-evidence",
        "external_original": root / "external-original",
        "external_target": root / "external-target",
        "journal": root / "journal",
        "finance": root / "finance-synthetic",
    }
    for path in values.values():
        path.mkdir(parents=True, exist_ok=True)
    return values


def _build_manifest_content(source: Path) -> None:
    (source / "whole-selected").mkdir(parents=True)
    (source / "mixed").mkdir()
    (source / "README.md").write_text("synthetic repository\n", "utf-8")
    (source / "whole-selected" / "one.txt").write_text("one\n", "utf-8")
    (source / "whole-selected" / "two.txt").write_text("two\n", "utf-8")
    (source / "mixed" / "selected.txt").write_text("selected\n", "utf-8")
    (source / ".gitignore").write_text(
        "mixed/cache.bin\nprivate/\nruntime/\ndatabase/\nlogs/\ncache/\n",
        "utf-8",
    )


def _build_residue(source: Path) -> None:
    values = {
        "mixed/cache.bin": b"ignored-cache",
        "private/secret.bin": b"private-residue",
        "runtime/state.bin": b"runtime-residue",
        "database/app.db": b"database-residue",
        "logs/app.log": b"log-residue",
        "cache/blob.bin": b"cache-residue",
    }
    for relative, payload in values.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def _exclude_worktree_roots(source: Path) -> None:
    exclude = source / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n.synthetic-worktrees/\n")


def _create_worktrees(root, source, parents):
    values = []
    for index in range(1, 12):
        role = f"worktree_{index:02d}"
        original = (
            source / ".synthetic-worktrees" / f"worktree-{index:02d}"
            if index <= 8
            else parents["external_original"] / f"worktree-{index:02d}"
        )
        original.parent.mkdir(parents=True, exist_ok=True)
        _run(source, "worktree", "add", "-b", role, str(original))
        target = (
            root / "Container" / "Worktrees" / f"worktree-{index:02d}"
            if index <= 8
            else parents["external_target"] / f"worktree-{index:02d}"
        )
        values.append(
            _SyntheticWorktreePaths(
                role=role,
                placement="embedded" if index <= 8 else "external",
                original=original,
                target=target,
                preservation=parents["physical"] / role,
            )
        )
    return tuple(values)


def run_manifest_git(cwd: Path, *arguments: str) -> bytes:
    return _run(cwd, *arguments)


def _run(cwd: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        env=_environment(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
        shell=False,
    )
    if completed.returncode != 0 or len(completed.stdout) > 1_000_000:
        raise RuntimeError("synthetic_git_fixture_failed")
    return completed.stdout


def _environment(cwd: Path) -> dict[str, str]:
    allowed = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_CEILING_DIRECTORIES": str(cwd.anchor),
        }
    )
    return environment
