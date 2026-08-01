"""Bounded Ed25519 verification for hidden single-use envelopes."""

from __future__ import annotations

import base64
from enum import Enum
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.cutover_composition_contracts.canonical import (
    canonical_json,
    is_fingerprint,
    strict_json_object,
)
from backend.cutover_contracts import (
    AuthorizationValidationStatus,
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    EvidencePublicationAuthorizationV1,
    RealPreflightAuthorizationV1,
    RecoveryAuthorizationV1,
    validate_real_host_authorization,
)


_ERROR = "R2_AUTHORIZATION_ENVELOPE_REJECTED"
_REPLAY = "R2_AUTHORIZATION_ENVELOPE_REPLAYED"
_TYPE = "R2OperatorAuthorizationEnvelopeV1"
_MAX_ENCODED_BYTES = 65_536
_BASE_BODY_KEYS = ("envelope_type", "domain", "nonce", "authorization")


class AuthorizationEnvelopeDomain(str, Enum):
    PREFLIGHT = "preflight"
    EVIDENCE = "evidence"
    EXECUTION = "execution"
    RECOVERY = "recovery"


_DOMAIN_AUTHORIZATIONS = {
    AuthorizationEnvelopeDomain.PREFLIGHT: (
        RealPreflightAuthorizationV1,
        "real_preflight",
    ),
    AuthorizationEnvelopeDomain.EVIDENCE: (
        EvidencePublicationAuthorizationV1,
        "evidence_publication",
    ),
    AuthorizationEnvelopeDomain.EXECUTION: (
        CutoverExecutionAuthorizationV1,
        "cutover_execution",
    ),
    AuthorizationEnvelopeDomain.RECOVERY: (
        RecoveryAuthorizationV1,
        "recovery",
    ),
}


class AuthorizationEnvelopeError(ValueError):
    def __init__(self) -> None:
        super().__init__(_ERROR)

    def __repr__(self) -> str:
        return f"AuthorizationEnvelopeError({_ERROR!r})"


class AuthorizationEnvelopeReplay(AuthorizationEnvelopeError):
    def __init__(self) -> None:
        ValueError.__init__(self, _REPLAY)

    def __repr__(self) -> str:
        return f"AuthorizationEnvelopeReplay({_REPLAY!r})"


def authorization_envelope_message(body: object) -> bytes:
    source = _exact_body(body)
    return b"r2-operator-authorization-envelope-v1\0" + canonical_json(source)


def decode_authorization_envelope_context(encoded: object) -> dict[str, object]:
    try:
        source = _decode_envelope(encoded)
        context = source.get("context")
        if type(context) is not dict:
            raise AuthorizationEnvelopeError
        return dict(context)
    except AuthorizationEnvelopeError:
        raise
    except Exception:
        raise AuthorizationEnvelopeError from None


def verify_authorization_envelope(
    encoded: object,
    *,
    expected_domain: AuthorizationEnvelopeDomain,
    verification_public_key: bytes,
    profile: CutoverProfileV1,
    operation_fingerprint: str,
    expected_phase: str,
    observed_at_epoch: int,
    claim_nonce: Callable[[str], bool],
    authorization_type: type = RealPreflightAuthorizationV1,
    expected_operation: str = "real_preflight",
    expected_context: dict[str, object] | None = None,
) -> object:
    try:
        return _verify_authorization(
            encoded,
            expected_domain,
            verification_public_key,
            profile,
            operation_fingerprint,
            expected_phase,
            observed_at_epoch,
            claim_nonce,
            authorization_type,
            expected_operation,
            expected_context,
        )
    except AuthorizationEnvelopeReplay:
        raise
    except Exception:
        raise AuthorizationEnvelopeError from None


def _verify_authorization(
    encoded,
    domain,
    public_key,
    profile,
    operation_fingerprint,
    phase,
    observed,
    claim_nonce,
    authorization_type,
    operation,
    expected_context,
):
    source = _decode_envelope(encoded)
    body = {
        name: source[name] for name in source if name != "signature"
    }
    if body.get("context") != expected_context:
        raise AuthorizationEnvelopeError
    _require_domain_and_signature(source, body, domain, public_key)
    _require_domain_authorization_type(domain, authorization_type, operation)
    authorization = authorization_type.from_mapping(body["authorization"])
    _require_authorization_binding(
        authorization,
        profile,
        operation_fingerprint,
        phase,
        observed,
        operation,
    )
    if claim_nonce(body["nonce"]) is not True:
        raise AuthorizationEnvelopeReplay
    return authorization


def _decode_envelope(encoded: object) -> dict[str, object]:
    if type(encoded) is not str or not 1 <= len(encoded) <= _MAX_ENCODED_BYTES:
        raise AuthorizationEnvelopeError
    try:
        payload = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        raise AuthorizationEnvelopeError from None
    source = strict_json_object(payload, code=_ERROR)
    if canonical_json(source) != payload:
        raise AuthorizationEnvelopeError
    if "signature" not in source:
        raise AuthorizationEnvelopeError
    _exact_body(
        {name: source[name] for name in source if name != "signature"}
    )
    return source


def _exact_body(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise AuthorizationEnvelopeError
    keys = set(value)
    valid_keys = (
        keys == set(_BASE_BODY_KEYS)
        or keys == {*_BASE_BODY_KEYS, "context"}
    )
    if not valid_keys:
        raise AuthorizationEnvelopeError
    domain = value["domain"]
    if (
        value["envelope_type"] != _TYPE
        or type(domain) is not str
        or domain not in {item.value for item in AuthorizationEnvelopeDomain}
        or not is_fingerprint(value["nonce"])
        or type(value["authorization"]) is not dict
        or ("context" in value and type(value["context"]) is not dict)
    ):
        raise AuthorizationEnvelopeError
    return value


def _require_domain_and_signature(source, body, domain, public_key) -> None:
    if (
        type(domain) is not AuthorizationEnvelopeDomain
        or body["domain"] != domain.value
        or type(public_key) is not bytes
        or len(public_key) != 32
    ):
        raise AuthorizationEnvelopeError
    signature = _decode_signature(source["signature"])
    try:
        key = Ed25519PublicKey.from_public_bytes(public_key)
        key.verify(signature, authorization_envelope_message(body))
    except (TypeError, ValueError, InvalidSignature):
        raise AuthorizationEnvelopeError from None


def _decode_signature(value: object) -> bytes:
    if type(value) is not str or len(value) != 88:
        raise AuthorizationEnvelopeError
    try:
        signature = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        raise AuthorizationEnvelopeError from None
    if len(signature) != 64 or base64.b64encode(signature).decode("ascii") != value:
        raise AuthorizationEnvelopeError
    return signature


def _require_domain_authorization_type(domain, kind, operation) -> None:
    expected = _DOMAIN_AUTHORIZATIONS.get(domain)
    if expected != (kind, operation):
        raise AuthorizationEnvelopeError


def _require_authorization_binding(
    authorization,
    profile,
    operation_fingerprint,
    phase,
    observed,
    operation,
) -> None:
    result = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation=operation,
        expected_operation_fingerprint=operation_fingerprint,
        expected_phase=phase,
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=observed,
    )
    if result.status is not AuthorizationValidationStatus.AUTHORIZED:
        raise AuthorizationEnvelopeError
