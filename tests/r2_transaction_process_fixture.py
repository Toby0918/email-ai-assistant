"""Fixed signed execution fixture for the Issue #73 process proof."""

from __future__ import annotations

import base64
import hashlib
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.cutover_composition_contracts import (
    ApprovedCutoverBindingV1,
    UNBOUND_FINGERPRINT,
)
from backend.r2_operator_process import authorization_envelope_message
from backend.r2_transaction_process.testing import SyntheticTransactionProcess
from tests.cutover_composition_fixtures import synthetic_context
from tests.cutover_contract_fixtures import opaque_fingerprint


OBSERVED_AT = 1_900_000_000
OPERATION = opaque_fingerprint(7300)
OWNER = opaque_fingerprint(7301)
HEAD = opaque_fingerprint(7302)
PLAN = opaque_fingerprint(7303)
_EXECUTION_SEED = hashlib.sha256(b"issue-73-execution-test-key").digest()
_RECOVERY_SEED = hashlib.sha256(b"issue-73-recovery-test-key").digest()


def create_synthetic_process(action, *, verb="execute") -> SyntheticTransactionProcess:
    profile, sequence, _binding = synthetic_context(
        operation_fingerprint=OPERATION
    )
    binding = ApprovedCutoverBindingV1.create(
        profile=profile,
        operation_fingerprint=OPERATION,
        authorization_sequence=sequence,
    )
    return SyntheticTransactionProcess.create(
        profile=profile,
        binding=binding,
        operation_fingerprint=OPERATION,
        journal_owner_fingerprint=OWNER,
        current_journal_head=lambda: HEAD,
        remaining_reverse_plan=lambda: PLAN,
        observed_at_epoch=lambda: OBSERVED_AT,
        execution_public_key=_public_key(_EXECUTION_SEED),
        recovery_public_key=_public_key(_RECOVERY_SEED),
        execute=action if verb == "execute" else (lambda: 0),
        resume=lambda: 0,
        rollback=action if verb == "rollback" else (lambda: 0),
        real_locked=False,
    )


def valid_hidden_envelope(verb="execute") -> str:
    profile, sequence, _binding = synthetic_context(
        operation_fingerprint=OPERATION
    )
    binding = ApprovedCutoverBindingV1.create(
        profile=profile,
        operation_fingerprint=OPERATION,
        authorization_sequence=sequence,
    )
    recovery = verb == "rollback"
    authorization_body = {
        "authorization_type": (
            "RecoveryAuthorizationV1"
            if recovery
            else "CutoverExecutionAuthorizationV1"
        ),
        "operation": "recovery" if recovery else "cutover_execution",
        "operation_fingerprint": OPERATION,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_commit": profile.governing_master_commit,
        "operator_fingerprint": profile.operator_fingerprint,
        "phase": verb,
        "issued_at_epoch": OBSERVED_AT - 20,
        "not_before_epoch": OBSERVED_AT - 10,
        "expires_at_epoch": OBSERVED_AT + 60,
    }
    body = {
        "envelope_type": "R2OperatorAuthorizationEnvelopeV1",
        "domain": "recovery" if recovery else "execution",
        "nonce": opaque_fingerprint(7398 if recovery else 7399),
        "authorization": {
            **authorization_body,
            "authorization_fingerprint": hashlib.sha256(
                _canonical_json(authorization_body)
            ).hexdigest(),
        },
        "context": {
            "context_type": "R2TransactionAuthorizationContextV1",
            "approved_binding_fingerprint": binding.binding_fingerprint,
            "journal_owner_fingerprint": OWNER,
            "journal_head_fingerprint": HEAD,
            "remaining_plan_fingerprint": PLAN if recovery else UNBOUND_FINGERPRINT,
            "boundary_epoch": OBSERVED_AT,
            "crash_nonce": opaque_fingerprint(7391 if recovery else 7390),
        },
    }
    key = Ed25519PrivateKey.from_private_bytes(
        _RECOVERY_SEED if recovery else _EXECUTION_SEED
    )
    payload = _canonical_json(
        {
            **body,
            "signature": base64.b64encode(
                key.sign(authorization_envelope_message(body))
            ).decode("ascii"),
        }
    )
    return base64.b64encode(payload).decode("ascii")


def _public_key(seed: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
