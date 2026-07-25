"""Strict content-free evidence values for injected read-only adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class AuditObjectKind(str, Enum):
    DIRECTORY = "directory"
    FILE = "file"


class OperatorPrivateState(str, Enum):
    DISABLED = "disabled"


class ExternalPrivateState(str, Enum):
    NOT_PROVISIONED = "not_provisioned"


class MetadataRole(str, Enum):
    CURRENT_LOG = "current_log"
    ROTATED_LOG = "rotated_log"
    PID = "pid"
    ARTIFACT = "artifact"


@dataclass(frozen=True, slots=True, repr=False)
class AuditObject:
    identity: str
    kind: AuditObjectKind
    volume_identity: str
    readable: bool = True
    canonical: bool = True
    has_reparse_component: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class TopLevelEntry:
    name: str
    object: AuditObject
    direct_child_of_container: bool


@dataclass(frozen=True, slots=True, repr=False)
class MetadataEntry:
    object: AuditObject
    size_bytes: int
    role: MetadataRole


@dataclass(frozen=True, slots=True, repr=False)
class BoundedMetadataInventory:
    root_identity: str
    entries: tuple[MetadataEntry, ...]
    inventory_complete: bool
    direct_only: bool
    content_observed: bool


@dataclass(frozen=True, slots=True, repr=False)
class ConfigMetadata:
    directory_identity: str
    filename: str
    present: bool
    settings_file: AuditObject | None
    size_bytes: int
    keys: tuple[str, ...]
    inventory_complete: bool
    direct_only: bool
    values_observed: bool


@dataclass(frozen=True, slots=True, repr=False)
class FilesystemEvidence:
    schema_version: int
    container: AuditObject
    entries: tuple[TopLevelEntry, ...]
    inventory_complete: bool
    config: ConfigMetadata
    logs: BoundedMetadataInventory
    artifacts: BoundedMetadataInventory
    operator_private_state: OperatorPrivateState
    operator_private_content_observed: bool
    raw_vault_state: ExternalPrivateState
    recovery_state: ExternalPrivateState


@dataclass(frozen=True, slots=True, repr=False)
class AclEvidence:
    schema_version: int
    container_identity: str
    container_fingerprint: str
    operator_private_identity: str
    operator_private_fingerprint: str
    inventory_complete: bool


@dataclass(frozen=True, slots=True, repr=False)
class VolumeEvidence:
    schema_version: int
    volume_identity: str
    filesystem_name: str
    drive_type: str
    bound_identities: tuple[str, ...]
    inventory_complete: bool


@dataclass(frozen=True, slots=True, repr=False)
class GitEvidence:
    schema_version: int
    inventory_complete: bool
    repository_count: int
    common_directory_count: int
    repository: AuditObject
    common_directory: AuditObject
    repository_name: str
    common_directory_name: str
    common_directory_inside_repository: bool
    common_directory_direct_child_of_repository: bool
    content_observed: bool


@dataclass(frozen=True, slots=True, repr=False)
class WorktreeRelationship:
    approval_id: str
    worktree: AuditObject
    common_directory_identity: str
    direct_child_of_worktrees: bool
    linked: bool
    branch_attached: bool
    clean: bool
    content_observed: bool


@dataclass(frozen=True, slots=True, repr=False)
class WorktreeEvidence:
    schema_version: int
    inventory_complete: bool
    main_worktree_count: int
    worktrees_root_identity: str
    relationships: tuple[WorktreeRelationship, ...]


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeEvidence:
    schema_version: int
    inventory_complete: bool
    runtime_count: int
    runtime_root: AuditObject
    pinned_runtime: AuditObject
    executable: AuditObject
    python_version: str
    sqlite_version: str
    executable_location_exact: bool
    pinned_runtime_location_exact: bool


@dataclass(frozen=True, slots=True, repr=False)
class SqliteEvidence:
    schema_version: int
    local_data_identity: str
    inventory_complete: bool
    service_stopped: bool
    present: bool
    filename: str
    database: AuditObject | None
    database_location_exact: bool
    size_bytes: int
    sidecars: tuple[str, ...]
    integrity_ok: bool
    schema_complete: bool
    aggregate_row_count: int
    rows_observed: bool
    query_only: bool


FilesystemAdapter = Callable[[], FilesystemEvidence]
AclAdapter = Callable[[], AclEvidence]
VolumeAdapter = Callable[[], VolumeEvidence]
GitAdapter = Callable[[], GitEvidence]
WorktreeAdapter = Callable[[], WorktreeEvidence]
RuntimeAdapter = Callable[[], RuntimeEvidence]
SqliteAdapter = Callable[[], SqliteEvidence]


@dataclass(frozen=True, slots=True, repr=False)
class ContainerAuditAdapters:
    filesystem: FilesystemAdapter
    acl: AclAdapter
    volume: VolumeAdapter
    git: GitAdapter
    worktree: WorktreeAdapter
    runtime: RuntimeAdapter
    sqlite: SqliteAdapter
