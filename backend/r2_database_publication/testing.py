"""Validated physical-sandbox binders for Issue #76 tests."""

from __future__ import annotations

from pathlib import Path

from .contracts import QuiescencePrerequisitesV1
from .service import LegacyServiceControllerRole, _bind_test_controller
from .transaction import SyntheticDatabasePublicationTransaction


def bind_test_legacy_service_controller(state: Path) -> LegacyServiceControllerRole:
    return _bind_test_controller(Path(state))


def bind_test_database_transaction(
    *,
    source: Path,
    staging: Path,
    target: Path,
    journal: Path,
    prerequisites: object,
    service_controller: object,
) -> SyntheticDatabasePublicationTransaction:
    paths = tuple(map(Path, (source, staging, target, journal)))
    if (
        type(prerequisites) is not QuiescencePrerequisitesV1
        or type(service_controller) is not LegacyServiceControllerRole
        or not paths[0].is_file()
        or paths[1].exists()
        or paths[2].exists()
        or paths[3].exists()
        or paths[1].parent != paths[2].parent
        or len({path.parent.resolve() for path in paths}) != 2
    ):
        raise ValueError("database_test_scope_invalid")
    return SyntheticDatabasePublicationTransaction(
        source=paths[0],
        staging=paths[1],
        target=paths[2],
        journal=paths[3],
        prerequisites=prerequisites,
        controller=service_controller,
    )
