"""Pure derivation of one reviewed production-binding candidate."""

from __future__ import annotations

from backend.r2_final_master_closure import FinalMasterBindingV1
from backend.r2_final_master_closure.global_gate_registry import (
    gate_evidence_registry,
)
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    OperatorRoleV2,
    ProductionBindingError,
    ProductionRoleV2,
    PublicKeyRoleV2,
    production_adapter_fingerprint_v1,
)
from backend.r2_production_binding._canonical import fingerprint

from .adapter_binding import operator_subject_fingerprint_v1
from .catalog import production_adapter_catalog_v1


def build_production_binding_candidate_v1(
    *,
    final_master_binding,
    verification_public_keys,
):
    """Derive every non-key binding input from reviewed public code."""
    try:
        keys = _require_inputs(final_master_binding, verification_public_keys)
        subject = operator_subject_fingerprint_v1(keys)
        operators = {
            role: fingerprint(
                "r2-operator-role-v2",
                {
                    "operator_subject_fingerprint": subject,
                    "role": role.value,
                },
            )
            for role in OperatorRoleV2
        }
        operation = fingerprint(
            "r2-project-container-operation-v2",
            {
                "final_master_binding_fingerprint": (
                    final_master_binding.binding_fingerprint
                ),
                "operation": "r2_project_container_cutover",
                "operator_subject_fingerprint": subject,
            },
        )
        roles = _production_role_fingerprints(final_master_binding)
        return ApprovedCutoverBindingV2.create(
            final_master_binding=final_master_binding,
            operation_fingerprint=operation,
            operator_role_fingerprints=operators,
            verification_public_keys=keys,
            production_role_fingerprints=roles,
        )
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def _production_role_fingerprints(final_master):
    catalog = production_adapter_catalog_v1()
    values = {
        item.production_role: production_adapter_fingerprint_v1(
            item.command,
            item.adapter_type,
        )
        for item in catalog
    }
    for role in ProductionRoleV2:
        if role not in values:
            values[role] = fingerprint(
                "r2-nominal-production-role-v2",
                {
                    "final_master_binding_fingerprint": (
                        final_master.binding_fingerprint
                    ),
                    "role": role.value,
                },
            )
    return values


def _require_inputs(final_master, verification_public_keys):
    if type(final_master) is not FinalMasterBindingV1:
        raise ProductionBindingError()
    keys = _require_public_keys(verification_public_keys)
    gate_keys = {
        item.verification_public_key for item in gate_evidence_registry()
    }
    if set(keys.values()) & gate_keys:
        raise ProductionBindingError()
    return keys


def _require_public_keys(value):
    if (
        type(value) is not dict
        or set(value) != set(PublicKeyRoleV2)
        or any(type(role) is not PublicKeyRoleV2 for role in value)
        or any(type(key) is not bytes or len(key) != 32 for key in value.values())
        or any(key == bytes(32) for key in value.values())
        or len(set(value.values())) != len(PublicKeyRoleV2)
    ):
        raise ProductionBindingError()
    return dict(value)
