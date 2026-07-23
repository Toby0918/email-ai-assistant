"""Temporary adapter for the current flat local-service layout."""

from __future__ import annotations

from pathlib import Path

from .errors import PlacementError
from .identity import (
    DirectoryInspector,
    inspect_local_directory,
    read_directory_identity,
)
from .operational import OperationalLayout


class FlatOperationalLayoutAdapter:
    """Resolve existing flat paths without adding a placement mode."""

    @staticmethod
    def resolve(
        repository_root: Path,
        *,
        inspect_directory: DirectoryInspector | None = None,
    ) -> OperationalLayout:
        source = Path(repository_root)
        inspector = inspect_directory or inspect_local_directory
        identity = read_directory_identity(source, inspector)
        if read_directory_identity(source, inspector) != identity:
            raise PlacementError("placement_identity_changed")
        repository = identity.canonical_path
        outputs = repository / "outputs"
        return OperationalLayout._create(
            runtime_root=repository / ".venv",
            data_root=outputs,
            temporary_root=outputs / "attachment_temp",
            log_root=outputs,
            artifact_root=outputs,
            worktree_root=repository / ".worktrees",
            configuration_root=repository,
        )
