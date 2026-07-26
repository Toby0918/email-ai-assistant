"""Pure Managed layout validation for the synthetic rehearsal."""

from __future__ import annotations

from .adapters import (
    ManagedLayoutEvidence,
    ManagedResourceEvidence,
    ZoneEvidence,
)
from .policy import CONFIG_KEYS, ManagedResourceRole, ManagedZone

_RESOURCE_PARENTS = {
    ManagedResourceRole.ATTACHMENT_TEMP: ManagedZone.RUNTIME_TEMP,
    ManagedResourceRole.SERVICE_LOG: ManagedZone.LOGS,
    ManagedResourceRole.PID_STATE: ManagedZone.LOGS,
    ManagedResourceRole.NON_SECRET_CONFIG: ManagedZone.CONFIG,
    ManagedResourceRole.BROWSER_EXTENSION: ManagedZone.ARTIFACTS,
}


def valid_layout(value: object) -> bool:
    """Require one complete, content-free synthetic layout."""
    if type(value) is not ManagedLayoutEvidence:
        return False
    if (
        type(value.schema_version) is not int
        or value.schema_version != 1
        or value.synthetic is not True
        or not _identity(value.scope_identity)
        or not _identity(value.container_identity)
        or value.scope_identity == value.container_identity
        or type(value.zones) is not tuple
        or type(value.resources) is not tuple
        or type(value.config_keys) is not tuple
        or not all(type(key) is str for key in value.config_keys)
        or value.config_keys != CONFIG_KEYS
        or value.config_values_observed is not False
        or value.signing_material_observed is not False
    ):
        return False
    zones = value.zones
    if len(zones) != len(ManagedZone):
        return False
    if any(type(zone) is not ZoneEvidence for zone in zones):
        return False
    if not all(_valid_zone(zone) for zone in zones):
        return False
    roles = tuple(zone.role for zone in zones)
    identities = tuple(zone.identity for zone in zones)
    return (
        set(roles) == set(ManagedZone)
        and len(set(roles)) == len(roles)
        and len(set(identities)) == len(identities)
        and _valid_resources(value)
    )


def stable_layout(
    first: object,
    second: object,
) -> bool:
    """Reject identity, role or observation drift."""
    return (
        valid_layout(first)
        and valid_layout(second)
        and second == first
    )


def zone_identity(
    layout: ManagedLayoutEvidence,
    role: ManagedZone,
) -> str:
    """Return the identity for one validated fixed role."""
    return next(
        zone.identity for zone in layout.zones if zone.role is role
    )


def resource_identity(
    layout: ManagedLayoutEvidence,
    role: ManagedResourceRole,
) -> str:
    """Return the identity for one validated fixed resource."""
    return next(
        resource.identity
        for resource in layout.resources
        if resource.role is role
    )


def _valid_zone(zone: ZoneEvidence) -> bool:
    return (
        type(zone.role) is ManagedZone
        and _identity(zone.identity)
        and zone.direct_child is True
        and zone.canonical is True
        and zone.has_reparse_component is False
    )


def _valid_resources(layout: ManagedLayoutEvidence) -> bool:
    resources = layout.resources
    if (
        len(resources) != len(ManagedResourceRole)
        or any(
            type(resource) is not ManagedResourceEvidence
            for resource in resources
        )
        or not all(
            _valid_resource(resource, layout)
            for resource in resources
        )
    ):
        return False
    roles = tuple(resource.role for resource in resources)
    identities = tuple(resource.identity for resource in resources)
    all_identities = identities + tuple(
        zone.identity for zone in layout.zones
    )
    return (
        set(roles) == set(ManagedResourceRole)
        and len(set(roles)) == len(roles)
        and len(set(all_identities)) == len(all_identities)
    )


def _valid_resource(
    resource: ManagedResourceEvidence,
    layout: ManagedLayoutEvidence,
) -> bool:
    return (
        type(resource.role) is ManagedResourceRole
        and _identity(resource.identity)
        and _identity(resource.parent_identity)
        and resource.parent_identity
        == zone_identity(layout, _RESOURCE_PARENTS[resource.role])
        and resource.direct_child is True
        and resource.canonical is True
        and resource.has_reparse_component is False
    )


def _identity(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 128
        and value.strip() == value
    )
