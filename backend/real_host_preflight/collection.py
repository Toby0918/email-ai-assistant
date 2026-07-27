"""One complete, ordered seven-reader topology observation."""

from __future__ import annotations

from .callbacks import CurrentTopologyCallbacks
from .canonical import role_selections_match
from .contracts import HostObjectObservationV1, MissingHostObjectObservationV1
from .contracts_bridge import CutoverProfileV1
from .evidence import (
    HostCheckKind,
    OpaqueHostCheckV1,
    VolumeObservationV1,
)
from .integrity import (
    valid_host_object,
    valid_missing_host_object,
    valid_opaque_check,
    valid_volume,
)
from .topology_evidence import CurrentTopologyObservationV1


def collect_current_topology(
    callbacks: CurrentTopologyCallbacks,
    *,
    profile: CutoverProfileV1,
) -> CurrentTopologyObservationV1:
    try:
        if type(profile) is not CutoverProfileV1:
            raise ValueError("REAL_HOST_TOPOLOGY_REJECTED")
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
        _require_role_bindings(profile, source, parent, finance, absence)
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
        not valid_host_object(source)
        or not valid_host_object(parent)
        or not valid_host_object(finance)
        or not valid_missing_host_object(absence)
        or not valid_opaque_check(git)
        or git.kind is not HostCheckKind.GIT
        or not valid_opaque_check(acl)
        or acl.kind is not HostCheckKind.ACL
        or not valid_volume(volume)
    ):
        raise ValueError("REAL_HOST_TOPOLOGY_REJECTED")


def _require_role_bindings(
    profile: CutoverProfileV1,
    source: HostObjectObservationV1,
    parent: HostObjectObservationV1,
    finance: HostObjectObservationV1,
    absence: MissingHostObjectObservationV1,
) -> None:
    names = {
        "source_root": source.normalized_name_fingerprint,
        "target_parent": parent.normalized_name_fingerprint,
        "finance_root": finance.normalized_name_fingerprint,
        "target_absence": absence.normalized_name_fingerprint,
    }
    if not role_selections_match(profile.to_mapping(), names):
        raise ValueError("REAL_HOST_TOPOLOGY_REJECTED")
