"""Opaque, store-issued capabilities for one synthetic effect attempt."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import JournalContractError
from .journal_types import JournalEventCode


@dataclass(frozen=True, slots=True, repr=False)
class _PermitIssuanceV1:
    intent_record_hash: str
    authorizing_head_hash: str
    owner_fingerprint: str


@dataclass(frozen=True, slots=True, repr=False)
class _EffectClaimV1:
    medium: object
    operation_claim: object


class DurableRecordPermitV1:
    """Non-copyable view over one store-owned shared issuance."""

    __slots__ = ("_issuer", "_token")

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("durable permit is store-issued")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("durable permit is immutable")

    @property
    def record_hash(self) -> str:
        return _permit_metadata(self).intent_record_hash

    @property
    def owner_fingerprint(self) -> str:
        return _permit_metadata(self).owner_fingerprint

    def __copy__(self) -> DurableRecordPermitV1:
        raise TypeError("durable permit cannot be copied")

    def __deepcopy__(
        self, memo: dict[int, object]
    ) -> DurableRecordPermitV1:
        raise TypeError("durable permit cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("durable permit cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("durable permit cannot be serialized")

    def __getstate__(self) -> object:
        raise TypeError("durable permit cannot be serialized")


def _new_permit(
    issuer: object,
    token: object,
) -> DurableRecordPermitV1:
    permit = object.__new__(DurableRecordPermitV1)
    object.__setattr__(permit, "_issuer", issuer)
    object.__setattr__(permit, "_token", token)
    return permit


def _permit_metadata(
    permit: DurableRecordPermitV1,
) -> _PermitIssuanceV1:
    issuer = object.__getattribute__(permit, "_issuer")
    token = object.__getattribute__(permit, "_token")
    return issuer._permit_tokens[token]


def _consume_durable_permit(
    permit: object,
    *,
    intent: object,
    direction: str,
    step_code: str,
) -> _EffectClaimV1:
    from .journal_record import JournalRecordV1
    from .journal_store import DurableJournalStore

    if (
        type(permit) is not DurableRecordPermitV1
        or type(intent) is not JournalRecordV1
        or type(permit._issuer) is not DurableJournalStore
    ):
        raise JournalContractError("JOURNAL_EFFECT_PERMIT_INVALID")
    try:
        return _consume_from_store(
            permit._issuer,
            permit,
            intent=intent,
            direction=direction,
            step_code=step_code,
        )
    except JournalContractError:
        raise JournalContractError(
            "JOURNAL_EFFECT_PERMIT_INVALID"
        ) from None


def _consume_from_store(
    store: object,
    permit: DurableRecordPermitV1,
    *,
    intent: object,
    direction: str,
    step_code: str,
) -> _EffectClaimV1:
    operation_claim = store._medium._claim_operation()
    try:
        _claim_store_permit(
            store,
            permit,
            intent=intent,
            direction=direction,
            step_code=step_code,
        )
    except Exception:
        store._medium._release_operation(operation_claim)
        raise
    return _EffectClaimV1(store._medium, operation_claim)


def _claim_store_permit(
    store: object,
    permit: DurableRecordPermitV1,
    *,
    intent: object,
    direction: str,
    step_code: str,
) -> None:
    from .journal_chain import verify_synthetic_journal_snapshot

    store._assert_record_context(intent)
    token = permit._token
    issuance = store._permit_tokens.get(token)
    snapshot = store._medium.snapshot()
    chain = verify_synthetic_journal_snapshot(
        snapshot, binding=store._binding
    )
    if _invalid_claim(
        store, permit, issuance, chain, snapshot, intent, direction, step_code
    ):
        raise JournalContractError("JOURNAL_EFFECT_PERMIT_INVALID")
    claimed = store._active_permit_tokens.pop(token, None)
    if claimed is not issuance:
        raise JournalContractError("JOURNAL_EFFECT_PERMIT_INVALID")


def _invalid_claim(
    store: object,
    permit: DurableRecordPermitV1,
    issuance: object,
    chain: object,
    snapshot: object,
    intent: object,
    direction: str,
    step_code: str,
) -> bool:
    from .journal_chain import active_observed_record

    token = permit._token
    key = (intent.record_hash, chain.head_hash)
    return (
        permit._issuer is not store
        or issuance is None
        or store._permit_scope_tokens.get(key) is not token
        or issuance.intent_record_hash != intent.record_hash
        or issuance.authorizing_head_hash != chain.head_hash
        or issuance.owner_fingerprint != intent.owner_fingerprint
        or chain._active_intent is None
        or chain._active_intent.record_hash != intent.record_hash
        or active_observed_record(chain) is not None
        or chain._pending_record is not None
        or intent.to_canonical_json() not in snapshot.published_records
        or intent.record_hash not in snapshot.namespace_barrier_hashes
        or intent.record_hash not in snapshot.stable_reread_hashes
        or chain.head_hash not in snapshot.stable_reread_hashes
        or intent.event_code != JournalEventCode.INTENT.value
        or intent.direction != direction
        or intent.step_code != step_code
    )


def _release_effect_claim(claim: _EffectClaimV1) -> None:
    if type(claim) is not _EffectClaimV1:
        raise JournalContractError("JOURNAL_EFFECT_PERMIT_INVALID")
    claim.medium._release_operation(claim.operation_claim)
