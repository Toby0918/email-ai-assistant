"""Bounded read-only Git discovery for reviewed migration evidence."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .contract import (
    GitBaseline,
    ReviewedRef,
    ReviewedWorktree,
)
from .errors import MigrationEvidenceError
from .git_remote import remote_baseline
from .git_runner import git_output
from .path_checks import require_existing_non_reparse_directory
from .policy import validate_relative_path


_MAX_REFS = 128
_MAX_WORKTREES = 64


def status_records(root: Path) -> tuple[tuple[str, str], ...]:
    """Return sorted XY/path records, including ignored names only."""

    payload = git_output(
        root,
        (
            "-c",
            "status.renames=false",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ),
    )
    assert payload is not None
    records = list(_parse_status_payload(payload))
    ignored = git_output(
        root,
        (
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "-z",
        ),
    )
    assert ignored is not None
    for raw in ignored.split(b"\0"):
        if not raw:
            continue
        try:
            path = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise MigrationEvidenceError() from None
        records.append(("!!", validate_relative_path(path)))
    if len(records) > 2048 or len({path for _, path in records}) != len(records):
        raise MigrationEvidenceError()
    return tuple(sorted(records, key=lambda item: item[1]))


def require_plain_index(root: Path) -> None:
    """Reject skip-worktree, assume-unchanged, and special index flags."""

    payload = git_output(root, ("ls-files", "-v", "-z"))
    assert payload is not None
    for raw in payload.split(b"\0"):
        if not raw:
            continue
        if len(raw) < 3 or raw[1:2] != b" ":
            raise MigrationEvidenceError()
        try:
            flag = raw[:1].decode("ascii")
            path = raw[2:].decode("utf-8")
        except UnicodeDecodeError:
            raise MigrationEvidenceError() from None
        if flag != "H":
            raise MigrationEvidenceError()
        validate_relative_path(path)


def reviewed_refs(root: Path, names: tuple[str, ...]) -> tuple[ReviewedRef, ...]:
    """Resolve exact local branch refs without consulting remotes."""

    if type(names) is not tuple or not names or len(names) > _MAX_REFS:
        raise MigrationEvidenceError()
    if len(set(names)) != len(names):
        raise MigrationEvidenceError()
    values: list[ReviewedRef] = []
    for name in sorted(names):
        if type(name) is not str or not name.startswith("refs/heads/"):
            raise MigrationEvidenceError()
        if name.startswith("-") or any(ord(character) < 33 for character in name):
            raise MigrationEvidenceError()
        payload = git_output(root, ("show-ref", "--verify", "--hash", name))
        assert payload is not None
        oid = _one_line(payload)
        _require_oid(oid)
        values.append(ReviewedRef(name=name, oid=oid))
    return tuple(values)


def reviewed_worktrees(
    root: Path,
    approved_paths: tuple[Path, ...],
    refs: tuple[ReviewedRef, ...],
) -> tuple[ReviewedWorktree, ...]:
    """Select exact attached worktrees from the live Git roster."""

    if type(approved_paths) is not tuple or not approved_paths:
        raise MigrationEvidenceError()
    if len(approved_paths) > _MAX_WORKTREES:
        raise MigrationEvidenceError()
    discovered = _parse_worktrees(root)
    approved = tuple(_resolve_existing(path) for path in approved_paths)
    if len(set(approved)) != len(approved):
        raise MigrationEvidenceError()
    if root not in approved:
        raise MigrationEvidenceError()
    ref_map = {item.name: item.oid for item in refs}
    selected: list[ReviewedWorktree] = []
    for path in sorted(approved, key=lambda item: os.path.normcase(str(item))):
        record = discovered.get(path)
        if record is None:
            raise MigrationEvidenceError()
        head, branch = record
        if branch not in ref_map or ref_map[branch] != head:
            raise MigrationEvidenceError()
        status = status_records(path)
        encoded = _status_bytes(status)
        selected.append(
            ReviewedWorktree(
                path=path,
                path_sha256=_sha256(os.path.normcase(str(path)).encode("utf-8")),
                branch_ref=branch,
                head_oid=head,
                status_sha256=_sha256(encoded),
                status_count=len(status),
                is_main=path == root,
            )
        )
    return tuple(selected)


def git_baseline(root: Path) -> GitBaseline:
    """Capture branch, HEAD, remote fingerprints, and ahead/behind counts."""

    branch_payload = git_output(root, ("symbolic-ref", "-q", "HEAD"))
    head_payload = git_output(root, ("rev-parse", "HEAD"))
    assert branch_payload is not None and head_payload is not None
    branch = _one_line(branch_payload)
    head = _one_line(head_payload)
    _require_oid(head)
    upstream_payload = git_output(
        root,
        ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
        optional=True,
    )
    upstream = "" if upstream_payload is None else _one_line(upstream_payload)
    ahead, behind = _ahead_behind(root, upstream)
    return GitBaseline(
        branch_ref=branch,
        head_oid=head,
        upstream_ref=upstream,
        ahead=ahead,
        behind=behind,
        remotes=remote_baseline(root),
    )


def repository_root(root: Path) -> Path:
    """Require the supplied path to be the exact worktree root."""

    resolved = _resolve_existing(root)
    payload = git_output(resolved, ("rev-parse", "--show-toplevel"))
    assert payload is not None
    discovered = _resolve_existing(Path(_one_line(payload)))
    if discovered != resolved:
        raise MigrationEvidenceError()
    return resolved


def _parse_worktrees(root: Path) -> dict[Path, tuple[str, str]]:
    payload = git_output(root, ("worktree", "list", "--porcelain", "-z"))
    assert payload is not None
    records: dict[Path, tuple[str, str]] = {}
    fields: dict[str, str] = {}
    for raw in payload.split(b"\0") + [b""]:
        if raw:
            key, separator, value = raw.partition(b" ")
            try:
                fields[key.decode("ascii")] = value.decode("utf-8") if separator else ""
            except UnicodeDecodeError:
                raise MigrationEvidenceError() from None
            continue
        if not fields:
            continue
        path = _resolve_existing(Path(fields.get("worktree", "")))
        head = fields.get("HEAD", "")
        branch = fields.get("branch", "")
        _require_oid(head)
        if not branch.startswith("refs/heads/") or "prunable" in fields:
            raise MigrationEvidenceError()
        records[path] = (head, branch)
        fields = {}
    if not records or len(records) > _MAX_WORKTREES:
        raise MigrationEvidenceError()
    return records


def _ahead_behind(root: Path, upstream: str) -> tuple[int, int]:
    if not upstream:
        return 0, 0
    payload = git_output(root, ("rev-list", "--left-right", "--count", f"HEAD...{upstream}"))
    assert payload is not None
    parts = _one_line(payload).split()
    if len(parts) != 2 or not all(part.isdecimal() for part in parts):
        raise MigrationEvidenceError()
    ahead, behind = (int(part) for part in parts)
    if ahead > 1_000_000 or behind > 1_000_000:
        raise MigrationEvidenceError()
    return ahead, behind


def _status_bytes(records: tuple[tuple[str, str], ...]) -> bytes:
    return b"".join(
        status.encode("ascii") + b"\0" + path.encode("utf-8") + b"\0"
        for status, path in records
    )


def _parse_status_payload(payload: bytes) -> tuple[tuple[str, str], ...]:
    records: list[tuple[str, str]] = []
    for raw in payload.split(b"\0"):
        if not raw:
            continue
        if len(raw) < 4 or raw[2:3] != b" ":
            raise MigrationEvidenceError()
        try:
            status = raw[:2].decode("ascii")
            path = raw[3:].decode("utf-8")
        except UnicodeDecodeError:
            raise MigrationEvidenceError() from None
        records.append((status, validate_relative_path(path)))
    return tuple(records)


def _one_line(payload: bytes) -> str:
    try:
        value = payload.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise MigrationEvidenceError() from None
    if not value or "\n" in value or "\r" in value:
        raise MigrationEvidenceError()
    return value


def _require_oid(value: str) -> None:
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise MigrationEvidenceError()


def _resolve_existing(path: Path) -> Path:
    return require_existing_non_reparse_directory(path)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
