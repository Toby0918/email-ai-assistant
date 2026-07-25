"""Pure validators for filesystem-zone ContainerAudit evidence."""

from __future__ import annotations

from .adapters import (
    AuditObject,
    AuditObjectKind,
    BoundedMetadataInventory,
    ConfigMetadata,
    ExternalPrivateState,
    FilesystemEvidence,
    MetadataEntry,
    MetadataRole,
    OperatorPrivateState,
    TopLevelEntry,
)
from .policy import (
    ALLOWED_CONFIG_KEYS,
    AUDIT_SCHEMA_VERSION,
    MAX_ARTIFACT_METADATA_ENTRIES,
    MAX_CONFIG_BYTES,
    MAX_CONFIG_KEYS,
    MAX_LOG_METADATA_ENTRIES,
    MAX_SQLITE_SIZE_BYTES,
    NORMAL_CONFIG_FILENAME,
    TOP_LEVEL_NAMES,
    is_opaque_fingerprint,
)


def valid_object(
    value: object,
    *,
    kind: AuditObjectKind,
) -> bool:
    return (
        type(value) is AuditObject
        and type(value.kind) is AuditObjectKind
        and value.kind is kind
        and is_opaque_fingerprint(value.identity)
        and is_opaque_fingerprint(value.volume_identity)
        and type(value.readable) is bool
        and value.readable
        and type(value.canonical) is bool
        and value.canonical
        and type(value.has_reparse_component) is bool
        and not value.has_reparse_component
    )


def _valid_metadata_entry(value: object) -> bool:
    return (
        type(value) is MetadataEntry
        and type(value.size_bytes) is int
        and 0 <= value.size_bytes <= MAX_SQLITE_SIZE_BYTES
        and type(value.role) is MetadataRole
        and type(value.object) is AuditObject
        and value.object.kind
        in (AuditObjectKind.DIRECTORY, AuditObjectKind.FILE)
        and valid_object(value.object, kind=value.object.kind)
    )


def valid_bounded_inventory(
    value: object,
    *,
    root: AuditObject | None,
    maximum_entries: int,
    allowed_roles: frozenset[MetadataRole],
    files_only: bool,
) -> bool:
    return (
        type(value) is BoundedMetadataInventory
        and root is not None
        and is_opaque_fingerprint(value.root_identity)
        and value.root_identity == root.identity
        and type(value.entries) is tuple
        and len(value.entries) <= maximum_entries
        and all(_valid_metadata_entry(entry) for entry in value.entries)
        and all(entry.role in allowed_roles for entry in value.entries)
        and (
            not files_only
            or all(
                entry.object.kind is AuditObjectKind.FILE
                for entry in value.entries
            )
        )
        and len({entry.object.identity for entry in value.entries})
        == len(value.entries)
        and type(value.inventory_complete) is bool
        and value.inventory_complete
        and type(value.direct_only) is bool
        and value.direct_only
        and type(value.content_observed) is bool
        and not value.content_observed
    )


def valid_config(
    value: object,
    *,
    root: AuditObject | None,
) -> bool:
    if type(value) is not ConfigMetadata:
        return False
    if not _valid_config_common(value, root=root):
        return False
    if not value.present:
        return (
            value.settings_file is None
            and value.size_bytes == 0
            and value.keys == ()
        )
    return valid_object(
        value.settings_file,
        kind=AuditObjectKind.FILE,
    )


def _valid_config_common(
    value: ConfigMetadata,
    *,
    root: AuditObject | None,
) -> bool:
    return (
        root is not None
        and is_opaque_fingerprint(value.directory_identity)
        and value.directory_identity == root.identity
        and type(value.filename) is str
        and value.filename == NORMAL_CONFIG_FILENAME
        and type(value.present) is bool
        and type(value.size_bytes) is int
        and 0 <= value.size_bytes <= MAX_CONFIG_BYTES
        and type(value.keys) is tuple
        and len(value.keys) <= MAX_CONFIG_KEYS
        and all(type(key) is str for key in value.keys)
        and len(set(value.keys)) == len(value.keys)
        and set(value.keys) <= ALLOWED_CONFIG_KEYS
        and type(value.inventory_complete) is bool
        and value.inventory_complete
        and type(value.direct_only) is bool
        and value.direct_only
        and type(value.values_observed) is bool
        and not value.values_observed
    )


def valid_filesystem(value: object) -> bool:
    if type(value) is not FilesystemEvidence:
        return False
    if not _valid_filesystem_header(value):
        return False
    entries = value.entries
    if not _valid_top_level_inventory(entries):
        return False
    identities = {
        value.container.identity,
        *(entry.object.identity for entry in entries),
    }
    return (
        len(identities) == len(entries) + 1
        and valid_config(
            value.config,
            root=entry_object(value, "Config"),
        )
        and valid_bounded_inventory(
            value.logs,
            root=entry_object(value, "Logs"),
            maximum_entries=MAX_LOG_METADATA_ENTRIES,
            allowed_roles=frozenset(
                {
                    MetadataRole.CURRENT_LOG,
                    MetadataRole.ROTATED_LOG,
                    MetadataRole.PID,
                }
            ),
            files_only=True,
        )
        and _valid_log_role_counts(value.logs)
        and valid_bounded_inventory(
            value.artifacts,
            root=entry_object(value, "Artifacts"),
            maximum_entries=MAX_ARTIFACT_METADATA_ENTRIES,
            allowed_roles=frozenset({MetadataRole.ARTIFACT}),
            files_only=False,
        )
    )


def _valid_filesystem_header(value: FilesystemEvidence) -> bool:
    return (
        type(value.schema_version) is int
        and value.schema_version == AUDIT_SCHEMA_VERSION
        and valid_object(value.container, kind=AuditObjectKind.DIRECTORY)
        and type(value.inventory_complete) is bool
        and value.inventory_complete
        and type(value.operator_private_state) is OperatorPrivateState
        and value.operator_private_state is OperatorPrivateState.DISABLED
        and type(value.operator_private_content_observed) is bool
        and not value.operator_private_content_observed
        and type(value.raw_vault_state) is ExternalPrivateState
        and value.raw_vault_state is ExternalPrivateState.NOT_PROVISIONED
        and type(value.recovery_state) is ExternalPrivateState
        and value.recovery_state is ExternalPrivateState.NOT_PROVISIONED
    )


def _valid_top_level_inventory(value: object) -> bool:
    return (
        type(value) is tuple
        and len(value) == len(TOP_LEVEL_NAMES)
        and all(_valid_top_level_entry(entry) for entry in value)
        and {entry.name for entry in value} == TOP_LEVEL_NAMES
    )


def _valid_top_level_entry(value: object) -> bool:
    return (
        type(value) is TopLevelEntry
        and type(value.name) is str
        and valid_object(value.object, kind=AuditObjectKind.DIRECTORY)
        and type(value.direct_child_of_container) is bool
        and value.direct_child_of_container
    )


def _valid_log_role_counts(value: BoundedMetadataInventory) -> bool:
    roles = tuple(entry.role for entry in value.entries)
    return (
        roles.count(MetadataRole.CURRENT_LOG) <= 1
        and roles.count(MetadataRole.ROTATED_LOG) <= 2
        and roles.count(MetadataRole.PID) <= 1
    )


def entry_object(
    filesystem: FilesystemEvidence,
    name: str,
) -> AuditObject | None:
    matches = tuple(
        entry.object for entry in filesystem.entries if entry.name == name
    )
    return matches[0] if len(matches) == 1 else None
