"""Fixed synthetic evidence process and signing fixture."""

from __future__ import annotations

import base64
import hashlib
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.cutover_composition_contracts import ApprovedCutoverBindingV1
from backend.r2_evidence_process.testing import SyntheticEvidenceProcess
from backend.r2_operator_process import authorization_envelope_message
from tests.cutover_composition_fixtures import synthetic_context
from tests.cutover_contract_fixtures import opaque_fingerprint


OBSERVED_AT = 1_900_000_000
OPERATION = opaque_fingerprint(7200)
CONFIRMED_REVIEW = opaque_fingerprint(7201)
_PRIVATE_SEED = hashlib.sha256(
    b"issue-72-test-owned-evidence-ed25519-key"
).digest()


def create_synthetic_process(publish) -> SyntheticEvidenceProcess:
    profile, sequence, _binding = synthetic_context(
        operation_fingerprint=OPERATION
    )
    binding = ApprovedCutoverBindingV1.create(
        profile=profile,
        operation_fingerprint=OPERATION,
        authorization_sequence=sequence,
    )
    public_key = Ed25519PrivateKey.from_private_bytes(
        _PRIVATE_SEED
    ).public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return SyntheticEvidenceProcess.create(
        profile=profile,
        binding=binding,
        operation_fingerprint=OPERATION,
        confirmed_review_fingerprint=CONFIRMED_REVIEW,
        expected_review_fingerprint=CONFIRMED_REVIEW,
        verification_public_key=public_key,
        observed_at_epoch=lambda: OBSERVED_AT,
        publish_confirmed_review=publish,
        real_locked=False,
    )


def valid_hidden_envelope() -> str:
    profile, _sequence, _binding = synthetic_context(
        operation_fingerprint=OPERATION
    )
    authorization_body = {
        "authorization_type": "EvidencePublicationAuthorizationV1",
        "operation": "evidence_publication",
        "operation_fingerprint": OPERATION,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_commit": profile.governing_master_commit,
        "operator_fingerprint": profile.operator_fingerprint,
        "phase": "evidence_publication",
        "issued_at_epoch": OBSERVED_AT - 20,
        "not_before_epoch": OBSERVED_AT - 10,
        "expires_at_epoch": OBSERVED_AT + 60,
    }
    authorization = {
        **authorization_body,
        "authorization_fingerprint": hashlib.sha256(
            _canonical_json(authorization_body)
        ).hexdigest(),
    }
    body = {
        "envelope_type": "R2OperatorAuthorizationEnvelopeV1",
        "domain": "evidence",
        "nonce": opaque_fingerprint(7299),
        "authorization": authorization,
    }
    key = Ed25519PrivateKey.from_private_bytes(_PRIVATE_SEED)
    payload = _canonical_json(
        {
            **body,
            "signature": base64.b64encode(
                key.sign(authorization_envelope_message(body))
            ).decode("ascii"),
        }
    )
    return base64.b64encode(payload).decode("ascii")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
