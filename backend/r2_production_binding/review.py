"""Final-review binding between one frozen master and production composition."""

from backend.r2_final_master_closure import FinalMasterBindingV1, reviewed_production

from ._canonical import fingerprint
from .binding import ApprovedCutoverBindingV2
from .errors import ProductionBindingError


def require_reviewed_production_binding_v2(final_master, production_binding):
    if (
        type(final_master) is not FinalMasterBindingV1
        or type(production_binding) is not ApprovedCutoverBindingV2
        or production_binding.final_master_binding_fingerprint
        != final_master.binding_fingerprint
        or production_binding.final_commit_oid != final_master.final_commit_oid
        or production_binding.final_tree_oid != final_master.final_tree_oid
        or production_binding.closure_map_fingerprint
        != final_master.closure_map_fingerprint
        or production_binding.source_package_fingerprint
        != final_master.source_package_fingerprint
        or production_binding.runbook_fingerprint != final_master.runbook_fingerprint
        or production_binding.workflow_fingerprint != final_master.workflow_fingerprint
    ):
        raise ProductionBindingError()
    return production_binding


def production_composition_evidence_fingerprint_v2(
    final_master, production_binding
):
    value = require_reviewed_production_binding_v2(
        final_master, production_binding
    )
    return fingerprint(
        "r2-reviewed-production-composition-evidence-v2",
        {
            "final_master_binding_fingerprint": final_master.binding_fingerprint,
            "production_binding_fingerprint": value.binding_fingerprint,
            "operator_role_registry_fingerprint": (
                value.operator_role_registry_fingerprint
            ),
            "command_domain_registry_fingerprint": (
                value.command_domain_registry_fingerprint
            ),
            "public_key_registry_fingerprint": value.public_key_registry_fingerprint,
            "production_role_registry_fingerprint": (
                value.production_role_registry_fingerprint
            ),
        },
    )


def reviewed_production_binding_receipt_v2(final_master, production_binding):
    value = require_reviewed_production_binding_v2(
        final_master, production_binding
    )
    return reviewed_production._allocate_reviewed_production_binding_receipt_v1(
        final_master,
        {
            "receipt_type": "R2ReviewedProductionBindingReceiptV1",
            "final_master_binding_fingerprint": final_master.binding_fingerprint,
            "production_binding_fingerprint": value.binding_fingerprint,
            "operator_role_registry_fingerprint": (
                value.operator_role_registry_fingerprint
            ),
            "command_domain_registry_fingerprint": (
                value.command_domain_registry_fingerprint
            ),
            "public_key_registry_fingerprint": value.public_key_registry_fingerprint,
            "production_role_registry_fingerprint": (
                value.production_role_registry_fingerprint
            ),
            "production_composition_evidence_fingerprint": (
                production_composition_evidence_fingerprint_v2(
                    final_master, value
                )
            ),
            "verified": 1,
        },
    )


def require_reviewed_production_binding_receipt_v2(production_binding, receipt):
    if type(production_binding) is not ApprovedCutoverBindingV2:
        raise ProductionBindingError()
    final_master = FinalMasterBindingV1.create(
        final_commit_oid=production_binding.final_commit_oid,
        final_tree_oid=production_binding.final_tree_oid,
        source_package_fingerprint=production_binding.source_package_fingerprint,
        runbook_fingerprint=production_binding.runbook_fingerprint,
        workflow_fingerprint=production_binding.workflow_fingerprint,
    )
    expected = reviewed_production_binding_receipt_v2(
        final_master, production_binding
    )
    if type(receipt) is not type(expected) or receipt.to_mapping() != expected.to_mapping():
        raise ProductionBindingError()
    return receipt
