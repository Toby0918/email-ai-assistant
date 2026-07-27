"""Fail-closed verification for a published synthetic journal chain."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._canonical import ZERO_FINGERPRINT
from .chain_reducer import ReducedChainState, reduce_records
from .durability import JournalMediumSnapshotV1
from .errors import JournalContractError
from .journal_record import JournalRecordV1
from .journal_types import JournalEventCode
from .operation_binding import JournalOperationBindingV1


CHAIN_ERROR = "JOURNAL_CHAIN_INVALID"


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedJournalChainV1:
    head_hash: str
    record_count: int
    forward_committed: int
    reverse_committed: int
    open_event: str | None
    open_direction: str | None
    open_step_code: str | None
    _records: tuple[JournalRecordV1, ...] = field(repr=False)
    _forward_intents: tuple[JournalRecordV1, ...] = field(repr=False)
    _forward_outcomes: tuple[str, ...] = field(repr=False)
    _active_intent: JournalRecordV1 | None = field(repr=False)
    _pending_record: JournalRecordV1 | None = field(repr=False)


def verify_synthetic_journal_snapshot(
    snapshot: object,
    *,
    binding: JournalOperationBindingV1,
) -> VerifiedJournalChainV1:
    """Return a closed verified projection or one fixed failure code."""
    try:
        return _verify_snapshot(snapshot, binding)
    except JournalContractError:
        raise JournalContractError(CHAIN_ERROR) from None
    except Exception:
        raise JournalContractError(CHAIN_ERROR) from None


def _verify_snapshot(
    snapshot: object,
    binding: JournalOperationBindingV1,
) -> VerifiedJournalChainV1:
    if type(snapshot) is not JournalMediumSnapshotV1:
        _invalid()
    _assert_binding(binding)
    records = tuple(
        JournalRecordV1.from_json(payload)
        for payload in snapshot.published_records
    )
    pending = tuple(
        JournalRecordV1.from_json(payload)
        for payload in snapshot.pending_records
    )
    _assert_durability(snapshot, records, pending)
    _assert_links_and_bindings(records, binding)
    state = reduce_records(records)
    chain = _project_chain(records, state, pending_record=None)
    if pending:
        validate_journal_candidate(
            chain,
            binding=binding,
            candidate=pending[0],
        )
    return _project_chain(
        records,
        state,
        pending_record=pending[0] if pending else None,
    )


def _assert_binding(binding: object) -> None:
    if type(binding) is not JournalOperationBindingV1:
        _invalid()
    JournalOperationBindingV1.from_mapping(binding.to_mapping())


def _assert_durability(
    snapshot: JournalMediumSnapshotV1,
    records: tuple[JournalRecordV1, ...],
    pending: tuple[JournalRecordV1, ...],
) -> None:
    hashes = tuple(record.record_hash for record in records)
    pending_hashes = tuple(record.record_hash for record in pending)
    stable_prefixes = {hashes, hashes[:-1]}
    allowed_pending_barriers = {
        hashes,
        (*pending_hashes, *hashes),
    }
    if (
        snapshot.published_barrier_hashes != hashes
        or snapshot.namespace_barrier_hashes != hashes
        or snapshot.stable_reread_hashes not in stable_prefixes
        or snapshot.pending_barrier_hashes not in allowed_pending_barriers
        or len(pending) > 1
    ):
        _invalid()


def validate_journal_candidate(
    chain: object,
    *,
    binding: JournalOperationBindingV1,
    candidate: JournalRecordV1,
) -> None:
    if (
        type(chain) is not VerifiedJournalChainV1
        or type(candidate) is not JournalRecordV1
    ):
        _invalid()
    records = (*chain._records, candidate)
    _assert_links_and_bindings(records, binding)
    reduce_records(records)


def active_observed_record(
    chain: VerifiedJournalChainV1,
) -> JournalRecordV1 | None:
    if (
        type(chain) is not VerifiedJournalChainV1
        or chain._active_intent is None
    ):
        return None
    for record in reversed(chain._records):
        if record.sequence <= chain._active_intent.sequence:
            break
        if record.event_code == JournalEventCode.EFFECT_OBSERVED.value:
            return record
    return None


def _assert_links_and_bindings(
    records: tuple[JournalRecordV1, ...],
    binding: JournalOperationBindingV1,
) -> None:
    previous = ZERO_FINGERPRINT
    for expected_sequence, record in enumerate(records, start=1):
        if (
            record.sequence != expected_sequence
            or record.previous_record_hash != previous
            or not _matches_binding(record, binding)
        ):
            _invalid()
        previous = record.record_hash


def _matches_binding(
    record: JournalRecordV1,
    binding: JournalOperationBindingV1,
) -> bool:
    return (
        record.governing_master_commit == binding.governing_master_commit
        and record.operation_fingerprint == binding.operation_fingerprint
        and record.profile_fingerprint == binding.profile_fingerprint
        and record.forward_authorization_fingerprint
        == binding.forward_authorization_fingerprint
        and record.recovery_authorization_fingerprint
        == binding.recovery_authorization_fingerprint
        and record.owner_fingerprint == binding.owner_fingerprint
    )


def _project_chain(
    records: tuple[JournalRecordV1, ...],
    state: ReducedChainState,
    *,
    pending_record: JournalRecordV1 | None,
) -> VerifiedJournalChainV1:
    active = state.active_intent
    return VerifiedJournalChainV1(
        head_hash=records[-1].record_hash if records else ZERO_FINGERPRINT,
        record_count=len(records),
        forward_committed=len(state.forward_intents),
        reverse_committed=state.reverse_committed,
        open_event=state.previous_event,
        open_direction=active.direction if active else None,
        open_step_code=active.step_code if active else None,
        _records=records,
        _forward_intents=tuple(state.forward_intents),
        _forward_outcomes=tuple(state.forward_outcomes),
        _active_intent=active,
        _pending_record=pending_record,
    )


def _invalid() -> None:
    raise JournalContractError(CHAIN_ERROR)
