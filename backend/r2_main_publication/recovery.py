"""Read-only exact-topology classification for Issue #74 recovery."""

from __future__ import annotations

import os

from .observations import UNITS
from .windows_dacl import capture_tree

_PROBES = frozenset({"projection-directory", "projection-file.bin"})
_UNITS = frozenset(UNITS)


def classify_topology(state, original_anchor_identity: str) -> str:
    source = state.source.exists()
    legacy = state.legacy.exists()
    main = state.main.exists()
    if source and not legacy and not main:
        identity = capture_tree(state.source).items[0].observation.identity_fingerprint
        return "initial" if identity == original_anchor_identity else "unknown"
    if source or not legacy or state.failed_main.exists():
        return "unknown"
    legacy_names = _top_level_names(state.legacy)
    if not main:
        return "partial" if legacy_names == _UNITS else "unknown"
    main_names = _top_level_names(state.main)
    if not _valid_split(legacy_names, main_names):
        return "unknown"
    capture_tree(state.legacy)
    capture_tree(state.main)
    return "partial"


def _valid_split(legacy: frozenset[str], main: frozenset[str]) -> bool:
    main_units = main - _PROBES
    probes = main & _PROBES
    return (
        legacy <= _UNITS
        and main_units <= _UNITS
        and not (legacy & main_units)
        and legacy | main_units == _UNITS
        and probes in {frozenset(), _PROBES}
        and not (main - _UNITS - _PROBES)
    )


def _top_level_names(path) -> frozenset[str]:
    try:
        return frozenset(entry.name for entry in os.scandir(path))
    except OSError:
        raise ValueError("main_publication_scan_failed") from None
