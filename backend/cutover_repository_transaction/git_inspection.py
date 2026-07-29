"""Bounded, scope-bound Git observations for a reviewed synthetic topology."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .errors import RepositoryTransactionError
from .git_runner import _BoundSyntheticGitRunner
from .scope_models import _ObservedWorktree, _SyntheticWorktreePaths
from .windows_identity import (
    directory_identity,
    opaque_directory_fingerprint,
)


def observe_git_topology(
    runner: _BoundSyntheticGitRunner,
    source: Path,
    expected: tuple[_SyntheticWorktreePaths, ...],
) -> tuple[tuple[_ObservedWorktree, ...], dict[str, str]]:
    common = _resolved_git_path(runner, source, common=True)
    expected_paths = (source, *(item.original for item in expected))
    listed = _listed_worktrees(runner, source)
    expected_keys = tuple(_path_key(path) for path in expected_paths)
    if (
        len(listed) != len(expected_keys)
        or len(set(listed)) != len(listed)
        or set(listed) != set(expected_keys)
    ):
        _fail()
    common_identity = directory_identity(common)
    observations = tuple(
        _observe_worktree(runner, item, common, common_identity)
        for item in expected
    )
    _require_exact_admin_namespace(common, observations)
    selections = _git_selections(
        runner, source, common_identity, observations
    )
    return observations, selections


def exact_admin_children(namespace: Path) -> dict[str, Path]:
    if not namespace.is_dir() or namespace.is_symlink():
        _fail()
    result: dict[str, Path] = {}
    for child in namespace.iterdir():
        key = child.name.casefold()
        if (
            not child.is_dir()
            or child.is_symlink()
            or not child.name
            or key in result
        ):
            _fail()
        directory_identity(child)
        result[key] = child
    return result


def _observe_worktree(runner, item, common, common_identity):
    path = item.original
    observed_common = _resolved_git_path(runner, path, common=True)
    admin = _resolved_git_path(runner, path, common=False)
    if (
        directory_identity(observed_common) != common_identity
        or admin.parent != common / "worktrees"
        or not admin.name
    ):
        _fail()
    ref = _text(runner.symbolic_ref(path))
    commit = _text(runner.head(path))
    status = runner.status(path)
    if status or not ref.startswith("refs/heads/") or len(commit) != 40:
        _fail()
    return _ObservedWorktree(
        paths=item,
        ref=ref,
        commit=commit,
        common=common,
        admin=admin,
        physical_identity=directory_identity(path),
        admin_identity=directory_identity(admin),
        admin_content=opaque_directory_fingerprint(admin),
        status_fingerprint=_fingerprint("clean-status", status),
    )


def _git_selections(runner, source, common_identity, observations):
    status_material = b"".join(
        bytes.fromhex(item.status_fingerprint) for item in observations
    )
    topology = b"".join(
        _path_key(item.paths.original).encode("utf-8")
        + b"\0" + item.ref.encode("utf-8")
        + b"\0" + item.commit.encode("ascii")
        for item in observations
    )
    return {
        "repository_identity": _fingerprint(
            "repository", bytes.fromhex(directory_identity(source))
        ),
        "common_directory_identity": _fingerprint(
            "common", bytes.fromhex(common_identity)
        ),
        "git_executable": _fingerprint(
            "git-executable",
            bytes.fromhex(runner.binding_fingerprint),
        ),
        "remote_configuration": _fingerprint(
            "remote-configuration", runner.remote_config(source)
        ),
        "local_refs": _fingerprint(
            "local-refs", runner.local_refs(source)
        ),
        "dirty_layers": _fingerprint(
            "dirty-layers", status_material
        ),
        "worktree_topology": _fingerprint("topology", topology),
    }


def _listed_worktrees(
    runner: _BoundSyntheticGitRunner, source: Path
) -> tuple[str, ...]:
    payload = runner.worktree_list(source)
    return tuple(
        _path_key(Path(field[9:].decode("utf-8")))
        for field in payload.split(b"\0")
        if field.startswith(b"worktree ")
    )


def _resolved_git_path(runner, cwd, *, common: bool) -> Path:
    payload = runner.common_dir(cwd) if common else runner.git_dir(cwd)
    value = _text(payload)
    try:
        path = Path(value).resolve(strict=True)
    except (OSError, RuntimeError):
        _fail()
    if runner.root not in path.parents:
        _fail()
    return path


def _require_exact_admin_namespace(common, observations) -> None:
    children = exact_admin_children(common / "worktrees")
    expected = {item.admin.name.casefold() for item in observations}
    if set(children) != expected:
        _fail()


def _text(payload: bytes) -> str:
    try:
        return payload.decode("utf-8", "strict").strip()
    except UnicodeError:
        _fail()


def _path_key(path: Path) -> str:
    try:
        return os.path.normcase(str(path.resolve(strict=True)))
    except (OSError, RuntimeError):
        _fail()


def _fingerprint(domain: str, *materials: bytes) -> str:
    digest = hashlib.sha256(domain.encode("ascii") + b"\0")
    for material in materials:
        digest.update(len(material).to_bytes(8, "big"))
        digest.update(material)
    return digest.hexdigest()


def _fail() -> None:
    raise RepositoryTransactionError("repository_scope_invalid") from None
