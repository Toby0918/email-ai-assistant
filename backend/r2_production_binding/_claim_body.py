"""Internal construction and validation for durable authority claims."""

from ._canonical import is_fingerprint
from .binding import ApprovedCutoverBindingV2
from .errors import AuthorityClaimError
from .vocabulary import (
    AuthorityDomainV2,
    OperatorRoleV2,
    ProductionCommandV2,
    PublicKeyRoleV2,
    authority_domain_for_command_v2,
)


_DOMAIN_ROLES = {
    AuthorityDomainV2.PREFLIGHT: (
        OperatorRoleV2.PREFLIGHT_OPERATOR,
        PublicKeyRoleV2.PREFLIGHT_VERIFICATION,
    ),
    AuthorityDomainV2.EVIDENCE: (
        OperatorRoleV2.EVIDENCE_OPERATOR,
        PublicKeyRoleV2.EVIDENCE_VERIFICATION,
    ),
    AuthorityDomainV2.EXECUTION: (
        OperatorRoleV2.EXECUTION_OPERATOR,
        PublicKeyRoleV2.EXECUTION_VERIFICATION,
    ),
    AuthorityDomainV2.RECOVERY: (
        OperatorRoleV2.RECOVERY_OPERATOR,
        PublicKeyRoleV2.RECOVERY_VERIFICATION,
    ),
}


def build_claim_body(**values):
    domain = _validate_claim_inputs(
        binding=values["binding"],
        command=values["command"],
        fingerprints=tuple(values[name] for name in (
            "action_fingerprint",
            "authority_fingerprint",
            "envelope_nonce",
            "journal_owner_fingerprint",
            "prior_journal_head_fingerprint",
        )),
        claim_sequence=values["claim_sequence"],
        times=tuple(values[name] for name in (
            "issued_at_epoch",
            "not_before_epoch",
            "expires_at_epoch",
            "claimed_at_epoch",
        )),
    )
    return _claim_fields(values, domain)


def _claim_fields(values, domain):
    binding = values["binding"]
    operator_role, key_role = _DOMAIN_ROLES[domain]
    return {
        "claim_type": "DurableAuthorityClaimV2",
        "binding_fingerprint": binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        "production_role_registry_fingerprint": binding.production_role_registry_fingerprint,
        "public_key_registry_fingerprint": binding.public_key_registry_fingerprint,
        "command": values["command"].value,
        "domain": domain.value,
        "operator_role": operator_role.value,
        "public_key_role": key_role.value,
        **{name: values[name] for name in (
            "action_fingerprint",
            "authority_fingerprint",
            "envelope_nonce",
            "journal_owner_fingerprint",
            "prior_journal_head_fingerprint",
            "claim_sequence",
            "issued_at_epoch",
            "not_before_epoch",
            "expires_at_epoch",
            "claimed_at_epoch",
        )},
        "single_use": 1,
    }


def _validate_claim_inputs(*, binding, command, fingerprints, claim_sequence, times):
    domain = authority_domain_for_command_v2(command)
    issued_at, not_before, expires_at, claimed_at = times
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(command) is not ProductionCommandV2
        or domain is None
        or not all(is_fingerprint(value) for value in fingerprints)
        or type(claim_sequence) is not int
        or claim_sequence < 1
        or any(type(value) is not int or value < 0 for value in times)
        or not issued_at <= not_before <= claimed_at
        or not claimed_at < expires_at
        or expires_at - issued_at > binding.max_authority_validity_seconds
    ):
        raise AuthorityClaimError()
    return domain
