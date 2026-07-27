"""Aggregate portable evidence for one current-topology pass."""

from __future__ import annotations

from dataclasses import dataclass

from .canonical import fingerprint, is_fingerprint
from .contracts import (
    HostObjectKind,
    HostObjectObservationV1,
    MissingHostObjectObservationV1,
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class CurrentTopologyObservationV1:
    schema_version: int
    source_root: HostObjectObservationV1
    finance_root: HostObjectObservationV1
    target_parent: HostObjectObservationV1
    target_absence: MissingHostObjectObservationV1
    git_fingerprint: str
    acl_fingerprint: str
    volume_fingerprint: str
    complete: bool
    content_observed: bool
    controlled_components_reparse_free: bool
    observation_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated topology observation construction required")

    @classmethod
    def create(
        cls,
        *,
        source_root: HostObjectObservationV1,
        finance_root: HostObjectObservationV1,
        target_parent: HostObjectObservationV1,
        target_absence: MissingHostObjectObservationV1,
        git_fingerprint: str,
        acl_fingerprint: str,
        volume_fingerprint: str,
        complete: bool,
        content_observed: bool,
        controlled_components_reparse_free: bool,
    ) -> CurrentTopologyObservationV1:
        _require_relationships(
            source_root,
            finance_root,
            target_parent,
            target_absence,
            volume_fingerprint,
        )
        _require_topology_flags(
            git_fingerprint,
            acl_fingerprint,
            complete,
            content_observed,
            controlled_components_reparse_free,
        )
        return _new_topology(
            cls,
            source_root=source_root,
            finance_root=finance_root,
            target_parent=target_parent,
            target_absence=target_absence,
            git_fingerprint=git_fingerprint,
            acl_fingerprint=acl_fingerprint,
            volume_fingerprint=volume_fingerprint,
            complete=complete,
            content_observed=content_observed,
            reparse_free=controlled_components_reparse_free,
        )


def _require_topology_flags(
    git_fingerprint: object,
    acl_fingerprint: object,
    complete: object,
    content_observed: object,
    reparse_free: object,
) -> None:
    if (
        not is_fingerprint(git_fingerprint)
        or not is_fingerprint(acl_fingerprint)
        or type(complete) is not bool
        or complete is not True
        or type(content_observed) is not bool
        or content_observed is not False
        or type(reparse_free) is not bool
        or reparse_free is not True
    ):
        raise ValueError("REAL_HOST_TOPOLOGY_INVALID")


def _new_topology(
    cls,
    *,
    source_root: HostObjectObservationV1,
    finance_root: HostObjectObservationV1,
    target_parent: HostObjectObservationV1,
    target_absence: MissingHostObjectObservationV1,
    git_fingerprint: str,
    acl_fingerprint: str,
    volume_fingerprint: str,
    complete: bool,
    content_observed: bool,
    reparse_free: bool,
):
    body = _topology_body(
        source_root,
        finance_root,
        target_parent,
        target_absence,
        git_fingerprint,
        acl_fingerprint,
        volume_fingerprint,
        complete,
        content_observed,
        reparse_free,
    )
    values = {
        "schema_version": 1,
        "source_root": source_root,
        "finance_root": finance_root,
        "target_parent": target_parent,
        "target_absence": target_absence,
        "git_fingerprint": git_fingerprint,
        "acl_fingerprint": acl_fingerprint,
        "volume_fingerprint": volume_fingerprint,
        "complete": complete,
        "content_observed": content_observed,
        "controlled_components_reparse_free": reparse_free,
        "observation_fingerprint": fingerprint(
            "current-topology-observation-v1", body
        ),
    }
    value = object.__new__(cls)
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value


def _topology_body(
    source,
    finance,
    parent,
    absence,
    git_fingerprint,
    acl_fingerprint,
    volume_fingerprint,
    complete,
    content_observed,
    reparse_free,
) -> dict[str, object]:
    return {
        "acl_fingerprint": acl_fingerprint,
        "complete": complete,
        "content_observed": content_observed,
        "controlled_components_reparse_free": reparse_free,
        "finance_root": finance.observation_fingerprint,
        "git_fingerprint": git_fingerprint,
        "schema_version": 1,
        "source_root": source.observation_fingerprint,
        "target_absence": absence.observation_fingerprint,
        "target_parent": parent.observation_fingerprint,
        "volume_fingerprint": volume_fingerprint,
    }


def _require_relationships(
    source: object,
    finance: object,
    parent: object,
    absence: object,
    volume_fingerprint: object,
) -> None:
    if (
        type(source) is not HostObjectObservationV1
        or type(finance) is not HostObjectObservationV1
        or type(parent) is not HostObjectObservationV1
        or type(absence) is not MissingHostObjectObservationV1
        or any(
            item.object_kind is not HostObjectKind.DIRECTORY
            or item.has_reparse_point
            for item in (source, finance, parent)
        )
        or not is_fingerprint(volume_fingerprint)
        or source.parent_identity_fingerprint
        != parent.object_identity_fingerprint
        or finance.parent_identity_fingerprint
        != parent.object_identity_fingerprint
        or len(
            {
                source.object_identity_fingerprint,
                finance.object_identity_fingerprint,
                parent.object_identity_fingerprint,
            }
        )
        != 3
        or absence.parent_identity_fingerprint
        != parent.object_identity_fingerprint
        or any(
            item.volume_fingerprint != volume_fingerprint
            for item in (source, finance, parent, absence)
        )
    ):
        raise ValueError("REAL_HOST_TOPOLOGY_INVALID")
