"""Manual orchestration for the pure injected ContainerAudit core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast

from .adapters import (
    AuditObject,
    AclEvidence,
    ContainerAuditAdapters,
    FilesystemEvidence,
    GitEvidence,
    RuntimeEvidence,
    SqliteEvidence,
    VolumeEvidence,
    WorktreeEvidence,
)
from .filesystem_checks import valid_filesystem
from .contract import (
    FAILED_RESULT,
    PASSED_RESULT,
    ContainerAuditResult,
)
from .system_checks import (
    valid_acl,
    valid_git,
    valid_runtime,
    valid_sqlite,
    valid_volume,
    valid_worktrees,
)
from .policy import TrustedAuditPolicy, is_valid_policy


@dataclass(frozen=True, slots=True, repr=False)
class _AuditSnapshot:
    filesystem: FilesystemEvidence
    acl: AclEvidence
    volume: VolumeEvidence
    git: GitEvidence
    worktree: WorktreeEvidence
    runtime: RuntimeEvidence
    sqlite: SqliteEvidence


def run_container_audit(
    *,
    policy: TrustedAuditPolicy,
    adapters: ContainerAuditAdapters,
) -> ContainerAuditResult:
    """Validate two stable bounded metadata snapshots without side effects."""
    try:
        if not is_valid_policy(policy):
            return FAILED_RESULT
        if type(adapters) is not ContainerAuditAdapters:
            return FAILED_RESULT
        first = _collect_snapshot(policy, adapters)
        if first is None:
            return FAILED_RESULT
        second = _collect_snapshot(policy, adapters)
        if second is None or second != first:
            return FAILED_RESULT
    except Exception:
        return FAILED_RESULT
    return PASSED_RESULT


def _collect_snapshot(
    policy: TrustedAuditPolicy,
    adapters: ContainerAuditAdapters,
) -> _AuditSnapshot | None:
    filesystem = _observe(adapters.filesystem)
    if not valid_filesystem(filesystem):
        return None
    volume = _observe(adapters.volume)
    if not valid_volume(policy, volume):
        return None
    acl = _observe(adapters.acl)
    if not valid_acl(policy, filesystem, acl):
        return None
    git = _observe(adapters.git)
    if not valid_git(filesystem, git):
        return None
    worktree = _observe(adapters.worktree)
    if not valid_worktrees(policy, filesystem, git, worktree):
        return None
    runtime = _observe(adapters.runtime)
    if not valid_runtime(filesystem, runtime):
        return None
    sqlite = _observe(adapters.sqlite)
    if not valid_sqlite(policy, filesystem, sqlite):
        return None
    snapshot = _AuditSnapshot(
        filesystem=cast(FilesystemEvidence, filesystem),
        acl=cast(AclEvidence, acl),
        volume=cast(VolumeEvidence, volume),
        git=cast(GitEvidence, git),
        worktree=cast(WorktreeEvidence, worktree),
        runtime=cast(RuntimeEvidence, runtime),
        sqlite=cast(SqliteEvidence, sqlite),
    )
    return snapshot if _cross_domain_valid(policy, snapshot) else None


def _observe(adapter: Callable[[], object]) -> object | None:
    try:
        return adapter()
    except Exception:
        return None


def _cross_domain_valid(
    policy: TrustedAuditPolicy,
    snapshot: _AuditSnapshot,
) -> bool:
    objects = _audited_objects(snapshot)
    identities = tuple(sorted({item.identity for item in objects}))
    return (
        len(identities) == len(objects)
        and snapshot.filesystem.container.identity
        == policy.container_identity
        and all(
            item.volume_identity == policy.volume_identity
            for item in objects
        )
        and identities == snapshot.volume.bound_identities
    )


def _audited_objects(snapshot: _AuditSnapshot) -> tuple[AuditObject, ...]:
    filesystem = snapshot.filesystem
    values = [
        filesystem.container,
        *(entry.object for entry in filesystem.entries),
        *(entry.object for entry in filesystem.logs.entries),
        *(entry.object for entry in filesystem.artifacts.entries),
        snapshot.git.common_directory,
        *(item.worktree for item in snapshot.worktree.relationships),
        snapshot.runtime.pinned_runtime,
        snapshot.runtime.executable,
    ]
    if filesystem.config.settings_file is not None:
        values.append(filesystem.config.settings_file)
    if snapshot.sqlite.database is not None:
        values.append(snapshot.sqlite.database)
    return tuple(values)
