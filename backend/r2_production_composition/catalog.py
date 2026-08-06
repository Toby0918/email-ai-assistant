"""Closed allocation of ten production commands to three adapter slots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.r2_production_binding import (
    ProductionBindingError,
    ProductionCommandV2,
    ProductionRoleV2,
)
from backend.r2_production_binding._adapter_identity import (
    _adapter_type_surface_digest_v1,
    _require_adapter_type_surface_v1,
    _snapshot_adapter_type_surface_v1,
)

from .evidence import EvidenceProductionAdapterV1
from .preflight import PreflightProductionAdapterV1
from .transaction import TransactionProductionAdapterV1


class ProductionAdapterSlotV1(str, Enum):
    PREFLIGHT = "preflight"
    EVIDENCE = "evidence"
    TRANSACTION = "transaction"


@dataclass(frozen=True, slots=True)
class ProductionAdapterRegistrationV1:
    command: ProductionCommandV2
    slot: ProductionAdapterSlotV1
    production_role: ProductionRoleV2
    adapter_type: type


_COMMAND_ROLES = (
    ProductionRoleV2.LEGACY_SOURCE_ANCHOR,
    ProductionRoleV2.PROJECT_CONTAINER,
    ProductionRoleV2.REPOSITORY_ROOT,
    ProductionRoleV2.GIT_COMMON_STATE,
    ProductionRoleV2.FINAL_RUNNING_AUDIT,
    ProductionRoleV2.STOPPED_LAYOUT_AUDIT,
    ProductionRoleV2.EVIDENCE_PACKAGE,
    ProductionRoleV2.MANAGED_MAIN,
    ProductionRoleV2.TRANSACTION_JOURNAL,
    ProductionRoleV2.LEGACY_SERVICE,
)
_SLOTS = (
    *(ProductionAdapterSlotV1.PREFLIGHT for _ in range(6)),
    ProductionAdapterSlotV1.EVIDENCE,
    *(ProductionAdapterSlotV1.TRANSACTION for _ in range(3)),
)
_ADAPTER_TYPES = {
    ProductionAdapterSlotV1.PREFLIGHT: PreflightProductionAdapterV1,
    ProductionAdapterSlotV1.EVIDENCE: EvidenceProductionAdapterV1,
    ProductionAdapterSlotV1.TRANSACTION: TransactionProductionAdapterV1,
}
_CATALOG = tuple(
    ProductionAdapterRegistrationV1(
        command,
        slot,
        role,
        _ADAPTER_TYPES[slot],
    )
    for command, slot, role in zip(
        ProductionCommandV2,
        _SLOTS,
        _COMMAND_ROLES,
        strict=True,
    )
)
_REVIEWED_ADAPTER_SURFACES = tuple(
    (
        adapter_type,
        _snapshot_adapter_type_surface_v1(adapter_type),
        _adapter_type_surface_digest_v1(adapter_type),
    )
    for adapter_type in _ADAPTER_TYPES.values()
)


def production_adapter_catalog_v1():
    for adapter_type, _surface, _digest in _REVIEWED_ADAPTER_SURFACES:
        _reviewed_adapter_surface_v1(adapter_type)
    return _CATALOG


def production_adapter_registration_v1(command):
    if type(command) is not ProductionCommandV2:
        raise ValueError("R2_PRODUCTION_ADAPTER_CATALOG_INVALID")
    index = tuple(ProductionCommandV2).index(command)
    return production_adapter_catalog_v1()[index]


def _reviewed_adapter_surface_v1(
    adapter_type,
    _frozen_surfaces=_REVIEWED_ADAPTER_SURFACES,
):
    try:
        if _REVIEWED_ADAPTER_SURFACES is not _frozen_surfaces:
            raise ProductionBindingError()
        matches = tuple(
            (surface, digest)
            for expected_type, surface, digest in _frozen_surfaces
            if adapter_type is expected_type
        )
        if len(matches) != 1:
            raise ProductionBindingError()
        surface, digest = matches[0]
        _require_adapter_type_surface_v1(adapter_type, surface)
        if _adapter_type_surface_digest_v1(adapter_type) != digest:
            raise ProductionBindingError()
        return surface
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None
