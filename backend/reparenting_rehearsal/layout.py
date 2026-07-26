"""The only Issue #36 bridge to repository-placement validation."""

from pathlib import Path

from backend.project_layout import RepositoryPlacement

from .errors import RehearsalError


def require_managed_synthetic_layout(
    *,
    container: Path,
    main: Path,
    legacy: Path,
) -> None:
    try:
        placement = RepositoryPlacement.managed(
            repository_root=main,
            project_container=container,
        )
    except Exception:
        raise RehearsalError() from None
    if (
        placement.repository_root != main
        or placement.project_container != container
        or legacy.parent != container.parent
        or legacy == container
        or legacy in container.parents
        or container in legacy.parents
    ):
        raise RehearsalError()
