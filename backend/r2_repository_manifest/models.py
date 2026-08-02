"""Private path-bearing state for the Issue #75 synthetic transaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True, repr=False)
class ManifestTransactionState:
    scope: object = field(repr=False)
    policy: object = field(repr=False)
    manifest: object = field(repr=False)
    baseline: object = field(repr=False)
    root: Path = field(repr=False)
    marker: Path = field(repr=False)
    marker_identity: str = field(repr=False)
    container: Path = field(repr=False)
    legacy: Path = field(repr=False)
    failed_container: Path = field(repr=False)
    main: Path = field(repr=False)
    profile: object = field(repr=False)
    authorization: object = field(repr=False)
    observed_at_epoch: int = field(repr=False)
    acl_adapter: object = field(repr=False)
    projection: object | None = field(default=None, repr=False)
    recreated: list[object] = field(default_factory=list, repr=False)
