"""Internal construction and validation for the V3 binding body."""

from backend.r2_solo_maintainer_closure.contracts import FinalMasterBindingV1

from ._canonical import fingerprint, fingerprint_entries, is_fingerprint
from .errors import ProductionBindingError
from .vocabulary import (
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    authority_domain_for_command_v2,
)


CONFIRMATION_POLICY = "SOLE_MAINTAINER_FRESH_TTY_CONFIRMATION_V1"
CONFIRMATION_ACKNOWLEDGEMENT = (
    "CONFIRM_R2_ISSUE39_EXECUTION_V1_NOT_CLOSURE_ATTESTATION"
)
CONFIRMATION_WINDOW_SECONDS = 300


def build_binding_body(final_master, operation, operators, roles):
    _validate_inputs(final_master, operation, operators, roles)
    operator_body, command_body, role_body = _registry_bodies(operators, roles)
    return {
        "binding_type": "ApprovedCutoverBindingV3",
        "final_master_binding_fingerprint": final_master.binding_fingerprint,
        "final_commit_oid": final_master.final_commit_oid,
        "final_tree_oid": final_master.final_tree_oid,
        "closure_map_fingerprint": final_master.closure_map_fingerprint,
        "source_package_fingerprint": final_master.source_package_fingerprint,
        "runbook_fingerprint": final_master.runbook_fingerprint,
        "workflow_fingerprint": final_master.workflow_fingerprint,
        "operation_fingerprint": operation,
        "operator_role_registry_fingerprint": fingerprint(
            "r2-operator-role-registry-v3", operator_body
        ),
        "command_domain_registry_fingerprint": fingerprint(
            "r2-command-domain-registry-v3", command_body
        ),
        "production_role_registry_fingerprint": fingerprint(
            "r2-production-role-registry-v3", role_body
        ),
        "execution_confirmation_policy": CONFIRMATION_POLICY,
        "execution_confirmation_policy_fingerprint": _policy_fingerprint(),
        "operator_role_count": 4,
        "command_count": 10,
        "command_domain_count": 4,
        "production_role_count": 18,
        "max_execution_confirmation_validity_seconds": 300,
        "operator_role_fingerprints": operator_body,
        "command_domains": command_body,
        "production_role_fingerprints": role_body,
        "assurance_model": "SOLE_MAINTAINER_SELF_REVIEW",
        "operator_count": 1,
        "independent_reviewer_count": 0,
        "external_signer_count": 0,
        "issue39_authority_count": 0,
    }


def _registry_bodies(operators, roles):
    operator_values = tuple((role, operators[role]) for role in OperatorRoleV2)
    role_values = tuple((role, roles[role]) for role in ProductionRoleV2)
    command_body = [
        {
            "command": command.value,
            "domain": authority_domain_for_command_v2(command).value,
        }
        for command in ProductionCommandV2
    ]
    return (
        fingerprint_entries(operator_values),
        command_body,
        fingerprint_entries(role_values),
    )


def _policy_fingerprint():
    return fingerprint(
        "r2-execution-confirmation-policy-v1",
        {
            "confirmation_policy": CONFIRMATION_POLICY,
            "confirmation_acknowledgement": CONFIRMATION_ACKNOWLEDGEMENT,
            "confirmation_window_seconds": CONFIRMATION_WINDOW_SECONDS,
            "single_use": 1,
            "assurance_model": "SOLE_MAINTAINER_SELF_REVIEW",
            "operator_count": 1,
            "independent_reviewer_count": 0,
            "external_signer_count": 0,
            "issue39_authority_count": 0,
        },
    )


def _validate_inputs(final_master, operation, operators, roles):
    if (
        type(final_master) is not FinalMasterBindingV1
        or not is_fingerprint(operation)
        or not _exact_enum_mapping(operators, OperatorRoleV2)
        or not _exact_enum_mapping(roles, ProductionRoleV2)
    ):
        raise ProductionBindingError()
    values = (*operators.values(), *roles.values())
    if (
        not all(is_fingerprint(value) for value in values)
        or len(set(values)) != len(values)
    ):
        raise ProductionBindingError()


def _exact_enum_mapping(value, enum_type):
    return (
        type(value) is dict
        and set(value) == set(enum_type)
        and all(type(key) is enum_type for key in value)
    )
