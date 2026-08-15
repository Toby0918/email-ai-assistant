"""Fixed foundation, repository, and worktree host transitions."""

from __future__ import annotations

import os
import hashlib
import stat
from pathlib import Path

from backend.cutover_repository_transaction.git_executable import resolved_executable

from .production_native import create_directory_no_replace, move_no_replace


_ZONES = (
    "Runtimes", "LocalData", "RuntimeTemp", "Logs", "Artifacts",
    "Worktrees", "Config", "OperatorPrivate",
)


def mutate_foundation(host, action, direction, attempt_token=None):
    name = action.action_name
    if name == "legacy_service_quiescence":
        return _service(host, action, direction, attempt_token)
    if name == "legacy_anchor_rename":
        source, target = host._layout.source, host._layout.legacy
        if direction == "forward":
            if os.path.lexists(source):
                move_no_replace(source, target)
            return
        if os.path.lexists(target):
            move_no_replace(target, source)
        _repair_all_original_worktrees(host)
        return
    if name == "container_publication":
        if direction == "forward":
            return create_directory_no_replace(
                host._layout.container.parent, host._layout.container
            )
        return move_no_replace(host._layout.container, host._layout.failed)
    if name == "main_publication":
        if direction == "forward":
            return create_directory_no_replace(
                host._layout.main.parent, host._layout.main
            )
        from .production_host_state import seal_action

        return seal_action(host, action, direction)
    if name == "acl_whole_tree_conformance":
        from .production_acl import apply_fixed_acl, restore_original_acl

        return apply_fixed_acl(host) if direction == "forward" else restore_original_acl(host)
    if name == "repository_relocation":
        from .production_repository import relocate_repository

        return relocate_repository(host, direction)
    raise ValueError("R2_ISSUE39_FOUNDATION_INVALID")


def foundation_state(host, name, reverse=False):
    layout = host._layout
    if name == "legacy_service_quiescence":
        return _legacy_matches_preimage(host) if reverse else _legacy_stopped(host)
    if name == "legacy_anchor_rename":
        relocated = (
            _exact_pair(layout.source, layout.legacy)
            if reverse else _exact_pair(layout.legacy, layout.source)
        )
        return relocated and (
            _all_original_worktrees_exact(host) if reverse else True
        )
    if name == "container_publication":
        if reverse:
            return _directory(layout.failed) and not os.path.lexists(layout.container)
        return _directory(layout.container) and _directory(layout.legacy)
    if name == "main_publication":
        return _directory(layout.main) if not reverse else False
    if name == "acl_whole_tree_conformance":
        from .production_acl import fixed_acl_conforms, original_acl_restored

        return original_acl_restored(host) if reverse else fixed_acl_conforms(host)
    if name == "repository_relocation":
        from .production_repository import repository_exact

        return repository_exact(host, reverse=reverse)
    raise ValueError("R2_ISSUE39_FOUNDATION_INVALID")


def mutate_worktree(host, action, direction):
    item = _worktree(host, action)
    original = _current_original(host, item.path)
    target = host._layout.worktrees / ("worktree_" + action.action_name[-2:])
    source, destination = (
        (original, target) if direction == "forward" else (target, original)
    )
    if os.path.lexists(source):
        move_no_replace(source, destination)
    _repair_worktree(host, destination)
    if not _worktree_semantic_exact(host, item, destination):
        raise ValueError("R2_ISSUE39_WORKTREE_REPAIR_INVALID")


def worktree_state(host, action, reverse=False):
    item = _worktree(host, action)
    original = _current_original(host, item.path)
    target = host._layout.worktrees / ("worktree_" + action.action_name[-2:])
    expected, absent = (original, target) if reverse else (target, original)
    if _directory(expected) and not os.path.lexists(absent):
        return _worktree_semantic_exact(host, item, expected)
    if os.path.lexists(expected) and os.path.lexists(absent):
        raise ValueError("R2_ISSUE39_WORKTREE_AMBIGUOUS")
    return False


def _worktree(host, action):
    index = int(action.action_name[-2:]) - 1
    snapshot = host._prepared._roster._snapshot
    if not 0 <= index < len(snapshot):
        raise ValueError("R2_ISSUE39_WORKTREE_INVALID")
    return snapshot[index]


def _current_original(host, original):
    if host._layout.source in original.parents:
        mapped = host._layout.legacy / original.relative_to(host._layout.source)
        if os.path.lexists(mapped) or not os.path.lexists(original):
            return mapped
    return original


def _service(host, action, direction, attempt_token):
    from .production_service import restore_legacy_service, stop_legacy_service

    return (
        restore_legacy_service(host, action, attempt_token)
        if direction == "rollback" else stop_legacy_service(host)
    )


def _legacy_stopped(host):
    from .production_service import observe_legacy_service

    root = host._layout.source if host._layout.source.joinpath(".git").is_dir() else host._layout.legacy
    return observe_legacy_service(root)["status"] == "STOPPED"


def _legacy_matches_preimage(host):
    from .production_service import legacy_recovery_observation

    try:
        return legacy_recovery_observation(host)["status"] == host._legacy_service[
            "status"
        ]
    except Exception:
        return False


def _git(cwd, arguments):
    from .production_process import run_bounded
    from .roster_windows import _git_environment

    result = run_bounded(
        (str(resolved_executable()), "-c", "core.hooksPath=NUL", *arguments),
        cwd=cwd, env=_git_environment(cwd.anchor), timeout=30,
        output_limit=1024 * 1024,
    )
    if result.returncode != 0:
        raise ValueError("R2_ISSUE39_GIT_ACTION_FAILED")
    return result.stdout


def _exact_pair(present, absent):
    return _directory(present) and (absent is None or not os.path.lexists(absent))


def _directory(path):
    try:
        value = path.lstat()
        return stat.S_ISDIR(value.st_mode) and not (
            getattr(value, "st_file_attributes", 0) & 0x400
        ) and not path.is_symlink() and not path.is_junction()
    except OSError:
        return False


def _regular(path):
    try:
        value = path.lstat()
        return stat.S_ISREG(value.st_mode) and not (
            getattr(value, "st_file_attributes", 0) & 0x400
        ) and not path.is_symlink()
    except OSError:
        return False


def foundation_partial(host, action, direction):
    if action.action_name == "repository_relocation":
        from .production_repository import repository_partial

        return repository_partial(host, action, direction)
    if (
        action.action_name == "acl_whole_tree_conformance"
        and direction == "forward"
    ):
        from .production_acl import acl_partial_state

        return acl_partial_state(host, action)
    if (
        action.action_name == "legacy_anchor_rename"
        and direction == "rollback"
        and _exact_pair(host._layout.source, host._layout.legacy)
        and not _all_original_worktrees_exact(host)
    ):
        return hashlib.sha256(
            b"r2-issue39-legacy-repair-partial-v1\0"
            + action.action_fingerprint.encode("ascii")
        ).hexdigest()
    return None


def worktree_partial(host, action, direction):
    if not action.action_name.startswith("worktree_reconstruction_"):
        return None
    item = _worktree(host, action)
    original = _current_original(host, item.path)
    target = host._layout.worktrees / ("worktree_" + action.action_name[-2:])
    expected = target if direction == "forward" else original
    absent = original if direction == "forward" else target
    if (
        _directory(expected) and not os.path.lexists(absent)
        and not _worktree_semantic_exact(host, item, expected)
        and _worktree_admin_recognized(host, item, expected, target)
    ):
        return hashlib.sha256(
            b"r2-issue39-worktree-partial-v1\0"
            + action.action_fingerprint.encode("ascii")
            + direction.encode("ascii")
        ).hexdigest()
    return None


def _repair_worktree(host, path):
    _git(host._layout.main, ("worktree", "repair", str(path)))


def _repair_all_original_worktrees(host):
    for item in host._prepared._roster._snapshot:
        path = item.path
        _git(host._layout.source, ("worktree", "repair", str(path)))


def _all_original_worktrees_exact(host):
    return all(
        _worktree_semantic_exact(host, item, item.path)
        for item in host._prepared._roster._snapshot
    )

def _worktree_semantic_exact(host, item, path):
    try:
        from .production_roster_reverify import _verify_final_git

        expected_common = (
            host._layout.source / ".git"
            if host._layout.source.joinpath(".git").is_dir()
            else host._layout.main / ".git"
        )
        _verify_final_git(host, item, path, _current_admin(host, item), expected_common)
        return True
    except Exception:
        return False


def _current_admin(host, item):
    for base in (host._layout.source, host._layout.legacy, host._layout.main):
        if host._layout.source / ".git" in item.admin_path.parents:
            candidate = base / item.admin_path.relative_to(host._layout.source)
        else:
            candidate = item.admin_path
        if os.path.lexists(candidate):
            return candidate
    raise ValueError("R2_ISSUE39_WORKTREE_ADMIN_MISSING")


def _worktree_admin_recognized(host, item, physical, final_target):
    admin = _current_admin(host, item)
    try:
        from backend.cutover_repository_transaction.windows_identity import (
            directory_identity, opaque_directory_fingerprint,
        )

        if directory_identity(admin) != item.admin_identity_fingerprint:
            return False
        if opaque_directory_fingerprint(admin) == item.admin_content_fingerprint:
            return True
        payload = (admin / "gitdir").read_text(encoding="utf-8").strip()
        return Path(payload).resolve(strict=False) in {
            physical / ".git", final_target / ".git"
        }
    except Exception:
        return False
