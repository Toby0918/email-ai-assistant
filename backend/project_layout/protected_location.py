"""Trusted protected-root policy derived from repository placement evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import PlacementError
from .identity import (
    DirectoryInspector,
    inspect_local_directory,
    read_directory_identity,
)
from .placement import RepositoryPlacement


_MANAGED_ZONE_NAMES = frozenset(
    {
        "main",
        "Runtimes",
        "LocalData",
        "RuntimeTemp",
        "Logs",
        "Artifacts",
        "Worktrees",
        "Config",
        "OperatorPrivate",
    }
)


@dataclass(frozen=True, slots=True, init=False)
class ProtectedLocationPolicy:
    """Immutable protected roots with no caller-supplied narrowing seam."""

    repository_root: Path
    protected_roots: tuple[Path, ...]

    @classmethod
    def _create(
        cls,
        repository_root: Path,
        protected_roots: tuple[Path, ...],
    ) -> ProtectedLocationPolicy:
        policy = object.__new__(cls)
        object.__setattr__(policy, "repository_root", repository_root)
        object.__setattr__(policy, "protected_roots", protected_roots)
        return policy

    @classmethod
    def for_placement(
        cls,
        placement: RepositoryPlacement,
        *,
        inspect_directory: DirectoryInspector | None = None,
    ) -> ProtectedLocationPolicy:
        """Revalidate an approved Managed or Standalone placement."""

        if type(placement) is not RepositoryPlacement:
            raise PlacementError("placement_identity_unavailable")
        if placement.project_container is not None:
            if (
                placement.standalone_state_root is not None
                or placement.standalone_state_kind is not None
            ):
                raise PlacementError("placement_identity_unavailable")
            refreshed = RepositoryPlacement.managed(
                repository_root=placement.repository_root,
                project_container=placement.project_container,
                inspect_directory=inspect_directory,
            )
        else:
            if (
                placement.standalone_state_root is None
                or placement.standalone_state_kind is None
            ):
                raise PlacementError("placement_identity_unavailable")
            refreshed = RepositoryPlacement.standalone(
                repository_root=placement.repository_root,
                state_root=placement.standalone_state_root,
                state_kind=placement.standalone_state_kind,
                inspect_directory=inspect_directory,
            )
        if refreshed != placement:
            raise PlacementError("placement_identity_changed")
        return cls._create(
            refreshed.repository_root,
            refreshed.protected_roots,
        )

    @classmethod
    def for_context(
        cls,
        context: Path | RepositoryPlacement,
        *,
        inspect_directory: DirectoryInspector | None = None,
    ) -> ProtectedLocationPolicy:
        """Revalidate an explicit placement or the repository compatibility."""

        if type(context) is RepositoryPlacement:
            return cls.for_placement(
                context,
                inspect_directory=inspect_directory,
            )
        return cls.for_repository(
            Path(context),
            inspect_directory=inspect_directory,
        )

    @classmethod
    def for_repository(
        cls,
        repository_root: Path,
        *,
        inspect_directory: DirectoryInspector | None = None,
    ) -> ProtectedLocationPolicy:
        """Resolve Managed placement or the bounded flat-layout compatibility."""

        source = Path(repository_root)
        looks_like_main = source.name == "main"
        looks_like_container_child = source.parent.name == "email_ai_assistant"
        if looks_like_main or looks_like_container_child:
            if not (looks_like_main and looks_like_container_child):
                raise PlacementError("managed_relationship_invalid")
            placement = RepositoryPlacement.managed(
                repository_root=source,
                project_container=source.parent,
                inspect_directory=inspect_directory,
            )
            return cls._create(
                placement.repository_root,
                placement.protected_roots,
            )
        if _inside_managed_zone(source):
            raise PlacementError("managed_relationship_invalid")

        inspector = inspect_directory or inspect_local_directory
        identity = read_directory_identity(source, inspector)
        identity_after = read_directory_identity(source, inspector)
        if identity_after != identity:
            raise PlacementError("placement_identity_changed")
        return cls._create(
            identity.canonical_path,
            (identity.canonical_path,),
        )

    def contains(
        self,
        *,
        original_path: Path,
        resolved_path: Path,
    ) -> bool:
        """Return whether either reviewed path view is protected."""

        original = _validated_path_view(original_path)
        resolved = _validated_path_view(resolved_path)
        return any(
            _contains(root, original) or _contains(root, resolved)
            for root in self.protected_roots
        )


def _validated_path_view(value: Path) -> Path:
    try:
        path = Path(value)
    except Exception:
        raise PlacementError("placement_alias_invalid") from None
    if not path.is_absolute() or ".." in path.parts:
        raise PlacementError("placement_alias_invalid")
    return path


def _contains(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _inside_managed_zone(path: Path) -> bool:
    for ancestor in path.parents:
        if ancestor.name != "email_ai_assistant":
            continue
        try:
            relative = path.relative_to(ancestor)
        except ValueError:
            continue
        return bool(relative.parts) and relative.parts[0] in _MANAGED_ZONE_NAMES
    return False
