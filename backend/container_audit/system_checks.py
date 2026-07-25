"""Pure validators for system-metadata ContainerAudit evidence."""

from __future__ import annotations

from .adapters import (
    AclEvidence,
    AuditObjectKind,
    FilesystemEvidence,
    GitEvidence,
    RuntimeEvidence,
    SqliteEvidence,
    VolumeEvidence,
    WorktreeEvidence,
    WorktreeRelationship,
)
from .filesystem_checks import entry_object, valid_object
from .policy import (
    AUDIT_SCHEMA_VERSION,
    MAX_APPROVED_WORKTREES,
    MAX_SQLITE_AGGREGATE_ROW_COUNT,
    MAX_SQLITE_SIDECARS,
    MAX_SQLITE_SIZE_BYTES,
    MAX_VOLUME_BOUND_IDENTITIES,
    NORMAL_SQLITE_FILENAME,
    PINNED_PYTHON_VERSION,
    PINNED_SQLITE_VERSION,
    SqliteExpectation,
    TrustedAuditPolicy,
    is_opaque_fingerprint,
)


def valid_acl(
    policy: TrustedAuditPolicy,
    filesystem: FilesystemEvidence,
    value: object,
) -> bool:
    operator_private = entry_object(filesystem, "OperatorPrivate")
    return (
        type(value) is AclEvidence
        and type(value.schema_version) is int
        and value.schema_version == AUDIT_SCHEMA_VERSION
        and is_opaque_fingerprint(value.container_identity)
        and value.container_identity == filesystem.container.identity
        and is_opaque_fingerprint(value.container_fingerprint)
        and value.container_fingerprint
        == policy.container_acl_fingerprint
        and operator_private is not None
        and is_opaque_fingerprint(value.operator_private_identity)
        and value.operator_private_identity == operator_private.identity
        and is_opaque_fingerprint(value.operator_private_fingerprint)
        and value.operator_private_fingerprint
        == policy.operator_private_acl_fingerprint
        and type(value.inventory_complete) is bool
        and value.inventory_complete
    )


def valid_volume(
    policy: TrustedAuditPolicy,
    value: object,
) -> bool:
    return (
        type(value) is VolumeEvidence
        and type(value.schema_version) is int
        and value.schema_version == AUDIT_SCHEMA_VERSION
        and is_opaque_fingerprint(value.volume_identity)
        and value.volume_identity == policy.volume_identity
        and type(value.filesystem_name) is str
        and value.filesystem_name == "NTFS"
        and type(value.drive_type) is str
        and value.drive_type == "fixed"
        and type(value.bound_identities) is tuple
        and len(value.bound_identities) <= MAX_VOLUME_BOUND_IDENTITIES
        and all(
            is_opaque_fingerprint(identity)
            for identity in value.bound_identities
        )
        and value.bound_identities
        == tuple(sorted(set(value.bound_identities)))
        and type(value.inventory_complete) is bool
        and value.inventory_complete
    )


def valid_git(
    filesystem: FilesystemEvidence,
    value: object,
) -> bool:
    main = entry_object(filesystem, "main")
    return (
        type(value) is GitEvidence
        and type(value.schema_version) is int
        and value.schema_version == AUDIT_SCHEMA_VERSION
        and type(value.inventory_complete) is bool
        and value.inventory_complete
        and type(value.repository_count) is int
        and value.repository_count == 1
        and type(value.common_directory_count) is int
        and value.common_directory_count == 1
        and main is not None
        and valid_object(value.repository, kind=AuditObjectKind.DIRECTORY)
        and value.repository == main
        and valid_object(
            value.common_directory,
            kind=AuditObjectKind.DIRECTORY,
        )
        and type(value.repository_name) is str
        and value.repository_name == "main"
        and type(value.common_directory_name) is str
        and value.common_directory_name == ".git"
        and type(value.common_directory_inside_repository) is bool
        and value.common_directory_inside_repository
        and type(
            value.common_directory_direct_child_of_repository
        )
        is bool
        and value.common_directory_direct_child_of_repository
        and type(value.content_observed) is bool
        and not value.content_observed
    )


def _valid_worktree_relationship(
    value: object,
    *,
    policy: TrustedAuditPolicy,
    git: GitEvidence,
) -> bool:
    return (
        type(value) is WorktreeRelationship
        and is_opaque_fingerprint(value.approval_id)
        and valid_object(value.worktree, kind=AuditObjectKind.DIRECTORY)
        and is_opaque_fingerprint(value.common_directory_identity)
        and value.common_directory_identity
        == git.common_directory.identity
        and type(value.direct_child_of_worktrees) is bool
        and value.direct_child_of_worktrees
        and type(value.linked) is bool
        and value.linked
        and type(value.branch_attached) is bool
        and value.branch_attached
        and type(value.clean) is bool
        and (value.clean or not policy.require_clean_worktrees)
        and type(value.content_observed) is bool
        and not value.content_observed
    )


def valid_worktrees(
    policy: TrustedAuditPolicy,
    filesystem: FilesystemEvidence,
    git: GitEvidence,
    value: object,
) -> bool:
    if type(value) is not WorktreeEvidence:
        return False
    relationships = value.relationships
    worktrees_root = entry_object(filesystem, "Worktrees")
    return (
        type(value.schema_version) is int
        and value.schema_version == AUDIT_SCHEMA_VERSION
        and type(value.inventory_complete) is bool
        and value.inventory_complete
        and type(value.main_worktree_count) is int
        and value.main_worktree_count == 1
        and worktrees_root is not None
        and is_opaque_fingerprint(value.worktrees_root_identity)
        and value.worktrees_root_identity == worktrees_root.identity
        and type(relationships) is tuple
        and len(relationships) <= MAX_APPROVED_WORKTREES
        and all(
            _valid_worktree_relationship(
                relationship,
                policy=policy,
                git=git,
            )
            for relationship in relationships
        )
        and tuple(sorted(item.approval_id for item in relationships))
        == policy.approved_worktrees
        and len({item.worktree.identity for item in relationships})
        == len(relationships)
    )


def valid_runtime(
    filesystem: FilesystemEvidence,
    value: object,
) -> bool:
    runtime_root = entry_object(filesystem, "Runtimes")
    return (
        type(value) is RuntimeEvidence
        and type(value.schema_version) is int
        and value.schema_version == AUDIT_SCHEMA_VERSION
        and type(value.inventory_complete) is bool
        and value.inventory_complete
        and type(value.runtime_count) is int
        and value.runtime_count == 1
        and runtime_root is not None
        and valid_object(value.runtime_root, kind=AuditObjectKind.DIRECTORY)
        and value.runtime_root == runtime_root
        and valid_object(
            value.pinned_runtime,
            kind=AuditObjectKind.DIRECTORY,
        )
        and valid_object(value.executable, kind=AuditObjectKind.FILE)
        and type(value.python_version) is str
        and value.python_version == PINNED_PYTHON_VERSION
        and type(value.sqlite_version) is str
        and value.sqlite_version == PINNED_SQLITE_VERSION
        and type(value.executable_location_exact) is bool
        and value.executable_location_exact
        and type(value.pinned_runtime_location_exact) is bool
        and value.pinned_runtime_location_exact
    )


def valid_sqlite(
    policy: TrustedAuditPolicy,
    filesystem: FilesystemEvidence,
    value: object,
) -> bool:
    if type(value) is not SqliteEvidence:
        return False
    local_data = entry_object(filesystem, "LocalData")
    if (
        local_data is None
        or not is_opaque_fingerprint(value.local_data_identity)
        or value.local_data_identity != local_data.identity
        or not _valid_sqlite_common(value)
    ):
        return False
    if policy.sqlite_expectation is SqliteExpectation.ABSENT_EXPECTED:
        return _valid_absent_sqlite(value)
    return _valid_present_sqlite(value)


def _valid_sqlite_common(value: SqliteEvidence) -> bool:
    return (
        type(value.schema_version) is int
        and value.schema_version == AUDIT_SCHEMA_VERSION
        and type(value.inventory_complete) is bool
        and value.inventory_complete
        and type(value.service_stopped) is bool
        and value.service_stopped
        and type(value.present) is bool
        and type(value.filename) is str
        and value.filename == NORMAL_SQLITE_FILENAME
        and type(value.database_location_exact) is bool
        and value.database_location_exact
        and type(value.size_bytes) is int
        and 0 <= value.size_bytes <= MAX_SQLITE_SIZE_BYTES
        and type(value.sidecars) is tuple
        and len(value.sidecars) <= MAX_SQLITE_SIDECARS
        and all(type(sidecar) is str for sidecar in value.sidecars)
        and type(value.integrity_ok) is bool
        and type(value.schema_complete) is bool
        and type(value.aggregate_row_count) is int
        and 0
        <= value.aggregate_row_count
        <= MAX_SQLITE_AGGREGATE_ROW_COUNT
        and type(value.rows_observed) is bool
        and not value.rows_observed
        and type(value.query_only) is bool
        and value.query_only
    )


def _valid_absent_sqlite(value: SqliteEvidence) -> bool:
    return (
        not value.present
        and value.database is None
        and value.size_bytes == 0
        and value.sidecars == ()
        and not value.integrity_ok
        and not value.schema_complete
        and value.aggregate_row_count == 0
    )


def _valid_present_sqlite(value: SqliteEvidence) -> bool:
    return (
        value.present
        and valid_object(value.database, kind=AuditObjectKind.FILE)
        and value.size_bytes > 0
        and value.sidecars == ()
        and value.integrity_ok
        and value.schema_complete
    )
