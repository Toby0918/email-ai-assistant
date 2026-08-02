"""Validated test-only assembly for the fixed Issue #74 tracer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_host_mutation.roles import AclRole
from backend.cutover_host_mutation.windows_security import WindowsSecurityApi

from .trace import SyntheticMainPublicationTrace


@dataclass(frozen=True, slots=True, repr=False)
class _TraceState:
    root: Path = field(repr=False)
    marker: Path = field(repr=False)
    source: Path = field(repr=False)
    legacy: Path = field(repr=False)
    container: Path = field(repr=False)
    main: Path = field(repr=False)
    failed_main: Path = field(repr=False)
    journal: Path = field(repr=False)
    profile: CutoverProfileV1 = field(repr=False)
    authorization: TestSandboxAuthorizationV1 = field(repr=False)
    observed_at_epoch: int = field(repr=False)
    marker_identity: str = field(repr=False)
    clock: object = field(repr=False)


def bind_test_main_publication(
    scenario: object,
    *,
    observed_at_epoch: int,
    _clock: object | None = None,
) -> SyntheticMainPublicationTrace:
    values = _scenario_values(scenario)
    _validate(values, observed_at_epoch)
    marker = WindowsSecurityApi().capture(
        values["marker"], role=AclRole.SOURCE_TREE
    )
    state = _TraceState(
        **values,
        observed_at_epoch=observed_at_epoch,
        marker_identity=marker.observation.object_identity_fingerprint,
        clock=_clock or (lambda: observed_at_epoch),
    )
    return SyntheticMainPublicationTrace(state)


def _scenario_values(scenario: object) -> dict[str, object]:
    names = (
        "root",
        "marker",
        "source",
        "legacy",
        "container",
        "main",
        "failed_main",
        "journal",
        "profile",
        "authorization",
    )
    try:
        return {name: getattr(scenario, name) for name in names}
    except Exception:
        raise ValueError("main_publication_scope_invalid") from None


def _validate(values: dict[str, object], observed_at: object) -> None:
    root = values["root"]
    paths = tuple(values[name] for name in _PATH_NAMES)
    if (
        type(root) is not type(Path())
        or any(type(path) is not type(Path()) for path in paths)
        or type(values["profile"]) is not CutoverProfileV1
        or type(values["authorization"]) is not TestSandboxAuthorizationV1
        or type(observed_at) is not int
        or values["authorization"].phase != "execute"
        or values["authorization"].profile_fingerprint
        != values["profile"].profile_fingerprint
        or values["authorization"].expires_at_epoch <= observed_at
    ):
        raise ValueError("main_publication_scope_invalid")
    _validate_paths(values)


def _validate_paths(values: dict[str, object]) -> None:
    root = values["root"]
    expected = {
        "marker": root / ".codex-cutover-mutation-test-sandbox",
        "source": root / "flat-root",
        "legacy": root / "LegacySourceAnchorV1",
        "container": root / "Container",
        "main": root / "Container" / "ManagedMainRootV1",
        "failed_main": root / "Container" / "FailedManagedMainRootV1",
        "journal": root / "main-publication.journal",
    }
    if any(values[name] != path for name, path in expected.items()):
        raise ValueError("main_publication_scope_invalid")
    if (
        not root.is_dir()
        or not values["marker"].is_file()
        or not values["source"].is_dir()
        or not values["container"].is_dir()
        or any(values[name].exists() for name in ("legacy", "main", "failed_main", "journal"))
    ):
        raise ValueError("main_publication_scope_invalid")


_PATH_NAMES = (
    "marker",
    "source",
    "legacy",
    "container",
    "main",
    "failed_main",
    "journal",
)
