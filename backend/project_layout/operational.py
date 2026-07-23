"""Ordinary operational locations derived from validated placement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import PlacementError
from .placement import RepositoryPlacement


@dataclass(frozen=True, slots=True, init=False)
class OperationalLayout:
    """Absolute ordinary locations with no reader or external capability."""

    runtime_root: Path
    data_root: Path
    temporary_root: Path
    log_root: Path
    artifact_root: Path
    worktree_root: Path
    configuration_root: Path

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise PlacementError("operational_layout_invalid")

    @classmethod
    def _create(
        cls,
        *,
        runtime_root: Path,
        data_root: Path,
        temporary_root: Path,
        log_root: Path,
        artifact_root: Path,
        worktree_root: Path,
        configuration_root: Path,
    ) -> OperationalLayout:
        locations = (
            runtime_root,
            data_root,
            temporary_root,
            log_root,
            artifact_root,
            worktree_root,
            configuration_root,
        )
        if any(
            not isinstance(location, Path) or not location.is_absolute()
            for location in locations
        ):
            raise PlacementError("operational_layout_invalid")
        layout = object.__new__(cls)
        for name, location in zip(cls.__slots__, locations, strict=True):
            object.__setattr__(layout, name, location)
        return layout

    @classmethod
    def for_placement(cls, placement: RepositoryPlacement) -> OperationalLayout:
        if not isinstance(placement, RepositoryPlacement):
            raise PlacementError("operational_layout_invalid")
        root = placement.project_container or placement.standalone_state_root
        if root is None:
            raise PlacementError("operational_layout_invalid")
        return cls._create(
            runtime_root=root / "Runtimes",
            data_root=root / "LocalData",
            temporary_root=root / "RuntimeTemp",
            log_root=root / "Logs",
            artifact_root=root / "Artifacts",
            worktree_root=root / "Worktrees",
            configuration_root=root / "Config",
        )
