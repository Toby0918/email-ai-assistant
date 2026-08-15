"""Phase-aware exact roster checks before every Issue #39 host effect."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from backend.cutover_repository_transaction.windows_identity import (
    directory_identity,
    opaque_directory_fingerprint,
    opaque_directory_fingerprint_with_gitdir,
)
from backend.cutover_repository_transaction.git_executable import resolved_executable
from .roster import _selection_fingerprint

from .roster_windows import (
    _git,
    _git_result,
    _path_identity,
    _validated_original_directory,
)


def reverify_evolving_roster(host, action, direction):
    snapshot = host._prepared._roster._snapshot
    if not snapshot or any(
        item.admin_path is None or item.common_path is None for item in snapshot
    ):
        raise ValueError("R2_ISSUE39_ROSTER_REVERIFY_INVALID")
    common = _current_common(host)
    if _path_identity(common) != snapshot[0].common_fingerprint:
        raise ValueError("R2_ISSUE39_ROSTER_COMMON_DRIFT")
    admins = _admin_directories(common)
    expected_admins = {item.admin_identity_fingerprint for item in snapshot}
    if set(admins) != expected_admins:
        raise ValueError("R2_ISSUE39_ROSTER_ADMIN_DRIFT")
    allowed_worktree_partial = None
    if action is not None and action.action_name.startswith("worktree_reconstruction_"):
        from .production_foundation import worktree_partial

        allowed_worktree_partial = worktree_partial(host, action, direction)
    for index, item in enumerate(snapshot, start=1):
        physical, final = _current_physical(host, item.path, index)
        if _path_identity(physical) != item.identity_fingerprint:
            raise ValueError("R2_ISSUE39_ROSTER_PHYSICAL_DRIFT")
        admin = admins[item.admin_identity_fingerprint]
        if final:
            try:
                _verify_final_git(host, item, physical, admin)
            except Exception:
                if not (
                    allowed_worktree_partial is not None
                    and action.action_name.endswith(f"{index:02d}")
                ):
                    raise
        elif not _admin_matches_snapshot(host, item, admin):
            raise ValueError("R2_ISSUE39_ROSTER_ADMIN_CONTENT_DRIFT")
    _require_no_extra_final_worktrees(host, snapshot)


def terminal_roster_fingerprint(host):
    """Rebuild the exact final roster from live Git and filesystem identities."""

    snapshot = host._prepared._roster._snapshot
    common = _validated_original_directory(host._layout.main / ".git")
    if _path_identity(common) != snapshot[0].common_fingerprint:
        raise ValueError("R2_ISSUE39_ROSTER_COMMON_DRIFT")
    admins = _admin_directories(common)
    facts = []
    for index, item in enumerate(snapshot, start=1):
        physical = _validated_original_directory(
            host._layout.worktrees / f"worktree_{index:02d}"
        )
        if _path_identity(physical) != item.identity_fingerprint:
            raise ValueError("R2_ISSUE39_ROSTER_PHYSICAL_DRIFT")
        admin = admins[item.admin_identity_fingerprint]
        _verify_final_git(host, item, physical, admin, common)
        if not _admin_matches_snapshot(host, item, admin):
            raise ValueError("R2_ISSUE39_ROSTER_ADMIN_CONTENT_DRIFT")
        facts.append(_roster_fact(item, physical, admin, common))
    _require_no_extra_final_worktrees(host, snapshot)
    return _fingerprint("r2-issue39-terminal-roster-v1", facts)


def legacy_roster_fingerprint(host):
    """Rebuild the original linked-worktree topology after reverse recovery."""

    snapshot = host._prepared._roster._snapshot
    common = _validated_original_directory(host._layout.source / ".git")
    if _path_identity(common) != snapshot[0].common_fingerprint:
        raise ValueError("R2_ISSUE39_ROSTER_COMMON_DRIFT")
    admins = _admin_directories(common)
    facts = []
    for item in snapshot:
        physical = _validated_original_directory(item.path)
        if _path_identity(physical) != item.identity_fingerprint:
            raise ValueError("R2_ISSUE39_ROSTER_PHYSICAL_DRIFT")
        admin = admins[item.admin_identity_fingerprint]
        _verify_final_git(host, item, physical, admin, common)
        facts.append(_roster_fact(item, physical, admin, common))
    if os.path.lexists(host._layout.worktrees):
        raise ValueError("R2_ISSUE39_ROSTER_PLACEMENT_DRIFT")
    return _fingerprint("r2-issue39-legacy-roster-v1", facts)


def _current_common(host):
    candidates = (
        host._layout.source / ".git",
        host._layout.legacy / ".git",
        host._layout.main / ".git",
    )
    present = tuple(path for path in candidates if os.path.lexists(path))
    if len(present) != 1:
        raise ValueError("R2_ISSUE39_ROSTER_COMMON_AMBIGUOUS")
    return _validated_original_directory(present[0])


def _admin_directories(common):
    parent = common / "worktrees"
    parent = _validated_original_directory(parent)
    values = {}
    for child in parent.iterdir():
        child = _validated_original_directory(child)
        identity = directory_identity(child)
        if identity in values:
            raise ValueError("R2_ISSUE39_ROSTER_ADMIN_DUPLICATE")
        values[identity] = child
    return values


def _current_physical(host, original, index):
    transitional = [original]
    if host._layout.source in original.parents:
        transitional.append(
            host._layout.legacy / original.relative_to(host._layout.source)
        )
    final = host._layout.worktrees / f"worktree_{index:02d}"
    present = tuple(
        (path, is_final)
        for path, is_final in (
            *((path, False) for path in transitional),
            (final, True),
        )
        if os.path.lexists(path)
    )
    if len(present) != 1:
        raise ValueError("R2_ISSUE39_ROSTER_PLACEMENT_DRIFT")
    return _validated_original_directory(present[0][0]), present[0][1]


def _verify_final_git(host, item, physical, admin, expected_common=None):
    executable = resolved_executable()
    head = _git(executable, physical, ("rev-parse", "HEAD")).strip().decode("ascii")
    branch, code = _git_result(
        executable, physical, ("symbolic-ref", "-q", "HEAD")
    )
    branch_value = branch.strip() if code == 0 else b"DETACHED"
    status = _git(
        executable, physical,
        ("status", "--porcelain=v2", "-z", "--untracked-files=all"),
    )
    common_text = _git(
        executable, physical,
        ("rev-parse", "--path-format=absolute", "--git-common-dir"),
    ).strip().decode("utf-8")
    admin_text = _git(
        executable, physical,
        ("rev-parse", "--path-format=absolute", "--git-dir"),
    ).strip().decode("utf-8")
    if (
        code not in {0, 1}
        or head != item.head_oid
        or hashlib.sha256(branch_value).hexdigest()
        != item.branch_fingerprint
        or status != b""
        or hashlib.sha256(status).hexdigest()
        != item.status_fingerprint
        or _validated_original_directory(Path(common_text))
        != (expected_common or host._layout.main / ".git")
        or _validated_original_directory(Path(admin_text)) != admin
    ):
        raise ValueError("R2_ISSUE39_ROSTER_GIT_DRIFT")


def _require_no_extra_final_worktrees(host, snapshot):
    root = host._layout.worktrees
    if not os.path.lexists(root):
        return
    root = _validated_original_directory(root)
    allowed = {f"worktree_{index:02d}" for index in range(1, len(snapshot) + 1)}
    if any(child.name not in allowed for child in root.iterdir()):
        raise ValueError("R2_ISSUE39_ROSTER_ADDITION")


def _recognized_gitdir(host, item, admin):
    try:
        value = Path((admin / "gitdir").read_text(encoding="utf-8").strip())
        candidates = {item.path / ".git"}
        if host._layout.source in item.path.parents:
            candidates.add(
                host._layout.legacy / item.path.relative_to(host._layout.source) / ".git"
            )
        index = host._prepared._roster._snapshot.index(item) + 1
        candidates.add(host._layout.worktrees / f"worktree_{index:02d}" / ".git")
        return value in candidates
    except Exception:
        return False


def _admin_matches_snapshot(host, item, admin):
    if opaque_directory_fingerprint(admin) == item.admin_content_fingerprint:
        return True
    if not _recognized_gitdir(host, item, admin):
        return False
    original = (item.path / ".git").as_posix().encode("utf-8") + b"\n"
    return (
        opaque_directory_fingerprint_with_gitdir(admin, original)
        == item.admin_content_fingerprint
    )


def _roster_fact(item, physical, admin, common):
    return {
        "selection_fingerprint": _selection_fingerprint(item),
        "physical_identity": _path_identity(physical),
        "admin_identity": directory_identity(admin),
        "common_identity": _path_identity(common),
    }


def _fingerprint(domain, value):
    payload = json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()
