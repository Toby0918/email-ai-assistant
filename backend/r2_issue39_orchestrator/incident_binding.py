"""Private path-bearing binding for the exact incident disposition."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True, repr=False)
class _ArtifactBinding:
    name: str = field(repr=False)
    length: int
    sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class _IncidentBinding:
    source: Path = field(repr=False)
    destination: Path = field(repr=False)
    artifacts: tuple[_ArtifactBinding, ...] = field(repr=False)
    source_dacl: str = field(repr=False)


_LEAF = (
    ".r2-solo-maintainer-closure-v1.incident-"
    "794aea72b0012d1de728f3b87f7f25c2f7c9ae3ac8f66777845010635fc69721"
)
_ARTIFACTS = (
    _ArtifactBinding(
        "solo-maintainer-attestation-receipt-v1.json",
        2023,
        "1449c090d8498f182432b231cc2489272426f4a22a6954e2b8486b6b56a370ab",
    ),
    _ArtifactBinding(
        "solo-maintainer-closure-manifest-v1.json",
        34827,
        "133537a1d29ba217a244178395862b629fb9cba91f864eb7654a2858f7b6ac4d",
    ),
)


def _fixed_incident_binding() -> _IncidentBinding:
    source = Path(r"D:\Projects\email_ai_assistant\.git") / _LEAF
    destination = (
        Path(r"D:\IncidentArchives\email_ai_assistant\issue38") / _LEAF
    )
    return _IncidentBinding(
        source,
        destination,
        _ARTIFACTS,
        "D:PAI(A;;0x1200a9;;;WD)",
    )
