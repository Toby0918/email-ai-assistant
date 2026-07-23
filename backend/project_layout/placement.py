"""Validated Repository Root and optional Project Container placement."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .errors import PlacementError
from .identity import (
    DirectoryInspector,
    inspect_local_directory,
    read_directory_identity,
)


class StandaloneStateKind(str, Enum):
    """Explicit non-managed state classifications."""

    SYNTHETIC = "synthetic"
    TEMPORARY = "temporary"


@dataclass(frozen=True, slots=True, init=False)
class RepositoryPlacement:
    """Immutable repository placement without filesystem capabilities."""

    repository_root: Path
    project_container: Path | None
    standalone_state_root: Path | None
    standalone_state_kind: StandaloneStateKind | None
    protected_roots: tuple[Path, ...]

    @classmethod
    def _create(
        cls,
        *,
        repository_root: Path,
        project_container: Path | None,
        standalone_state_root: Path | None,
        standalone_state_kind: StandaloneStateKind | None,
        protected_roots: tuple[Path, ...],
    ) -> RepositoryPlacement:
        placement = object.__new__(cls)
        object.__setattr__(placement, "repository_root", repository_root)
        object.__setattr__(placement, "project_container", project_container)
        object.__setattr__(
            placement,
            "standalone_state_root",
            standalone_state_root,
        )
        object.__setattr__(
            placement,
            "standalone_state_kind",
            standalone_state_kind,
        )
        object.__setattr__(placement, "protected_roots", protected_roots)
        return placement

    @classmethod
    def managed(
        cls,
        *,
        repository_root: Path,
        project_container: Path,
        inspect_directory: DirectoryInspector | None = None,
    ) -> RepositoryPlacement:
        inspector = inspect_directory or inspect_local_directory
        repository_source = Path(repository_root)
        container_source = Path(project_container)
        repository_identity = read_directory_identity(
            repository_source, inspector
        )
        container_identity = read_directory_identity(
            container_source, inspector
        )
        repository = repository_identity.canonical_path
        container = container_identity.canonical_path
        if (
            repository.name != "main"
            or container.name != "email_ai_assistant"
            or repository.parent != container
        ):
            raise PlacementError("managed_relationship_invalid")
        repository_after = read_directory_identity(
            repository_source, inspector
        )
        container_after = read_directory_identity(container_source, inspector)
        if (
            repository_after != repository_identity
            or container_after != container_identity
        ):
            raise PlacementError("placement_identity_changed")
        return cls._create(
            repository_root=repository,
            project_container=container,
            standalone_state_root=None,
            standalone_state_kind=None,
            protected_roots=(container,),
        )

    @classmethod
    def standalone(
        cls,
        *,
        repository_root: Path,
        state_root: Path,
        state_kind: StandaloneStateKind,
        inspect_directory: DirectoryInspector | None = None,
    ) -> RepositoryPlacement:
        if not isinstance(state_kind, StandaloneStateKind):
            raise PlacementError("standalone_state_root_invalid")
        inspector = inspect_directory or inspect_local_directory
        repository_source = Path(repository_root)
        state_source = Path(state_root)
        repository_identity = read_directory_identity(
            repository_source, inspector
        )
        state_identity = read_directory_identity(state_source, inspector)
        repository = repository_identity.canonical_path
        state = state_identity.canonical_path
        if (
            repository == state
            or repository in state.parents
            or state in repository.parents
        ):
            raise PlacementError("standalone_state_root_invalid")
        repository_after = read_directory_identity(
            repository_source, inspector
        )
        state_after = read_directory_identity(state_source, inspector)
        if (
            repository_after != repository_identity
            or state_after != state_identity
        ):
            raise PlacementError("placement_identity_changed")
        return cls._create(
            repository_root=repository,
            project_container=None,
            standalone_state_root=state,
            standalone_state_kind=state_kind,
            protected_roots=(repository, state),
        )
