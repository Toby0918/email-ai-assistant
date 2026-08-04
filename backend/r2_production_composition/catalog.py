"""Closed allocation of ten production commands to three adapter slots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.r2_production_binding import ProductionCommandV2, ProductionRoleV2

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


def production_adapter_catalog_v1():
    return _CATALOG


def production_adapter_registration_v1(command):
    if type(command) is not ProductionCommandV2:
        raise ValueError("R2_PRODUCTION_ADAPTER_CATALOG_INVALID")
    return _CATALOG[tuple(ProductionCommandV2).index(command)]
