"""Exact pure bodies for dormant Execution Confirmation V1."""

from ._binding_body import (
    CONFIRMATION_ACKNOWLEDGEMENT,
    CONFIRMATION_POLICY,
    CONFIRMATION_WINDOW_SECONDS,
)
from ._canonical import fingerprint, is_fingerprint
from .binding import ApprovedCutoverBindingV3
from .errors import ExecutionConfirmationError
from .vocabulary import (
    AuthorityDomainV2,
    OperatorRoleV2,
    ProductionCommandV2,
    authority_domain_for_command_v2,
)


CANDIDATE_FIELDS = (
    "candidate_type", "status", "confirmation_policy",
    "production_binding_fingerprint", "final_master_binding_fingerprint",
    "closure_manifest_fingerprint",
    "solo_maintainer_attestation_receipt_fingerprint", "command",
    "command_domain", "operator_role_fingerprint", "operation_fingerprint",
    "action_fingerprint", "journal_owner_fingerprint",
    "prior_journal_head_fingerprint", "transition_instance_fingerprint",
    "remaining_reverse_plan_fingerprint", "claim_sequence",
    "confirmation_acknowledgement", "prepared_at_epoch", "expires_at_epoch",
    "confirmation_window_seconds", "single_use",
)
CLAIM_FIELDS = (
    "claim_type", "status", "confirmation_policy",
    "production_binding_fingerprint", "final_master_binding_fingerprint",
    "closure_manifest_fingerprint",
    "solo_maintainer_attestation_receipt_fingerprint", "command",
    "command_domain", "operator_role_fingerprint", "operation_fingerprint",
    "action_fingerprint", "journal_owner_fingerprint",
    "prior_journal_head_fingerprint", "transition_instance_fingerprint",
    "remaining_reverse_plan_fingerprint", "claim_sequence", "prepared_at_epoch",
    "confirmed_at_epoch", "expires_at_epoch", "confirmation_window_seconds",
    "acknowledgement", "acknowledgement_fingerprint", "assurance_model",
    "operator_count", "independent_reviewer_count", "external_signer_count",
    "execution_confirmation_count", "single_use", "replay_count",
    "provider_attempt_count", "deletion_operation_count",
)
_DOMAIN_ROLES = {
    AuthorityDomainV2.PREFLIGHT: OperatorRoleV2.PREFLIGHT_OPERATOR,
    AuthorityDomainV2.EVIDENCE: OperatorRoleV2.EVIDENCE_OPERATOR,
    AuthorityDomainV2.EXECUTION: OperatorRoleV2.EXECUTION_OPERATOR,
    AuthorityDomainV2.RECOVERY: OperatorRoleV2.RECOVERY_OPERATOR,
}


def build_candidate_body(**values):
    binding = values["binding"]
    command = values["command"]
    domain = _validate_candidate_inputs(binding, command, values)
    operator_role = _DOMAIN_ROLES[domain]
    return {
        "candidate_type": "ExecutionConfirmationCandidateV1",
        "status": "AWAITING_EXECUTION_CONFIRMATION",
        "confirmation_policy": CONFIRMATION_POLICY,
        "production_binding_fingerprint": binding.binding_fingerprint,
        "final_master_binding_fingerprint": (
            binding.final_master_binding_fingerprint
        ),
        "closure_manifest_fingerprint": values["closure_manifest_fingerprint"],
        "solo_maintainer_attestation_receipt_fingerprint": values[
            "solo_maintainer_attestation_receipt_fingerprint"
        ],
        "command": command.value,
        "command_domain": domain.value,
        "operator_role_fingerprint": dict(binding.operator_role_fingerprints)[
            operator_role
        ],
        "operation_fingerprint": binding.operation_fingerprint,
        **{
            name: values[name]
            for name in _ACTION_FINGERPRINT_FIELDS
        },
        "claim_sequence": values["claim_sequence"],
        "confirmation_acknowledgement": CONFIRMATION_ACKNOWLEDGEMENT,
        "prepared_at_epoch": values["prepared_at_epoch"],
        "expires_at_epoch": (
            values["prepared_at_epoch"] + CONFIRMATION_WINDOW_SECONDS
        ),
        "confirmation_window_seconds": CONFIRMATION_WINDOW_SECONDS,
        "single_use": 1,
    }


_ACTION_FINGERPRINT_FIELDS = (
    "action_fingerprint", "journal_owner_fingerprint",
    "prior_journal_head_fingerprint", "transition_instance_fingerprint",
    "remaining_reverse_plan_fingerprint",
)


def build_claim_body(candidate_body, confirmed_at_epoch):
    _validate_candidate_body(candidate_body)
    if (
        type(confirmed_at_epoch) is not int
        or confirmed_at_epoch < candidate_body["prepared_at_epoch"]
        or confirmed_at_epoch >= candidate_body["expires_at_epoch"]
    ):
        raise ExecutionConfirmationError()
    copied = (
        "confirmation_policy", "production_binding_fingerprint",
        "final_master_binding_fingerprint", "closure_manifest_fingerprint",
        "solo_maintainer_attestation_receipt_fingerprint", "command",
        "command_domain", "operator_role_fingerprint", "operation_fingerprint",
        *_ACTION_FINGERPRINT_FIELDS, "claim_sequence", "prepared_at_epoch",
        "expires_at_epoch", "confirmation_window_seconds",
    )
    return {
        "claim_type": "ExecutionConfirmationClaimV1",
        "status": "EXECUTION_CONFIRMATION_RECORDED",
        **{name: candidate_body[name] for name in copied},
        "confirmed_at_epoch": confirmed_at_epoch,
        "acknowledgement": CONFIRMATION_ACKNOWLEDGEMENT,
        "acknowledgement_fingerprint": _acknowledgement_fingerprint(),
        "assurance_model": "SOLE_MAINTAINER_SELF_REVIEW",
        "operator_count": 1,
        "independent_reviewer_count": 0,
        "external_signer_count": 0,
        "execution_confirmation_count": 1,
        "single_use": 1,
        "replay_count": 0,
        "provider_attempt_count": 0,
        "deletion_operation_count": 0,
    }


def candidate_body_from_claim(binding, source):
    values = {
        "binding": binding,
        "command": _command(source.get("command")),
        "closure_manifest_fingerprint": source.get(
            "closure_manifest_fingerprint"
        ),
        "solo_maintainer_attestation_receipt_fingerprint": source.get(
            "solo_maintainer_attestation_receipt_fingerprint"
        ),
        **{name: source.get(name) for name in _ACTION_FINGERPRINT_FIELDS},
        "claim_sequence": source.get("claim_sequence"),
        "prepared_at_epoch": source.get("prepared_at_epoch"),
    }
    return build_candidate_body(**values)


def candidate_body_from_source(binding, source):
    names = (
        "closure_manifest_fingerprint",
        "solo_maintainer_attestation_receipt_fingerprint",
        *_ACTION_FINGERPRINT_FIELDS,
        "claim_sequence",
        "prepared_at_epoch",
    )
    return build_candidate_body(
        binding=binding,
        command=_command(source.get("command")),
        **{name: source.get(name) for name in names},
    )


def allocate_contract(value_type, body, fields):
    value = object.__new__(value_type)
    enums = {"command": ProductionCommandV2, "command_domain": AuthorityDomainV2}
    for name in fields:
        item = enums[name](body[name]) if name in enums else body[name]
        object.__setattr__(value, name, item)
    return value


def contract_mapping(value, fields, fingerprint_name):
    return {
        **contract_body(value, fields),
        fingerprint_name: getattr(value, fingerprint_name),
    }


def contract_body(value, fields):
    body = {name: getattr(value, name) for name in fields}
    for name in ("command", "command_domain"):
        body[name] = body[name].value
    return body


def candidate_fingerprint(body):
    return fingerprint("r2-execution-confirmation-candidate-v1", body)


def claim_fingerprint(body):
    return fingerprint("r2-execution-confirmation-claim-v1", body)


def _validate_candidate_inputs(binding, command, values):
    domain = authority_domain_for_command_v2(command)
    fingerprints = (
        values["closure_manifest_fingerprint"],
        values["solo_maintainer_attestation_receipt_fingerprint"],
        *(values[name] for name in _ACTION_FINGERPRINT_FIELDS),
    )
    if (
        type(binding) is not ApprovedCutoverBindingV3
        or type(command) is not ProductionCommandV2
        or domain is None
        or not all(is_fingerprint(value) for value in fingerprints)
        or type(values["claim_sequence"]) is not int
        or values["claim_sequence"] < 1
        or type(values["prepared_at_epoch"]) is not int
        or values["prepared_at_epoch"] < 0
        or binding.execution_confirmation_policy != CONFIRMATION_POLICY
        or binding.max_execution_confirmation_validity_seconds
        != CONFIRMATION_WINDOW_SECONDS
    ):
        raise ExecutionConfirmationError()
    return domain


def _validate_candidate_body(body):
    if (
        type(body) is not dict
        or set(body) != set(CANDIDATE_FIELDS)
        or body["candidate_type"] != "ExecutionConfirmationCandidateV1"
        or body["status"] != "AWAITING_EXECUTION_CONFIRMATION"
        or body["confirmation_policy"] != CONFIRMATION_POLICY
        or body["confirmation_acknowledgement"] != CONFIRMATION_ACKNOWLEDGEMENT
        or body["confirmation_window_seconds"] != CONFIRMATION_WINDOW_SECONDS
        or body["single_use"] != 1
        or body["expires_at_epoch"]
        != body["prepared_at_epoch"] + CONFIRMATION_WINDOW_SECONDS
    ):
        raise ExecutionConfirmationError()


def _acknowledgement_fingerprint():
    return fingerprint(
        "r2-execution-confirmation-claim-v1",
        {"acknowledgement": CONFIRMATION_ACKNOWLEDGEMENT},
    )


def _command(value):
    try:
        return ProductionCommandV2(value)
    except (TypeError, ValueError):
        raise ExecutionConfirmationError() from None
