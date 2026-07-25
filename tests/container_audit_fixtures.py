from __future__ import annotations

from dataclasses import replace

from backend.container_audit import (
    AclEvidence,
    AuditObject,
    AuditObjectKind,
    BoundedMetadataInventory,
    ConfigMetadata,
    ContainerAuditAdapters,
    ExternalPrivateState,
    FilesystemEvidence,
    GitEvidence,
    MetadataEntry,
    MetadataRole,
    OperatorPrivateState,
    RuntimeEvidence,
    SqliteEvidence,
    SqliteExpectation,
    TopLevelEntry,
    TrustedAuditPolicy,
    VolumeEvidence,
    WorktreeEvidence,
    WorktreeRelationship,
)


TOP_LEVEL_NAMES = (
    "main",
    "Runtimes",
    "LocalData",
    "RuntimeTemp",
    "Logs",
    "Artifacts",
    "Worktrees",
    "Config",
    "OperatorPrivate",
)


def opaque(value: int) -> str:
    return f"{value:064x}"


class SequenceAdapter:
    def __init__(self, *values: object) -> None:
        self._values = values
        self.calls = 0

    def __call__(self) -> object:
        value = self._values[min(self.calls, len(self._values) - 1)]
        self.calls += 1
        return value

    @property
    def first(self) -> object:
        return self._values[0]


class RaisingAdapter:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def __call__(self) -> object:
        self.calls += 1
        raise self.error


def first_evidence(
    adapters: ContainerAuditAdapters,
    name: str,
) -> object:
    adapter = getattr(adapters, name)
    if type(adapter) is not SequenceAdapter:
        raise AssertionError("expected synthetic SequenceAdapter")
    return adapter.first


def with_adapter(
    adapters: ContainerAuditAdapters,
    name: str,
    first: object,
    second: object | None = None,
) -> ContainerAuditAdapters:
    values = (first, first if second is None else second)
    return replace(
        adapters,
        **{name: SequenceAdapter(*values)},
    )


def valid_audit_inputs() -> tuple[TrustedAuditPolicy, ContainerAuditAdapters]:
    volume_id = opaque(900)
    container = AuditObject(
        identity=opaque(1),
        kind=AuditObjectKind.DIRECTORY,
        volume_identity=volume_id,
    )
    entries = tuple(
        TopLevelEntry(
            name=name,
            object=AuditObject(
                identity=opaque(index + 10),
                kind=AuditObjectKind.DIRECTORY,
                volume_identity=volume_id,
            ),
            direct_child_of_container=True,
        )
        for index, name in enumerate(TOP_LEVEL_NAMES)
    )
    roots = {entry.name: entry.object for entry in entries}
    filesystem = _valid_filesystem(container, entries, roots)
    acl = AclEvidence(
        schema_version=1,
        container_identity=container.identity,
        container_fingerprint=opaque(901),
        operator_private_identity=roots["OperatorPrivate"].identity,
        operator_private_fingerprint=opaque(902),
        inventory_complete=True,
    )
    common_directory = AuditObject(
        identity=opaque(30),
        kind=AuditObjectKind.DIRECTORY,
        volume_identity=volume_id,
    )
    git = GitEvidence(
        schema_version=1,
        inventory_complete=True,
        repository_count=1,
        common_directory_count=1,
        repository=roots["main"],
        common_directory=common_directory,
        repository_name="main",
        common_directory_name=".git",
        common_directory_inside_repository=True,
        common_directory_direct_child_of_repository=True,
        content_observed=False,
    )
    worktrees = WorktreeEvidence(
        schema_version=1,
        inventory_complete=True,
        main_worktree_count=1,
        worktrees_root_identity=roots["Worktrees"].identity,
        relationships=(),
    )
    pinned_runtime = AuditObject(
        identity=opaque(31),
        kind=AuditObjectKind.DIRECTORY,
        volume_identity=volume_id,
    )
    executable = AuditObject(
        identity=opaque(32),
        kind=AuditObjectKind.FILE,
        volume_identity=volume_id,
    )
    runtime = RuntimeEvidence(
        schema_version=1,
        inventory_complete=True,
        runtime_count=1,
        runtime_root=roots["Runtimes"],
        pinned_runtime=pinned_runtime,
        executable=executable,
        python_version="3.12.13",
        sqlite_version="3.50.4",
        executable_location_exact=True,
        pinned_runtime_location_exact=True,
    )
    sqlite = _absent_sqlite(roots["LocalData"])
    audited = (
        container,
        *(entry.object for entry in entries),
        common_directory,
        pinned_runtime,
        executable,
    )
    volume = VolumeEvidence(
        schema_version=1,
        volume_identity=volume_id,
        filesystem_name="NTFS",
        drive_type="fixed",
        bound_identities=tuple(
            sorted(item.identity for item in audited)
        ),
        inventory_complete=True,
    )
    policy = TrustedAuditPolicy(
        schema_version=1,
        container_identity=container.identity,
        container_acl_fingerprint=acl.container_fingerprint,
        operator_private_acl_fingerprint=(
            acl.operator_private_fingerprint
        ),
        volume_identity=volume_id,
        approved_worktrees=(),
        require_clean_worktrees=True,
        sqlite_expectation=SqliteExpectation.ABSENT_EXPECTED,
    )
    adapters = ContainerAuditAdapters(
        filesystem=SequenceAdapter(filesystem, filesystem),
        acl=SequenceAdapter(acl, acl),
        volume=SequenceAdapter(volume, volume),
        git=SequenceAdapter(git, git),
        worktree=SequenceAdapter(worktrees, worktrees),
        runtime=SequenceAdapter(runtime, runtime),
        sqlite=SequenceAdapter(sqlite, sqlite),
    )
    return policy, adapters


def _valid_filesystem(
    container: AuditObject,
    entries: tuple[TopLevelEntry, ...],
    roots: dict[str, AuditObject],
) -> FilesystemEvidence:
    return FilesystemEvidence(
        schema_version=1,
        container=container,
        entries=entries,
        inventory_complete=True,
        config=ConfigMetadata(
            directory_identity=roots["Config"].identity,
            filename="settings.env",
            present=False,
            settings_file=None,
            size_bytes=0,
            keys=(),
            inventory_complete=True,
            direct_only=True,
            values_observed=False,
        ),
        logs=BoundedMetadataInventory(
            root_identity=roots["Logs"].identity,
            entries=(),
            inventory_complete=True,
            direct_only=True,
            content_observed=False,
        ),
        artifacts=BoundedMetadataInventory(
            root_identity=roots["Artifacts"].identity,
            entries=(),
            inventory_complete=True,
            direct_only=True,
            content_observed=False,
        ),
        operator_private_state=OperatorPrivateState.DISABLED,
        operator_private_content_observed=False,
        raw_vault_state=ExternalPrivateState.NOT_PROVISIONED,
        recovery_state=ExternalPrivateState.NOT_PROVISIONED,
    )


def _absent_sqlite(local_data: AuditObject) -> SqliteEvidence:
    return SqliteEvidence(
        schema_version=1,
        local_data_identity=local_data.identity,
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


def populated_audit_inputs(
) -> tuple[TrustedAuditPolicy, ContainerAuditAdapters]:
    policy, adapters = valid_audit_inputs()
    filesystem = first_evidence(adapters, "filesystem")
    git = first_evidence(adapters, "git")
    volume = first_evidence(adapters, "volume")
    sqlite = first_evidence(adapters, "sqlite")
    if not all(
        (
            type(filesystem) is FilesystemEvidence,
            type(git) is GitEvidence,
            type(volume) is VolumeEvidence,
            type(sqlite) is SqliteEvidence,
        )
    ):
        raise AssertionError("invalid synthetic fixture")
    roots = {entry.name: entry.object for entry in filesystem.entries}
    objects = _populated_objects(policy.volume_identity)
    populated_filesystem = replace(
        filesystem,
        config=ConfigMetadata(
            directory_identity=roots["Config"].identity,
            filename="settings.env",
            present=True,
            settings_file=objects["config"],
            size_bytes=128,
            keys=(
                "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS",
                "EMAIL_AGENT_LOG_LEVEL",
            ),
            inventory_complete=True,
            direct_only=True,
            values_observed=False,
        ),
        logs=BoundedMetadataInventory(
            root_identity=roots["Logs"].identity,
            entries=(
                MetadataEntry(
                    objects["log"],
                    500,
                    MetadataRole.CURRENT_LOG,
                ),
                MetadataEntry(
                    objects["rotated"],
                    400,
                    MetadataRole.ROTATED_LOG,
                ),
                MetadataEntry(objects["pid"], 8, MetadataRole.PID),
            ),
            inventory_complete=True,
            direct_only=True,
            content_observed=False,
        ),
        artifacts=BoundedMetadataInventory(
            root_identity=roots["Artifacts"].identity,
            entries=(
                MetadataEntry(
                    objects["artifact"],
                    1024,
                    MetadataRole.ARTIFACT,
                ),
            ),
            inventory_complete=True,
            direct_only=True,
            content_observed=False,
        ),
    )
    approval_id = opaque(1000)
    worktrees = WorktreeEvidence(
        schema_version=1,
        inventory_complete=True,
        main_worktree_count=1,
        worktrees_root_identity=roots["Worktrees"].identity,
        relationships=(
            WorktreeRelationship(
                approval_id=approval_id,
                worktree=objects["worktree"],
                common_directory_identity=git.common_directory.identity,
                direct_child_of_worktrees=True,
                linked=True,
                branch_attached=True,
                clean=True,
                content_observed=False,
            ),
        ),
    )
    present_sqlite = replace(
        sqlite,
        present=True,
        database=objects["database"],
        size_bytes=4096,
        integrity_ok=True,
        schema_complete=True,
        aggregate_row_count=42,
    )
    bound = tuple(
        sorted(
            (
                *volume.bound_identities,
                *(item.identity for item in objects.values()),
            )
        )
    )
    populated_adapters = replace(
        adapters,
        filesystem=SequenceAdapter(
            populated_filesystem,
            populated_filesystem,
        ),
        volume=SequenceAdapter(
            replace(volume, bound_identities=bound),
            replace(volume, bound_identities=bound),
        ),
        worktree=SequenceAdapter(worktrees, worktrees),
        sqlite=SequenceAdapter(present_sqlite, present_sqlite),
    )
    populated_policy = replace(
        policy,
        approved_worktrees=(approval_id,),
        sqlite_expectation=SqliteExpectation.STOPPED_PRESENT,
    )
    return populated_policy, populated_adapters


def _populated_objects(volume_identity: str) -> dict[str, AuditObject]:
    kinds = {
        "config": AuditObjectKind.FILE,
        "log": AuditObjectKind.FILE,
        "rotated": AuditObjectKind.FILE,
        "pid": AuditObjectKind.FILE,
        "artifact": AuditObjectKind.DIRECTORY,
        "worktree": AuditObjectKind.DIRECTORY,
        "database": AuditObjectKind.FILE,
    }
    return {
        name: AuditObject(
            identity=opaque(100 + index),
            kind=kind,
            volume_identity=volume_identity,
        )
        for index, (name, kind) in enumerate(kinds.items())
    }
