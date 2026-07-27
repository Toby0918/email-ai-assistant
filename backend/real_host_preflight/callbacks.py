"""Exact zero-argument callbacks for one complete topology pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .contracts import (
    HostObjectObservationV1,
    MissingHostObjectObservationV1,
)
from .evidence import OpaqueHostCheckV1, VolumeObservationV1


ObjectReader = Callable[[], HostObjectObservationV1]
AbsenceReader = Callable[[], MissingHostObjectObservationV1]
CheckReader = Callable[[], OpaqueHostCheckV1]
VolumeReader = Callable[[], VolumeObservationV1]


@dataclass(frozen=True, slots=True, repr=False)
class CurrentTopologyCallbacks:
    """The seven fixed-role read-only readers in one complete pass."""

    source_root: ObjectReader
    target_parent: ObjectReader
    finance_root: ObjectReader
    target_absence: AbsenceReader
    git: CheckReader
    acl: CheckReader
    volume: VolumeReader
