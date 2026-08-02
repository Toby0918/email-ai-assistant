"""Internal construction and validation for the reviewed V2 binding body."""

from backend.r2_final_master_closure import FinalMasterBindingV1

from ._canonical import fingerprint, fingerprint_entries, is_fingerprint
from .errors import ProductionBindingError
from .vocabulary import (
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    PublicKeyRoleV2,
    authority_domain_for_command_v2,
)


def build_binding_body(final_master, operation, operators, keys, roles):
    _validate_inputs(final_master, operation, operators, keys, roles)
    operator_body, command_body, key_body, role_body = _registry_bodies(
        operators, keys, roles
    )
    return {
        "binding_type": "ApprovedCutoverBindingV2",
        "final_master_binding_fingerprint": final_master.binding_fingerprint,
        "final_commit_oid": final_master.final_commit_oid,
        "final_tree_oid": final_master.final_tree_oid,
        "closure_map_fingerprint": final_master.closure_map_fingerprint,
        "source_package_fingerprint": final_master.source_package_fingerprint,
        "runbook_fingerprint": final_master.runbook_fingerprint,
        "workflow_fingerprint": final_master.workflow_fingerprint,
        "operation": "r2_project_container_cutover",
        "operation_fingerprint": operation,
        "operator_role_registry_fingerprint": fingerprint(
            "r2-operator-role-registry-v2", operator_body
        ),
        "command_domain_registry_fingerprint": fingerprint(
            "r2-command-domain-registry-v2", command_body
        ),
        "public_key_registry_fingerprint": fingerprint(
            "r2-public-key-registry-v2", key_body
        ),
        "production_role_registry_fingerprint": fingerprint(
            "r2-production-role-registry-v2", role_body
        ),
        "authority_domain_count": 4,
        "preflight_verb_count": 6,
        "process_root_count": 3,
        "local_ref_count": 14,
        "worktree_count": 11,
        "managed_unit_count": 4,
        "max_authority_validity_seconds": 300,
        "operator_role_fingerprints": operator_body,
        "command_domains": command_body,
        "verification_public_keys": key_body,
        "production_role_fingerprints": role_body,
    }


def _registry_bodies(operators, keys, roles):
    operator_values = tuple((role, operators[role]) for role in OperatorRoleV2)
    key_values = tuple((role, keys[role]) for role in PublicKeyRoleV2)
    role_values = tuple((role, roles[role]) for role in ProductionRoleV2)
    commands = tuple(
        (command, authority_domain_for_command_v2(command))
        for command in ProductionCommandV2
    )
    operator_body = fingerprint_entries(operator_values)
    command_body = [
        {"command": command.value, "domain": domain.value}
        for command, domain in commands
    ]
    key_body = [
        {"role": role.value, "public_key_hex": key.hex()}
        for role, key in key_values
    ]
    return operator_body, command_body, key_body, fingerprint_entries(role_values)


def _validate_inputs(final_master, operation, operators, keys, roles) -> None:
    if (
        type(final_master) is not FinalMasterBindingV1
        or not is_fingerprint(operation)
        or not _exact_enum_mapping(operators, OperatorRoleV2)
        or not _exact_enum_mapping(keys, PublicKeyRoleV2)
        or not _exact_enum_mapping(roles, ProductionRoleV2)
    ):
        raise ProductionBindingError()
    fingerprints = (*operators.values(), *roles.values())
    public_keys = tuple(keys.values())
    if (
        not all(is_fingerprint(value) for value in fingerprints)
        or len(set(fingerprints)) != len(fingerprints)
        or any(type(value) is not bytes or len(value) != 32 for value in public_keys)
        or any(value == bytes(32) for value in public_keys)
        or len(set(public_keys)) != len(public_keys)
    ):
        raise ProductionBindingError()


def _exact_enum_mapping(value, enum_type) -> bool:
    return (
        type(value) is dict
        and set(value) == set(enum_type)
        and all(type(key) is enum_type for key in value)
    )
