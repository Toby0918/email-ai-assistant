"""One complete, ordered seven-reader topology observation."""

from __future__ import annotations

from .callbacks import CurrentTopologyCallbacks
from .contracts import HostObjectObservationV1, MissingHostObjectObservationV1
from .evidence import (
    HostCheckKind,
    OpaqueHostCheckV1,
    VolumeObservationV1,
)
from .topology_evidence import CurrentTopologyObservationV1


def collect_current_topology(
    callbacks: CurrentTopologyCallbacks,
) -> CurrentTopologyObservationV1:
    try:
        source = callbacks.source_root()
        parent = callbacks.target_parent()
        finance = callbacks.finance_root()
        absence = callbacks.target_absence()
        git = callbacks.git()
        acl = callbacks.acl()
        volume = callbacks.volume()
        _require_component_types(
            source, parent, finance, absence, git, acl, volume
        )
        return CurrentTopologyObservationV1.create(
            source_root=source,
            target_parent=parent,
            finance_root=finance,
            target_absence=absence,
            git_fingerprint=git.fingerprint,
            acl_fingerprint=acl.fingerprint,
            volume_fingerprint=volume.volume_fingerprint,
            complete=True,
            content_observed=False,
            controlled_components_reparse_free=True,
        )
    except Exception:
        raise ValueError("REAL_HOST_TOPOLOGY_REJECTED") from None


def _require_component_types(
    source: object,
    parent: object,
    finance: object,
    absence: object,
    git: object,
    acl: object,
    volume: object,
) -> None:
    if (
        type(source) is not HostObjectObservationV1
        or type(parent) is not HostObjectObservationV1
        or type(finance) is not HostObjectObservationV1
        or type(absence) is not MissingHostObjectObservationV1
        or type(git) is not OpaqueHostCheckV1
        or git.kind is not HostCheckKind.GIT
        or type(acl) is not OpaqueHostCheckV1
        or acl.kind is not HostCheckKind.ACL
        or type(volume) is not VolumeObservationV1
    ):
        raise ValueError("REAL_HOST_TOPOLOGY_REJECTED")
