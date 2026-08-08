"""Pure derivation of one sole-maintainer production-binding candidate."""

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    OperatorRoleV2,
    ProductionBindingError,
    ProductionRoleV2,
    production_adapter_fingerprint_v1,
)
from backend.r2_production_binding._canonical import fingerprint
from backend.r2_solo_maintainer_closure.contracts import FinalMasterBindingV1

from .catalog import production_adapter_catalog_v1


def build_production_binding_candidate_v1(*, final_master_binding):
    """Derive every V3 binding input from one nominal frozen master."""
    try:
        if type(final_master_binding) is not FinalMasterBindingV1:
            raise ProductionBindingError()
        subject = operator_subject_fingerprint_v1(final_master_binding)
        operators = {
            role: fingerprint(
                "r2-operator-role-v3",
                {
                    "operator_subject_fingerprint": subject,
                    "role": role.value,
                },
            )
            for role in OperatorRoleV2
        }
        operation = fingerprint(
            "r2-project-container-operation-v3",
            {
                "final_master_binding_fingerprint": (
                    final_master_binding.binding_fingerprint
                ),
                "operation": "r2_project_container_cutover",
                "operator_subject_fingerprint": subject,
            },
        )
        return ApprovedCutoverBindingV3.create(
            final_master_binding=final_master_binding,
            operation_fingerprint=operation,
            operator_role_fingerprints=operators,
            production_role_fingerprints=_production_role_fingerprints(
                final_master_binding
            ),
        )
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def operator_subject_fingerprint_v1(final_master_binding):
    if type(final_master_binding) is not FinalMasterBindingV1:
        raise ProductionBindingError()
    return _operator_subject_fingerprint(
        final_master_binding.binding_fingerprint
    )


def _operator_subject_fingerprint(final_master_binding_fingerprint):
    return fingerprint(
        "r2-solo-maintainer-operator-subject-v1",
        {
            "final_master_binding_fingerprint": final_master_binding_fingerprint,
            "assurance_model": "SOLE_MAINTAINER_SELF_REVIEW",
            "operator_count": 1,
        },
    )


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
                "r2-nominal-production-role-v3",
                {
                    "final_master_binding_fingerprint": (
                        final_master.binding_fingerprint
                    ),
                    "role": role.value,
                },
            )
    return values
