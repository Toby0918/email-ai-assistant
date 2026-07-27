"""Content-free Git installation and worktree selection bindings."""

from __future__ import annotations

import shutil
from pathlib import Path

from .canonical import (
    fingerprint,
    object_identity_fingerprint,
    path_fingerprint,
)
from .review_bridge import (
    git_output,
    require_existing_non_reparse_directory,
)


_ERROR = "MIGRATION_EVIDENCE_PROFILE_BINDING_REJECTED"


def directory_selection(path: Path) -> str:
    return fingerprint(
        "migration-evidence-directory-selection-v1",
        {
            "path_sha256": path_fingerprint(path),
            "identity_fingerprint": object_identity_fingerprint(path),
        },
    )


def git_common_directory(root: Path) -> Path:
    payload = git_output(
        root,
        ("rev-parse", "--git-common-dir"),
        maximum=4096,
    )
    if payload is None:
        raise ValueError(_ERROR)
    raw = payload.decode("utf-8").strip()
    if not raw or "\n" in raw or "\r" in raw:
        raise ValueError(_ERROR)
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return require_existing_non_reparse_directory(path)


def git_executable_selection(root: Path) -> str:
    executable = shutil.which("git")
    if type(executable) is not str:
        raise ValueError(_ERROR)
    path = Path(executable).resolve(strict=True)
    payload = git_output(root, ("--version",), maximum=512)
    if payload is None or len(payload) > 512:
        raise ValueError(_ERROR)
    return fingerprint(
        "migration-evidence-git-executable-v1",
        {
            "path_sha256": path_fingerprint(path),
            "identity_fingerprint": object_identity_fingerprint(path),
            "version_sha256": fingerprint(
                "migration-evidence-git-version-v1",
                payload.hex(),
            ),
        },
    )


def worktree_roster(
    ordered: tuple[Path, ...],
    reviewed_by_path: dict[Path, object],
) -> tuple[dict[str, str], ...]:
    result = []
    for index, path in enumerate(ordered, start=1):
        item = reviewed_by_path[path]
        role = f"worktree_{index:02d}"
        placement = "embedded" if index <= 8 else "external"
        if item.is_main is not (index == 1):
            raise ValueError(_ERROR)
        selection = fingerprint(
            "migration-evidence-worktree-selection-v1",
            {
                "role": role,
                "placement": placement,
                "path_sha256": item.path_sha256,
                "branch_ref": item.branch_ref,
                "head_oid": item.head_oid,
                "status_sha256": item.status_sha256,
                "status_count": item.status_count,
                "is_main": item.is_main,
            },
        )
        result.append(
            {
                "role": role,
                "placement": placement,
                "selection_fingerprint": selection,
            }
        )
    return tuple(result)
