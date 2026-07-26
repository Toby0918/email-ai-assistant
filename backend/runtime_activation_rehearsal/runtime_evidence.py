"""Content-free pinned runtime and rebuilt-venv evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeBuildRequest:
    """The code-fixed runtime and dependency lock."""

    python_version: str
    sqlite_version: str
    locked_dependencies: tuple[str, ...]
    lock_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeBuildEvidence:
    """Runtime creation and offline Windows venv rebuild evidence."""

    schema_version: int
    runtime_identity: str
    runtime_parent_identity: str
    venv_identity: str
    venv_parent_identity: str
    scripts_identity: str
    scripts_parent_identity: str
    executable_identity: str
    executable_parent_identity: str
    python_version: str
    sqlite_version: str
    locked_dependencies: tuple[str, ...]
    lock_sha256: str
    lock_identity_before: str
    lock_identity_after: str
    lock_sha256_before: str
    lock_sha256_after: str
    source_identity_before: str
    source_identity_after: str
    legacy_venv_identity_before: str
    legacy_venv_identity_after: str
    runtime_created: bool
    venv_rebuilt: bool
    create_only: bool
    source_preserved: bool
    legacy_preserved: bool
    legacy_observed: bool
    legacy_moved: bool
    network_used: bool
    has_reparse_component: bool


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeProbeEvidence:
    """Independent pinned-version and dependency observation."""

    schema_version: int
    runtime_identity: str
    venv_identity: str
    scripts_identity: str
    executable_identity: str
    python_version: str
    sqlite_version: str
    locked_dependencies: tuple[str, ...]
    lock_sha256: str
    has_reparse_component: bool
