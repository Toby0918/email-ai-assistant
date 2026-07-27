"""Pure binding and incomplete-publication checks for the journal store."""

from __future__ import annotations

from .durability import (
    JournalMediumSnapshotV1,
    SyntheticJournalMediumV1,
)
from .errors import JournalContractError
from .journal_record import JournalRecordV1
from .operation_binding import JournalOperationBindingV1


def durable_prefix_snapshot(
    snapshot: JournalMediumSnapshotV1,
    record: JournalRecordV1,
) -> JournalMediumSnapshotV1:
    prefix_records = snapshot.published_records[:-1]
    prefix_hashes = tuple(
        JournalRecordV1.from_json(payload).record_hash
        for payload in prefix_records
    )
    candidate_hashes = (*prefix_hashes, record.record_hash)
    if (
        snapshot.namespace_barrier_hashes != prefix_hashes
        or snapshot.stable_reread_hashes != prefix_hashes
        or snapshot.published_barrier_hashes
        not in {prefix_hashes, candidate_hashes}
        or snapshot.pending_barrier_hashes != candidate_hashes
    ):
        raise JournalContractError("JOURNAL_CHAIN_INVALID")
    return JournalMediumSnapshotV1(
        pending_records=(),
        published_records=prefix_records,
        pending_barrier_hashes=prefix_hashes,
        published_barrier_hashes=prefix_hashes,
        namespace_barrier_hashes=prefix_hashes,
        stable_reread_hashes=prefix_hashes,
        trace=snapshot.trace,
    )


def ensure_published_head_stable(
    medium: SyntheticJournalMediumV1,
    binding: JournalOperationBindingV1,
) -> None:
    snapshot = medium.snapshot()
    if not snapshot.published_records:
        return
    records = tuple(
        JournalRecordV1.from_json(payload)
        for payload in snapshot.published_records
    )
    hashes = tuple(record.record_hash for record in records)
    if snapshot.stable_reread_hashes == hashes:
        return
    if (
        snapshot.namespace_barrier_hashes != hashes
        or snapshot.stable_reread_hashes != hashes[:-1]
    ):
        return
    from .journal_chain import verify_synthetic_journal_snapshot

    verify_synthetic_journal_snapshot(snapshot, binding=binding)
    medium._stable_reread(records[-1])
    verify_synthetic_journal_snapshot(
        medium.snapshot(),
        binding=binding,
    )


def binding_is_intact(binding: object) -> bool:
    if type(binding) is not JournalOperationBindingV1:
        return False
    try:
        JournalOperationBindingV1.from_mapping(binding.to_mapping())
    except JournalContractError:
        return False
    return True


def record_matches_binding(
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
    )
