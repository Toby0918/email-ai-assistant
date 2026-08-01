"""Exact forward/reverse topology proofs for the Issue #75 slice."""

from __future__ import annotations

from pathlib import Path

from backend.cutover_repository_transaction.git_recreation import (
    observe_all_recreated,
)
from backend.cutover_repository_transaction.windows_identity import (
    directory_identity,
    file_identity,
    opaque_directory_fingerprint,
)

from .canonical import fingerprint


def manifest_exact(state) -> bool:
    if not state.main.is_dir() or not state.legacy.is_dir():
        return False
    for item in state.manifest.moves:
        source = state.legacy / item.relative
        target = state.main / item.relative
        if source.exists() or _identity(target, item.directory) != item.identity_fingerprint:
            return False
    return all((state.main / relative).is_dir() for relative in state.manifest.skeletons)


def residue_exact(state) -> bool:
    for item in state.manifest.residue:
        source = state.legacy / item.relative
        target = state.main / item.relative
        if target.exists() or file_identity(source) != item.identity_fingerprint:
            return False
    return True


def originals_retained(state) -> bool:
    scenario = state.scope.review.scenario
    for item in state.scope.review.observations:
        physical = Path(scenario.worktree_preservation) / item.paths.role
        admin = Path(scenario.admin_preservation) / item.paths.role
        if (
            directory_identity(physical) != item.physical_identity
            or directory_identity(admin) != item.admin_identity
            or opaque_directory_fingerprint(admin) != item.admin_content
        ):
            return False
    return True


def verify_forward(state) -> tuple[object, ...]:
    if (
        not manifest_exact(state)
        or not residue_exact(state)
        or not originals_retained(state)
        or directory_identity(state.main / ".git")
        != state.scope.review.common_object_identity
    ):
        raise ValueError("repository_manifest_forward_invalid")
    recreated = observe_all_recreated(state.scope, state.main)
    if len(recreated) != 11 or any(
        state.main == item.physical or state.main in item.physical.parents
        for item in recreated
    ):
        raise ValueError("repository_manifest_forward_invalid")
    return recreated


def current_original_identities(state) -> tuple[str, ...]:
    scenario = state.scope.review.scenario
    return (
        directory_identity(Path(scenario.source)),
        *(directory_identity(item.paths.original) for item in state.scope.review.observations),
        *(directory_identity(item.admin) for item in state.scope.review.observations),
    )


def expected_original_identities(state) -> tuple[str, ...]:
    return (
        state.scope.review.repository_object_identity,
        *(item.physical_identity for item in state.scope.review.observations),
        *(item.admin_identity for item in state.scope.review.observations),
    )


def verify_reverse(state) -> None:
    if current_original_identities(state) != expected_original_identities(state):
        raise ValueError("repository_manifest_reverse_invalid")
    if directory_identity(state.container / ".git") != state.scope.review.common_object_identity:
        raise ValueError("repository_manifest_reverse_invalid")
    for item in state.scope.review.observations:
        if opaque_directory_fingerprint(item.admin) != item.admin_content:
            raise ValueError("repository_manifest_reverse_invalid")


def topology_fingerprint(state) -> str:
    values = []
    for path in (
        state.container,
        state.legacy,
        state.failed_container,
        state.main,
    ):
        if path.is_dir():
            values.append((path.name, directory_identity(path)))
        else:
            values.append((path.name, "absent"))
    values.extend(
        (
            item.paths.role,
            "target" if item.paths.target.is_dir() else "absent",
            "original" if item.paths.original.is_dir() else "absent",
            "preserved" if item.paths.preservation.is_dir() else "absent",
        )
        for item in state.scope.review.observations
    )
    return fingerprint("repository-manifest-topology-v1", values)


def _identity(path: Path, directory: bool) -> str:
    return directory_identity(path) if directory else file_identity(path)
