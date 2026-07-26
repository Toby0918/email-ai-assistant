"""The only Issue #36 bridge to the injected ContainerAudit core."""

from __future__ import annotations

from pathlib import Path

from backend.container_audit import (
    AclEvidence,
    AuditObject,
    AuditObjectKind,
    AuditStatus,
    BoundedMetadataInventory,
    ConfigMetadata,
    ContainerAuditAdapters,
    ExternalPrivateState,
    FilesystemEvidence,
    GitEvidence,
    OperatorPrivateState,
    RuntimeEvidence,
    SqliteEvidence,
    SqliteExpectation,
    TopLevelEntry,
    TrustedAuditPolicy,
    VolumeEvidence,
    WorktreeEvidence,
    WorktreeRelationship,
    run_container_audit,
)

from . import audit_metadata as metadata
from .baseline import current_branch
from .contract import SyntheticWorktree
from .errors import RehearsalError
from .git_runner import git_output
from .publication import PublishedRepository
from .synthetic_project import (
    TOP_LEVEL_NAMES, SyntheticProject, require_bound_synthetic_scope,
)
from .worktrees import PublishedWorktrees


def require_passed_container_audit(
    *,
    project: SyntheticProject,
    repository: PublishedRepository,
    worktrees: PublishedWorktrees,
) -> None:
    require_bound_synthetic_scope(project)
    reader = _SyntheticAuditReader(project, repository, worktrees)
    policy = reader.policy()
    result = run_container_audit(
        policy=policy,
        adapters=ContainerAuditAdapters(
            filesystem=reader.filesystem,
            acl=reader.acl,
            volume=reader.volume,
            git=reader.git,
            worktree=reader.worktree,
            runtime=reader.runtime,
            sqlite=reader.sqlite,
        ),
    )
    if result.status is not AuditStatus.PASSED:
        raise RehearsalError()


class _SyntheticAuditReader:
    def __init__(
        self,
        project: SyntheticProject,
        repository: PublishedRepository,
        worktrees: PublishedWorktrees,
    ) -> None:
        self._project = project
        self._repository = repository
        self._worktrees = worktrees

    def policy(self) -> TrustedAuditPolicy:
        return TrustedAuditPolicy(
            schema_version=1,
            container_identity=self._directory(
                self._repository.container
            ).identity,
            container_acl_fingerprint=metadata.CONTAINER_ACL,
            operator_private_acl_fingerprint=metadata.OPERATOR_ACL,
            volume_identity=metadata.VOLUME_ID,
            approved_worktrees=tuple(
                sorted(metadata.approval_id(item) for item in SyntheticWorktree)
            ),
            require_clean_worktrees=True,
            sqlite_expectation=SqliteExpectation.ABSENT_EXPECTED,
        )

    def filesystem(self) -> FilesystemEvidence:
        roots = self._roots()
        container = self._directory(self._repository.container)
        names = {path.name for path in self._repository.container.iterdir()}
        if names != set(TOP_LEVEL_NAMES):
            raise RehearsalError()
        metadata.require_empty(roots["Config"])
        metadata.require_empty(roots["Logs"])
        metadata.require_empty(roots["Artifacts"])
        metadata.require_empty(roots["OperatorPrivate"])
        return FilesystemEvidence(
            schema_version=1,
            container=container,
            entries=tuple(
                TopLevelEntry(
                    name=name,
                    object=self._directory(roots[name]),
                    direct_child_of_container=True,
                )
                for name in TOP_LEVEL_NAMES
            ),
            inventory_complete=True,
            config=ConfigMetadata(
                directory_identity=self._directory(roots["Config"]).identity,
                filename="settings.env",
                present=False,
                settings_file=None,
                size_bytes=0,
                keys=(),
                inventory_complete=True,
                direct_only=True,
                values_observed=False,
            ),
            logs=self._empty_inventory(roots["Logs"]),
            artifacts=self._empty_inventory(roots["Artifacts"]),
            operator_private_state=OperatorPrivateState.DISABLED,
            operator_private_content_observed=False,
            raw_vault_state=ExternalPrivateState.NOT_PROVISIONED,
            recovery_state=ExternalPrivateState.NOT_PROVISIONED,
        )

    def acl(self) -> AclEvidence:
        roots = self._roots()
        return AclEvidence(
            schema_version=1,
            container_identity=self._directory(
                self._repository.container
            ).identity,
            container_fingerprint=metadata.CONTAINER_ACL,
            operator_private_identity=self._directory(
                roots["OperatorPrivate"]
            ).identity,
            operator_private_fingerprint=metadata.OPERATOR_ACL,
            inventory_complete=True,
        )

    def volume(self) -> VolumeEvidence:
        objects = self._audited_objects()
        return VolumeEvidence(
            schema_version=1,
            volume_identity=metadata.VOLUME_ID,
            filesystem_name="NTFS",
            drive_type="fixed",
            bound_identities=tuple(sorted(item.identity for item in objects)),
            inventory_complete=True,
        )

    def git(self) -> GitEvidence:
        roots = self._roots()
        return GitEvidence(
            schema_version=1,
            inventory_complete=True,
            repository_count=1,
            common_directory_count=1,
            repository=self._directory(roots["main"]),
            common_directory=self._directory(self._repository.main / ".git"),
            repository_name="main",
            common_directory_name=".git",
            common_directory_inside_repository=True,
            common_directory_direct_child_of_repository=True,
            content_observed=False,
        )

    def worktree(self) -> WorktreeEvidence:
        roots = self._roots()
        relationships = tuple(
            sorted(
                (
                    self._worktree_relationship(item)
                    for item in SyntheticWorktree
                ),
                key=lambda item: item.approval_id,
            )
        )
        return WorktreeEvidence(
            schema_version=1,
            inventory_complete=True,
            main_worktree_count=1,
            worktrees_root_identity=self._directory(
                roots["Worktrees"]
            ).identity,
            relationships=relationships,
        )

    def runtime(self) -> RuntimeEvidence:
        roots = self._roots()
        pinned = metadata.pinned_runtime(self._repository.container)
        return RuntimeEvidence(
            schema_version=1,
            inventory_complete=True,
            runtime_count=1,
            runtime_root=self._directory(roots["Runtimes"]),
            pinned_runtime=self._directory(pinned),
            executable=self._file(pinned / "python.exe"),
            python_version="3.12.13",
            sqlite_version="3.50.4",
            executable_location_exact=True,
            pinned_runtime_location_exact=True,
        )

    def sqlite(self) -> SqliteEvidence:
        roots = self._roots()
        local_data = roots["LocalData"]
        metadata.require_empty(local_data)
        return SqliteEvidence(
            schema_version=1,
            local_data_identity=self._directory(local_data).identity,
            inventory_complete=True,
            service_stopped=True,
            present=False,
            filename="email_agent.sqlite3",
            database=None,
            database_location_exact=True,
            size_bytes=0,
            sidecars=(),
            integrity_ok=False,
            schema_complete=False,
            aggregate_row_count=0,
            rows_observed=False,
            query_only=True,
        )

    def _worktree_relationship(
        self,
        worktree: SyntheticWorktree,
    ) -> WorktreeRelationship:
        path = self._worktrees.path(worktree)
        branch = current_branch(self._project, path)
        status = git_output(
            self._project.scope,
            path,
            ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        )
        return WorktreeRelationship(
            approval_id=metadata.approval_id(worktree),
            worktree=self._directory(path),
            common_directory_identity=self._directory(
                self._repository.main / ".git"
            ).identity,
            direct_child_of_worktrees=(
                path.parent == self._repository.container / "Worktrees"
            ),
            linked=True,
            branch_attached=branch.startswith("refs/heads/"),
            clean=status == "",
            content_observed=False,
        )

    def _roots(self) -> dict[str, Path]:
        return metadata.top_level_roots(self._repository.container)

    def _audited_objects(self) -> tuple[AuditObject, ...]:
        paths = metadata.audited_paths(
            self._repository.container,
            self._repository.main,
            tuple(self._worktrees.path(item) for item in SyntheticWorktree),
        )
        return tuple(
            self._directory(path) if directory else self._file(path)
            for path, directory in paths
        )

    def _directory(self, path: Path) -> AuditObject:
        return _audit_object(path, AuditObjectKind.DIRECTORY)

    def _file(self, path: Path) -> AuditObject:
        return _audit_object(path, AuditObjectKind.FILE)

    def _empty_inventory(self, path: Path) -> BoundedMetadataInventory:
        metadata.require_empty(path)
        return BoundedMetadataInventory(
            root_identity=self._directory(path).identity,
            entries=(),
            inventory_complete=True,
            direct_only=True,
            content_observed=False,
        )

def _audit_object(path: Path, kind: AuditObjectKind) -> AuditObject:
    return AuditObject(
        identity=metadata.path_identity(
            path,
            directory=kind is AuditObjectKind.DIRECTORY,
        ),
        kind=kind,
        volume_identity=metadata.VOLUME_ID,
    )
