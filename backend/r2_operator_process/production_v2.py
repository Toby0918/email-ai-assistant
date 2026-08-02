"""Verification-only ingress for reviewed production authority V2."""

from __future__ import annotations

import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.cutover_composition_contracts.canonical import (
    canonical_json,
    is_fingerprint,
    strict_json_object,
)
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    AuthorityDomainV2,
    DurableAuthorityClaimV2,
    OperatorRoleV2,
    ProductionCommandV2,
    PublicKeyRoleV2,
    authority_domain_for_command_v2,
    production_action_fingerprint_v2,
    validate_new_authority_claim,
)


_ERROR = "R2_PRODUCTION_AUTHORITY_ENVELOPE_REJECTED"
_TYPE = "R2ProductionAuthorityEnvelopeV2"
_MAX_ENCODED_BYTES = 65_536
_BODY_FIELDS = (
    "envelope_type",
    "binding_fingerprint",
    "final_master_binding_fingerprint",
    "operation_fingerprint",
    "command",
    "domain",
    "operator_role",
    "operator_fingerprint",
    "public_key_role",
    "action_fingerprint",
    "envelope_nonce",
    "journal_owner_fingerprint",
    "prior_journal_head_fingerprint",
    "claim_sequence",
    "issued_at_epoch",
    "not_before_epoch",
    "expires_at_epoch",
    "authority_fingerprint",
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


class ProductionAuthorityEnvelopeError(ValueError):
    def __init__(self) -> None:
        super().__init__(_ERROR)

    def __repr__(self) -> str:
        return f"ProductionAuthorityEnvelopeError({_ERROR!r})"


def production_authority_message_v2(body: object) -> bytes:
    source = _exact_body(body)
    return b"r2-production-authority-envelope-v2\0" + canonical_json(source)


def verify_production_authority_v2(
    encoded: object,
    *,
    binding: object,
    expected_command: object,
    durable_claims: object,
    expected_prior_journal_head_fingerprint: object,
    observed_at_epoch: object,
    expected_action_fingerprint: object = None,
) -> DurableAuthorityClaimV2:
    try:
        source = _decode_envelope(encoded)
        body = {name: source[name] for name in _BODY_FIELDS}
        command = _require_binding(
            body,
            binding,
            expected_command,
            expected_action_fingerprint,
        )
        _require_signature(source["signature"], body, binding, command)
        claim = _claim_from_body(body, binding, command, observed_at_epoch)
        return validate_new_authority_claim(
            binding=binding,
            candidate=claim,
            durable_claims=durable_claims,
            observed_at_epoch=observed_at_epoch,
            expected_prior_journal_head_fingerprint=(
                expected_prior_journal_head_fingerprint
            ),
        )
    except ProductionAuthorityEnvelopeError:
        raise
    except Exception:
        raise ProductionAuthorityEnvelopeError() from None


def _decode_envelope(encoded):
    if type(encoded) is not str or not 1 <= len(encoded) <= _MAX_ENCODED_BYTES:
        raise ProductionAuthorityEnvelopeError()
    try:
        payload = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        raise ProductionAuthorityEnvelopeError() from None
    source = strict_json_object(payload, code=_ERROR)
    if (
        canonical_json(source) != payload
        or set(source) != {*_BODY_FIELDS, "signature"}
    ):
        raise ProductionAuthorityEnvelopeError()
    _exact_body({name: source[name] for name in _BODY_FIELDS})
    return source


def _exact_body(value):
    if type(value) is not dict or set(value) != set(_BODY_FIELDS):
        raise ProductionAuthorityEnvelopeError()
    fingerprints = (
        value[name]
        for name in _BODY_FIELDS
        if name.endswith("fingerprint") or name == "envelope_nonce"
    )
    times = tuple(
        value[name]
        for name in ("issued_at_epoch", "not_before_epoch", "expires_at_epoch")
    )
    if (
        value["envelope_type"] != _TYPE
        or not all(is_fingerprint(item) for item in fingerprints)
        or any(type(item) is not int or item < 0 for item in times)
        or type(value["claim_sequence"]) is not int
        or value["claim_sequence"] < 1
        or any(
            type(value[name]) is not str
            for name in ("command", "domain", "operator_role", "public_key_role")
        )
    ):
        raise ProductionAuthorityEnvelopeError()
    return value


def _require_binding(body, binding, expected_command, expected_action):
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(expected_command) is not ProductionCommandV2
        or body["command"] != expected_command.value
    ):
        raise ProductionAuthorityEnvelopeError()
    domain = authority_domain_for_command_v2(expected_command)
    operator_role, key_role = _DOMAIN_ROLES[domain]
    if expected_action is None:
        expected_action = production_action_fingerprint_v2(
            binding, expected_command
        )
    if not is_fingerprint(expected_action):
        raise ProductionAuthorityEnvelopeError()
    expected = {
        "binding_fingerprint": binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        "operation_fingerprint": binding.operation_fingerprint,
        "domain": domain.value,
        "operator_role": operator_role.value,
        "operator_fingerprint": dict(binding.operator_role_fingerprints)[operator_role],
        "public_key_role": key_role.value,
        "action_fingerprint": expected_action,
    }
    if any(body[name] != value for name, value in expected.items()):
        raise ProductionAuthorityEnvelopeError()
    unsigned = {
        name: body[name]
        for name in _BODY_FIELDS
        if name != "authority_fingerprint"
    }
    authority = hashlib.sha256(
        b"r2-production-authority-v2\0" + canonical_json(unsigned)
    ).hexdigest()
    if body["authority_fingerprint"] != authority:
        raise ProductionAuthorityEnvelopeError()
    return expected_command


def _require_signature(signature_value, body, binding, command):
    try:
        signature = base64.b64decode(signature_value.encode("ascii"), validate=True)
        domain = authority_domain_for_command_v2(command)
        key_role = _DOMAIN_ROLES[domain][1]
        public_key = dict(binding.verification_public_keys)[key_role]
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            production_authority_message_v2(body),
        )
    except (AttributeError, TypeError, ValueError, InvalidSignature):
        raise ProductionAuthorityEnvelopeError() from None
    if (
        len(signature) != 64
        or base64.b64encode(signature).decode("ascii") != signature_value
    ):
        raise ProductionAuthorityEnvelopeError()


def _claim_from_body(body, binding, command, observed):
    return DurableAuthorityClaimV2.create(
        binding=binding,
        command=command,
        action_fingerprint=body["action_fingerprint"],
        authority_fingerprint=body["authority_fingerprint"],
        envelope_nonce=body["envelope_nonce"],
        journal_owner_fingerprint=body["journal_owner_fingerprint"],
        prior_journal_head_fingerprint=body["prior_journal_head_fingerprint"],
        claim_sequence=body["claim_sequence"],
        issued_at_epoch=body["issued_at_epoch"],
        not_before_epoch=body["not_before_epoch"],
        expires_at_epoch=body["expires_at_epoch"],
        claimed_at_epoch=observed,
    )
