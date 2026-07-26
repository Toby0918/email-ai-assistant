"""Pure runtime and locked-dependency validation."""

from __future__ import annotations

import re

from .adapters import (
    ManagedLayoutEvidence,
    RuntimeBuildEvidence,
    RuntimeProbeEvidence,
)
from .filesystem_checks import zone_identity
from .policy import (
    LOCKED_DEPENDENCIES,
    LOCK_SHA256,
    ManagedZone,
    PINNED_PYTHON_VERSION,
    PINNED_SQLITE_VERSION,
)

_SHA256 = re.compile(r"[0-9a-f]{64}", re.ASCII)


def valid_runtime_build(
    value: object,
    layout: ManagedLayoutEvidence,
) -> bool:
    """Require create-only offline rebuild evidence."""
    if type(value) is not RuntimeBuildEvidence:
        return False
    return (
        type(value.schema_version) is int
        and value.schema_version == 1
        and _valid_runtime_identity_graph(value, layout)
        and _valid_runtime_lock(value)
        and _valid_runtime_flags(value)
    )


def _valid_runtime_identity_graph(
    value: RuntimeBuildEvidence,
    layout: ManagedLayoutEvidence,
) -> bool:
    identities = (
        value.runtime_identity,
        value.runtime_parent_identity,
        value.venv_identity,
        value.venv_parent_identity,
        value.scripts_identity,
        value.scripts_parent_identity,
        value.executable_identity,
        value.executable_parent_identity,
        value.lock_identity_before,
        value.lock_identity_after,
        value.source_identity_before,
        value.source_identity_after,
        value.legacy_venv_identity_before,
        value.legacy_venv_identity_after,
    )
    distinct_identities = (
        value.runtime_identity,
        value.venv_identity,
        value.scripts_identity,
        value.executable_identity,
        value.lock_identity_before,
        value.source_identity_before,
        value.legacy_venv_identity_before,
    )
    return (
        all(_identity(item) for item in identities)
        and len(set(distinct_identities)) == len(distinct_identities)
        and value.runtime_parent_identity
        == zone_identity(layout, ManagedZone.RUNTIMES)
        and value.venv_parent_identity
        == zone_identity(layout, ManagedZone.RUNTIMES)
        and value.scripts_parent_identity == value.venv_identity
        and value.executable_parent_identity == value.scripts_identity
    )


def _valid_runtime_lock(value: RuntimeBuildEvidence) -> bool:
    return (
        _valid_pins(
            value.python_version,
            value.sqlite_version,
            value.locked_dependencies,
            value.lock_sha256,
        )
        and _digest(value.lock_sha256_before)
        and _digest(value.lock_sha256_after)
        and value.lock_identity_after == value.lock_identity_before
        and value.lock_sha256_before == LOCK_SHA256
        and value.lock_sha256_after == value.lock_sha256_before
        and value.source_identity_after == value.source_identity_before
        and value.legacy_venv_identity_after
        == value.legacy_venv_identity_before
    )


def _valid_runtime_flags(value: RuntimeBuildEvidence) -> bool:
    return (
        value.runtime_created is True
        and value.venv_rebuilt is True
        and value.create_only is True
        and value.source_preserved is True
        and value.legacy_preserved is True
        and value.legacy_observed is False
        and value.legacy_moved is False
        and value.network_used is False
        and value.has_reparse_component is False
    )


def stable_runtime(
    build: object,
    observed: object,
    probe: object,
    layout: ManagedLayoutEvidence,
) -> bool:
    """Cross-check the creator, second observation and independent probe."""
    if (
        not valid_runtime_build(build, layout)
        or not valid_runtime_build(observed, layout)
        or observed != build
        or not _valid_runtime_probe(probe)
    ):
        return False
    return (
        probe.runtime_identity == build.runtime_identity
        and probe.venv_identity == build.venv_identity
        and probe.scripts_identity == build.scripts_identity
        and probe.executable_identity == build.executable_identity
    )


def _valid_runtime_probe(value: object) -> bool:
    if type(value) is not RuntimeProbeEvidence:
        return False
    return (
        type(value.schema_version) is int
        and value.schema_version == 1
        and _identity(value.runtime_identity)
        and _identity(value.venv_identity)
        and _identity(value.scripts_identity)
        and _identity(value.executable_identity)
        and _valid_pins(
            value.python_version,
            value.sqlite_version,
            value.locked_dependencies,
            value.lock_sha256,
        )
        and value.has_reparse_component is False
    )


def _valid_pins(
    python_version: object,
    sqlite_version: object,
    locked_dependencies: object,
    lock_sha256: object,
) -> bool:
    return (
        type(python_version) is str
        and python_version == PINNED_PYTHON_VERSION
        and type(sqlite_version) is str
        and sqlite_version == PINNED_SQLITE_VERSION
        and type(locked_dependencies) is tuple
        and all(type(item) is str for item in locked_dependencies)
        and locked_dependencies == LOCKED_DEPENDENCIES
        and _digest(lock_sha256)
        and lock_sha256 == LOCK_SHA256
    )


def _digest(value: object) -> bool:
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _identity(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 128
        and value.strip() == value
    )
