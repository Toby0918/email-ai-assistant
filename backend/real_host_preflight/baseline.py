"""Read-only collector that projects separate evidence into HostBaseline."""

from __future__ import annotations

from dataclasses import dataclass

from .authorization_gate import require_preflight_authorization
from .baseline_bridge import HostBaseline
from .baseline_evidence import (
    AclBaselineObservationV1,
    BaselineAclRole,
    OperatorSidObservationV1,
    RealHostBaselineCallbacks,
)
from .canonical import fingerprint, role_selections_match
from .contracts import HostObjectKind, HostObjectObservationV1
from .contracts_bridge import CutoverProfileV1
from .evidence import VolumeObservationV1
from .integrity import (
    valid_acl_baseline,
    valid_host_object,
    valid_operator_sid,
    valid_volume,
)


@dataclass(frozen=True, slots=True, repr=False)
class RealHostBaselineCollector:
    """Collect exactly eight fixed-role content-free observations."""

    callbacks: RealHostBaselineCallbacks

    def collect(
        self,
        *,
        profile: CutoverProfileV1,
        authorization: object,
        operation_fingerprint: str,
        observed_at_epoch: int,
    ) -> HostBaseline:
        try:
            require_preflight_authorization(
                authorization,
                profile=profile,
                operation_fingerprint=operation_fingerprint,
                phase="host_baseline",
                observed_at_epoch=observed_at_epoch,
            )
            values = self._collect_values()
            _validate_baseline_relationships(
                *values,
                profile.to_mapping(),
            )
            return _project_baseline(*values)
        except Exception:
            raise ValueError("REAL_HOST_BASELINE_REJECTED") from None

    def _collect_values(
        self,
    ) -> tuple[
        HostObjectObservationV1,
        HostObjectObservationV1,
        HostObjectObservationV1,
        VolumeObservationV1,
        OperatorSidObservationV1,
        AclBaselineObservationV1,
        AclBaselineObservationV1,
        AclBaselineObservationV1,
    ]:
        if type(self.callbacks) is not RealHostBaselineCallbacks:
            raise ValueError("REAL_HOST_BASELINE_REJECTED")
        return (
            self.callbacks.source_root(),
            self.callbacks.parent(),
            self.callbacks.finance(),
            self.callbacks.volume(),
            self.callbacks.operator_sid(),
            self.callbacks.source_acl(),
            self.callbacks.parent_acl(),
            self.callbacks.finance_acl(),
        )


def _validate_baseline_relationships(
    source: object,
    parent: object,
    finance: object,
    volume: object,
    operator_sid: object,
    source_acl: object,
    parent_acl: object,
    finance_acl: object,
    profile_mapping: object,
) -> None:
    if (
        not valid_host_object(source)
        or not valid_host_object(parent)
        or not valid_host_object(finance)
        or not valid_volume(volume)
        or not valid_operator_sid(operator_sid)
        or any(
            item.object_kind is not HostObjectKind.DIRECTORY
            or item.has_reparse_point
            for item in (source, parent, finance)
        )
        or not _valid_acl(source_acl, BaselineAclRole.SOURCE_ROOT, source)
        or not _valid_acl(parent_acl, BaselineAclRole.PARENT, parent)
        or not _valid_acl(finance_acl, BaselineAclRole.FINANCE, finance)
        or not _valid_acl_total(source_acl, parent_acl, finance_acl)
        or source.parent_identity_fingerprint
        != parent.object_identity_fingerprint
        or finance.parent_identity_fingerprint
        != parent.object_identity_fingerprint
        or len(
            {
                source.object_identity_fingerprint,
                parent.object_identity_fingerprint,
                finance.object_identity_fingerprint,
            }
        )
        != 3
        or any(
            item.volume_fingerprint != volume.volume_fingerprint
            for item in (source, parent, finance)
        )
        or not _baseline_roles_match(
            profile_mapping, source, parent, finance
        )
    ):
        raise ValueError("REAL_HOST_BASELINE_REJECTED")


def _baseline_roles_match(
    profile_mapping: object,
    source: HostObjectObservationV1,
    parent: HostObjectObservationV1,
    finance: HostObjectObservationV1,
) -> bool:
    return role_selections_match(
        profile_mapping,
        {
            "source_root": source.normalized_name_fingerprint,
            "target_parent": parent.normalized_name_fingerprint,
            "finance_root": finance.normalized_name_fingerprint,
        },
    )


def _valid_acl(
    value: object,
    role: BaselineAclRole,
    observed_object: HostObjectObservationV1,
) -> bool:
    return (
        valid_acl_baseline(value)
        and value.role is role
        and value.object_identity_fingerprint
        == observed_object.object_identity_fingerprint
    )


def _valid_acl_total(*values: AclBaselineObservationV1) -> bool:
    return sum(value.entry_count for value in values) <= 4096


def _project_baseline(
    source: HostObjectObservationV1,
    parent: HostObjectObservationV1,
    finance: HostObjectObservationV1,
    volume: VolumeObservationV1,
    operator_sid: OperatorSidObservationV1,
    source_acl: AclBaselineObservationV1,
    parent_acl: AclBaselineObservationV1,
    finance_acl: AclBaselineObservationV1,
) -> HostBaseline:
    acl_hash = fingerprint(
        "real-host-acl-baseline-v1",
        {
            "finance": finance_acl.observation_fingerprint,
            "operator_sid": operator_sid.observation_fingerprint,
            "parent": parent_acl.observation_fingerprint,
            "source_root": source_acl.observation_fingerprint,
        },
    )
    volume_hash = fingerprint(
        "real-host-volume-baseline-v1",
        {
            "finance": finance.observation_fingerprint,
            "parent": parent.observation_fingerprint,
            "source_root": source.observation_fingerprint,
            "volume": volume.observation_fingerprint,
        },
    )
    return HostBaseline(
        schema_version=1,
        acl_sha256=acl_hash,
        acl_entry_count=(
            source_acl.entry_count
            + parent_acl.entry_count
            + finance_acl.entry_count
        ),
        volume_sha256=volume_hash,
        filesystem_name=volume.filesystem_name,
        drive_type=volume.drive_type,
        evidence_complete=True,
        content_observed=False,
    )
