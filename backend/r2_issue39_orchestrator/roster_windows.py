"""Fixed Git/Windows observer for the Issue #39 roster contract."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path, PureWindowsPath

from backend.cutover_repository_transaction.git_executable import (
    resolved_executable,
)
from backend.cutover_repository_transaction.windows_identity import (
    directory_identity,
    opaque_directory_fingerprint,
)

from .roster import _DiscoveredWorktree, _RosterPorts


_MAX_WORKTREES = 16
_MAX_OUTPUT = 256 * 1024


def production_roster_ports() -> _RosterPorts:
    return _RosterPorts(_discover_production_roster)


def _discover_production_roster(root: Path):
    executable = resolved_executable()
    payload = _git(
        executable, root, ("worktree", "list", "--porcelain", "-z")
    )
    records = _parse_worktree_records(payload)
    canonical_root = _validated_original_directory(root)
    root_key = _path_key(canonical_root)
    if sum(_path_key(item[0]) == root_key for item in records) != 1:
        raise ValueError
    linked = tuple(item for item in records if _path_key(item[0]) != root_key)
    return tuple(
        _observe_worktree(executable, canonical_root, *record) for record in linked
    )


def _parse_worktree_records(payload: bytes):
    if type(payload) is not bytes or len(payload) > _MAX_OUTPUT:
        raise ValueError
    chunks = payload.split(b"\0\0")
    if not chunks or chunks[-1] != b"":
        raise ValueError
    values = []
    paths = set()
    for chunk in chunks[:-1]:
        fields = chunk.split(b"\0")
        if len(fields) != 3 or not fields[0].startswith(b"worktree "):
            raise ValueError
        path_text = fields[0][9:].decode("utf-8")
        listed_path = PureWindowsPath(path_text)
        path = Path(path_text)
        path_key = str(listed_path).casefold()
        head = fields[1][5:].decode("ascii") if fields[1].startswith(b"HEAD ") else ""
        mode = fields[2]
        if (
            not listed_path.is_absolute()
            or not _git_oid(head)
            or not (mode == b"detached" or mode.startswith(b"branch refs/heads/"))
            or path_key in paths
        ):
            raise ValueError
        paths.add(path_key)
        values.append((path, head, mode))
    if not values or len(values) > _MAX_WORKTREES + 1:
        raise ValueError
    return tuple(values)


def _observe_worktree(executable, root, path, listed_head, listed_mode):
    path = _validated_original_directory(path)
    head = _git(executable, path, ("rev-parse", "HEAD")).strip().decode("ascii")
    branch, code = _git_result(
        executable, path, ("symbolic-ref", "-q", "HEAD")
    )
    if code not in {0, 1}:
        raise ValueError
    branch_value = branch.strip() if code == 0 else b"DETACHED"
    expected_mode = b"branch " + branch_value if code == 0 else b"detached"
    if head != listed_head or expected_mode != listed_mode:
        raise ValueError
    common_text = _git(
        executable,
        path,
        ("rev-parse", "--path-format=absolute", "--git-common-dir"),
    ).strip().decode("utf-8")
    common = _validated_original_directory(Path(common_text))
    admin_text = _git(
        executable,
        path,
        ("rev-parse", "--path-format=absolute", "--git-dir"),
    ).strip().decode("utf-8")
    admin = _validated_original_directory(Path(admin_text))
    status = _git(
        executable,
        path,
        ("status", "--porcelain=v2", "-z", "--untracked-files=all"),
    )
    placement = (
        "embedded" if root / ".worktrees" in path.parents else "external"
    )
    return _DiscoveredWorktree(
        path=path,
        placement=placement,
        identity_fingerprint=_path_identity(path),
        admin_identity_fingerprint=directory_identity(admin),
        admin_content_fingerprint=opaque_directory_fingerprint(admin),
        head_oid=head,
        branch_fingerprint=hashlib.sha256(branch_value).hexdigest(),
        common_fingerprint=_path_identity(common),
        status_fingerprint=hashlib.sha256(status).hexdigest(),
        clean=status == b"",
        admin_path=admin,
        common_path=common,
    )


def _git(executable, cwd, arguments) -> bytes:
    payload, code = _git_result(executable, cwd, arguments)
    if code != 0:
        raise ValueError
    return payload


def _git_result(executable, cwd, arguments):
    from .production_process import run_bounded

    result = run_bounded(
        (str(executable), "-c", "core.hooksPath=NUL", *arguments),
        cwd=cwd,
        env=_git_environment(cwd.anchor),
        timeout=20,
        output_limit=_MAX_OUTPUT,
    )
    return result.stdout, result.returncode


def _git_environment(anchor: str) -> dict[str, str]:
    allowed = (
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "WINDIR",
    )
    value = {name: os.environ[name] for name in allowed if name in os.environ}
    value.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CEILING_DIRECTORIES": anchor,
        }
    )
    return value


def _validated_original_directory(path: Path) -> Path:
    if type(path) is not type(Path()) or not path.is_absolute():
        raise ValueError
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        metadata = current.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & 0x400
            or current.is_symlink()
            or current.is_junction()
        ):
            raise ValueError
    return path


def _path_identity(path: Path) -> str:
    metadata = path.lstat()
    return _fingerprint(
        "r2-issue39-path-identity-v1",
        {
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "mode": stat.S_IFMT(metadata.st_mode),
        },
    )


def _fingerprint(domain: str, value) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _git_oid(value: str) -> bool:
    return len(value) == 40 and all(item in "0123456789abcdef" for item in value)
