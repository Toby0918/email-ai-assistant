"""Code-fixed public verification context for dormant pre-#39 executables."""

from __future__ import annotations

from dataclasses import dataclass

from backend.cutover_composition_contracts import UNBOUND_FINGERPRINT
from backend.cutover_composition_contracts.canonical import is_fingerprint


_OBSERVED_AT = 1_900_000_000
_PROFILE = "ceb500026912924e3b3b1a946c2d968389d329794d99c5bbecec78539ade435e"
_MASTER = "4dd5183c7cb2731f519b0516516d9c0eb4490804"
_OPERATOR = "000000000000000000000000000000000000000000000000000000000000000c"
PREFLIGHT_OPERATION = "0000000000000000000000000000000000000000000000000000000000001bbc"
EVIDENCE_OPERATION = "0000000000000000000000000000000000000000000000000000000000001c20"
TRANSACTION_OPERATION = "0000000000000000000000000000000000000000000000000000000000001c84"
TRANSACTION_BINDING = "90cdb45bb8aeae7014c610517fa37090378d8e0ada8004e0bd1ca9795c1727b6"
TRANSACTION_OWNER = "0000000000000000000000000000000000000000000000000000000000001c85"
TRANSACTION_HEAD = "0000000000000000000000000000000000000000000000000000000000001c86"
TRANSACTION_PLAN = "0000000000000000000000000000000000000000000000000000000000001c87"
PREFLIGHT_PUBLIC_KEY = bytes.fromhex(
    "19219234c71bc9a8af2a7bdc11d97bdfd339736655f1563cc6feacd3ded2400d"
)
EVIDENCE_PUBLIC_KEY = bytes.fromhex(
    "ed67534bc3ae79397fc791530aacab71303d20a07c576c24d4c359c5cc02429d"
)
EXECUTION_PUBLIC_KEY = bytes.fromhex(
    "1cc78ad44a27bdb6b606e8ce024333e2cb82655df2b1d2b56f7acf336b6dea1b"
)
RECOVERY_PUBLIC_KEY = bytes.fromhex(
    "e411c6cc5d4a29318a914ddea3dd52b5ca59f7cca78a4d428df004f4507e65bf"
)


@dataclass(frozen=True, slots=True)
class DormantProfileBindingV1:
    profile_fingerprint: str
    governing_master_commit: str
    operator_fingerprint: str

    def __post_init__(self) -> None:
        if (
            not is_fingerprint(self.profile_fingerprint)
            or len(self.governing_master_commit) != 40
            or not is_fingerprint(self.operator_fingerprint)
        ):
            raise ValueError("R2_DORMANT_PROFILE_BINDING_INVALID")


DORMANT_PROFILE = DormantProfileBindingV1(_PROFILE, _MASTER, _OPERATOR)
_CLAIMED_ENVELOPES: set[str] = set()
_CLAIMED_CRASH_NONCES: set[str] = set()


def observed_at_epoch() -> int:
    return _OBSERVED_AT


def claim_envelope_nonce(nonce: str) -> bool:
    return _claim_once(_CLAIMED_ENVELOPES, nonce)


def claim_crash_nonce(nonce: str) -> bool:
    return _claim_once(_CLAIMED_CRASH_NONCES, nonce)


def expected_transaction_context(verb, context):
    crash_nonce = context.get("crash_nonce")
    expected = {
        "context_type": "R2TransactionAuthorizationContextV1",
        "approved_binding_fingerprint": TRANSACTION_BINDING,
        "journal_owner_fingerprint": TRANSACTION_OWNER,
        "journal_head_fingerprint": TRANSACTION_HEAD,
        "remaining_plan_fingerprint": (
            TRANSACTION_PLAN if verb == "rollback" else UNBOUND_FINGERPRINT
        ),
        "boundary_epoch": _OBSERVED_AT,
        "crash_nonce": crash_nonce,
    }
    if not is_fingerprint(crash_nonce) or context != expected:
        raise ValueError("R2_DORMANT_TRANSACTION_CONTEXT_INVALID")
    return expected


def _claim_once(claimed, nonce):
    if not is_fingerprint(nonce) or nonce in claimed:
        return False
    claimed.add(nonce)
    return True
