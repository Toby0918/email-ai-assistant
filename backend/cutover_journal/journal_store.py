"""Create-only durable publication over the exact synthetic medium."""

from __future__ import annotations

from dataclasses import dataclass

from .durability import (
    SyntheticJournalMediumV1,
    _OwnerLeaseV1,
    protocol_for,
)
from .effect_permit import (
    DurableRecordPermitV1,
    _new_permit,
    _PermitIssuanceV1,
)
from .errors import JournalContractError
from .journal_record import JournalRecordV1
from .journal_types import JournalEventCode
from .operation_binding import JournalOperationBindingV1
from .store_support import (
    binding_is_intact,
    durable_prefix_snapshot,
    ensure_published_head_stable,
    record_matches_binding,
)


@dataclass(slots=True, init=False, repr=False)
class DurableJournalStore:
    _medium: SyntheticJournalMediumV1
    _binding: JournalOperationBindingV1
    _owner_fingerprint: str
    _owner_lease: _OwnerLeaseV1
    _permit_scope_tokens: dict[tuple[str, str], object]
    _permit_tokens: dict[object, _PermitIssuanceV1]
    _active_permit_tokens: dict[object, _PermitIssuanceV1]
    _closed: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("DurableJournalStore requires begin_synthetic()")

    @classmethod
    def begin_synthetic(
        cls,
        *,
        medium: SyntheticJournalMediumV1,
        binding: JournalOperationBindingV1,
    ) -> DurableJournalStore:
        if type(medium) is not SyntheticJournalMediumV1:
            raise JournalContractError("JOURNAL_MEDIUM_INVALID")
        if not binding_is_intact(binding):
            raise JournalContractError("JOURNAL_BINDING_INVALID")
        owner_fingerprint = binding.owner_fingerprint
        owner_lease = medium._claim_owner(owner_fingerprint)
        snapshot = medium.snapshot()
        if snapshot.pending_records or snapshot.published_records:
            medium._release_owner(owner_lease)
            raise JournalContractError("JOURNAL_NOT_EMPTY")
        store = object.__new__(cls)
        store._medium = medium
        store._binding = binding
        store._owner_fingerprint = owner_fingerprint
        store._owner_lease = owner_lease
        store._permit_scope_tokens = {}
        store._permit_tokens = {}
        store._active_permit_tokens = {}
        store._closed = False
        return store

    @classmethod
    def recover_synthetic(
        cls,
        *,
        medium: SyntheticJournalMediumV1,
        binding: JournalOperationBindingV1,
    ) -> DurableJournalStore:
        if type(medium) is not SyntheticJournalMediumV1:
            raise JournalContractError("JOURNAL_MEDIUM_INVALID")
        if not binding_is_intact(binding):
            raise JournalContractError("JOURNAL_BINDING_INVALID")
        owner_fingerprint = binding.owner_fingerprint
        owner_lease = medium._claim_owner(owner_fingerprint)
        try:
            from .journal_chain import verify_synthetic_journal_snapshot

            verify_synthetic_journal_snapshot(
                medium.snapshot(),
                binding=binding,
            )
        except JournalContractError:
            medium._release_owner(owner_lease)
            raise
        store = object.__new__(cls)
        store._medium = medium
        store._binding = binding
        store._owner_fingerprint = owner_fingerprint
        store._owner_lease = owner_lease
        store._permit_scope_tokens = {}
        store._permit_tokens = {}
        store._active_permit_tokens = {}
        store._closed = False
        return store

    def append_record(
        self, record: JournalRecordV1
    ) -> DurableRecordPermitV1:
        claim = self._medium._claim_operation()
        try:
            return self._append_record(record)
        finally:
            self._medium._release_operation(claim)

    def _append_record(
        self, record: JournalRecordV1
    ) -> DurableRecordPermitV1:
        self._assert_record_context(record)
        ensure_published_head_stable(self._medium, self._binding)
        append_mode = self._assert_record(record)
        if append_mode == "DURABLE_RETRY":
            self._medium._stable_reread(record)
            return self._permit_for(record, record.record_hash)
        protocol = protocol_for(self._medium.platform)
        self._medium._write_pending(record)
        self._medium._flush_pending(record, protocol)
        self._medium._publish_no_replace(record)
        self._medium._flush_published(record, protocol)
        self._medium._flush_namespace(record, protocol)
        self._medium._stable_reread(record)
        return self._permit_for(record, record.record_hash)

    def close(self) -> None:
        if self._closed:
            return
        self._medium._release_owner(self._owner_lease)
        self._closed = True

    def _durable_permit_for(
        self, record: JournalRecordV1
    ) -> DurableRecordPermitV1:
        claim = self._medium._claim_operation()
        try:
            return self._current_durable_permit(record)
        finally:
            self._medium._release_operation(claim)

    def _current_durable_permit(
        self, record: JournalRecordV1
    ) -> DurableRecordPermitV1:
        self._assert_record_context(record)
        ensure_published_head_stable(self._medium, self._binding)
        from .journal_chain import (
            active_observed_record,
            verify_synthetic_journal_snapshot,
        )

        snapshot = self._medium.snapshot()
        chain = verify_synthetic_journal_snapshot(
            snapshot, binding=self._binding
        )
        last = chain._records[-1] if chain._records else None
        observed = active_observed_record(chain)
        if (
            chain._active_intent is None
            or chain._active_intent.record_hash != record.record_hash
            or chain._pending_record is not None
            or last is None
            or last.event_code
            not in {
                JournalEventCode.INTENT.value,
                JournalEventCode.RESUME_BOUND.value,
            }
            or observed is not None
            or record.to_canonical_json() not in snapshot.published_records
            or record.record_hash not in snapshot.namespace_barrier_hashes
            or chain.head_hash not in snapshot.stable_reread_hashes
        ):
            raise JournalContractError("JOURNAL_EFFECT_PERMIT_INVALID")
        if record.record_hash not in snapshot.stable_reread_hashes:
            self._medium._stable_reread(record)
        return self._permit_for(record, chain.head_hash)

    def _permit_for(
        self,
        record: JournalRecordV1,
        authorizing_head_hash: str,
    ) -> DurableRecordPermitV1:
        key = (record.record_hash, authorizing_head_hash)
        token = self._permit_scope_tokens.get(key)
        if token is None:
            token = object()
            issuance = _PermitIssuanceV1(
                intent_record_hash=record.record_hash,
                authorizing_head_hash=authorizing_head_hash,
                owner_fingerprint=record.owner_fingerprint,
            )
            self._permit_scope_tokens[key] = token
            self._permit_tokens[token] = issuance
            self._active_permit_tokens[token] = issuance
        return _new_permit(self, token)

    def _assert_record(self, record: JournalRecordV1) -> str:
        self._assert_record_context(record)
        snapshot = self._medium.snapshot()
        if (
            snapshot.published_records
            and snapshot.published_records[-1]
            == record.to_canonical_json()
            and record.sequence == len(snapshot.published_records)
        ):
            return self._assert_exact_retry(snapshot, record)
        from .journal_chain import (
            validate_journal_candidate,
            verify_synthetic_journal_snapshot,
        )

        chain = verify_synthetic_journal_snapshot(
            snapshot,
            binding=self._binding,
        )
        expected_sequence = len(snapshot.published_records) + 1
        previous_hash = chain.head_hash
        if (
            record.sequence != expected_sequence
            or record.previous_record_hash != previous_hash
        ):
            raise JournalContractError("JOURNAL_SEQUENCE_INVALID")
        validate_journal_candidate(
            chain,
            binding=self._binding,
            candidate=record,
        )
        return "NEW"

    def _assert_record_context(self, record: JournalRecordV1) -> None:
        if self._closed or type(record) is not JournalRecordV1:
            raise JournalContractError("JOURNAL_STORE_INVALID")
        JournalRecordV1.from_mapping(record.to_mapping())
        self._medium._assert_owner(self._owner_lease)
        if record.owner_fingerprint != self._owner_fingerprint:
            raise JournalContractError("JOURNAL_OWNER_INVALID")
        if not record_matches_binding(record, self._binding):
            raise JournalContractError("JOURNAL_BINDING_INVALID")

    def _assert_exact_retry(
        self,
        snapshot,
        record: JournalRecordV1,
    ) -> str:
        from .journal_chain import (
            validate_journal_candidate,
            verify_synthetic_journal_snapshot,
        )

        if (
            snapshot.namespace_barrier_hashes
            and snapshot.namespace_barrier_hashes[-1] == record.record_hash
        ):
            chain = verify_synthetic_journal_snapshot(
                snapshot,
                binding=self._binding,
            )
            if chain.head_hash != record.record_hash:
                raise JournalContractError("JOURNAL_CHAIN_INVALID")
            return "DURABLE_RETRY"
        prefix = durable_prefix_snapshot(snapshot, record)
        chain = verify_synthetic_journal_snapshot(
            prefix,
            binding=self._binding,
        )
        validate_journal_candidate(
            chain,
            binding=self._binding,
            candidate=record,
        )
        return "INCOMPLETE_RETRY"
