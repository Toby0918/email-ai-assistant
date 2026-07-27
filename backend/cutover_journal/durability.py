"""Exact in-memory durability model; no host filesystem adapter exists."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ._canonical import is_opaque_fingerprint
from .errors import JournalContractError
from .journal_record import JournalRecordV1


class DurabilityPlatform(str, Enum):
    WINDOWS = "WINDOWS"
    LINUX = "LINUX"


class DurabilityCutPoint(str, Enum):
    NONE = "NONE"
    BEFORE_PENDING_WRITE = "BEFORE_PENDING_WRITE"
    DURING_PENDING_WRITE = "DURING_PENDING_WRITE"
    AFTER_PENDING_WRITE = "AFTER_PENDING_WRITE"
    AFTER_PENDING_FILE_BARRIER = "AFTER_PENDING_FILE_BARRIER"
    AFTER_NO_REPLACE_PUBLICATION = "AFTER_NO_REPLACE_PUBLICATION"
    AFTER_PUBLISHED_FILE_BARRIER = "AFTER_PUBLISHED_FILE_BARRIER"
    AFTER_NAMESPACE_BARRIER = "AFTER_NAMESPACE_BARRIER"
    AFTER_FINAL_STABLE_REREAD = "AFTER_FINAL_STABLE_REREAD"


@dataclass(frozen=True, slots=True)
class DurabilityProtocolV1:
    pending_file_barrier: str
    published_file_barrier: str
    namespace_barrier: str


@dataclass(slots=True, repr=False)
class _OwnerLeaseV1:
    owner_fingerprint: str
    generation: int
    active: bool = True


@dataclass(frozen=True, slots=True, repr=False)
class JournalMediumSnapshotV1:
    pending_records: tuple[bytes, ...]
    published_records: tuple[bytes, ...]
    pending_barrier_hashes: tuple[str, ...]
    published_barrier_hashes: tuple[str, ...]
    namespace_barrier_hashes: tuple[str, ...]
    stable_reread_hashes: tuple[str, ...]
    trace: tuple[str, ...]


@dataclass(slots=True, init=False, repr=False)
class SyntheticJournalMediumV1:
    platform: DurabilityPlatform
    cut_point: DurabilityCutPoint
    _operation_token: object
    _operation_gate: dict[object, object]
    _active_lease: _OwnerLeaseV1 | None = field(default=None)
    _lease_generation: int = field(default=0)
    _pending: dict[int, bytes] = field(default_factory=dict)
    _published: dict[int, bytes] = field(default_factory=dict)
    _pending_barriers: dict[int, str] = field(default_factory=dict)
    _published_barriers: dict[int, str] = field(default_factory=dict)
    _namespace_barriers: dict[int, str] = field(default_factory=dict)
    _stable_rereads: dict[int, str] = field(default_factory=dict)
    _trace: list[str] = field(default_factory=list)
    _cut_fired: bool = field(default=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticJournalMediumV1 requires empty()")

    @classmethod
    def empty(
        cls,
        *,
        platform: DurabilityPlatform,
        cut_point: DurabilityCutPoint = DurabilityCutPoint.NONE,
    ) -> SyntheticJournalMediumV1:
        if type(platform) is not DurabilityPlatform:
            raise JournalContractError("JOURNAL_MEDIUM_INVALID")
        if type(cut_point) is not DurabilityCutPoint:
            raise JournalContractError("JOURNAL_MEDIUM_INVALID")
        medium = object.__new__(cls)
        medium.platform = platform
        medium.cut_point = cut_point
        medium._operation_token = object()
        medium._operation_gate = {
            medium._operation_token: medium._operation_token
        }
        medium._active_lease = None
        medium._lease_generation = 0
        medium._pending = {}
        medium._published = {}
        medium._pending_barriers = {}
        medium._published_barriers = {}
        medium._namespace_barriers = {}
        medium._stable_rereads = {}
        medium._trace = []
        medium._cut_fired = False
        return medium

    def snapshot(self) -> JournalMediumSnapshotV1:
        sequences = tuple(sorted(self._published))
        pending_sequences = tuple(sorted(self._pending))
        return JournalMediumSnapshotV1(
            pending_records=tuple(
                self._pending[sequence] for sequence in pending_sequences
            ),
            published_records=tuple(
                self._published[sequence] for sequence in sequences
            ),
            pending_barrier_hashes=_ordered_hashes(
                self._pending_barriers, (*pending_sequences, *sequences)
            ),
            published_barrier_hashes=_ordered_hashes(
                self._published_barriers, sequences
            ),
            namespace_barrier_hashes=_ordered_hashes(
                self._namespace_barriers, sequences
            ),
            stable_reread_hashes=_ordered_hashes(
                self._stable_rereads, sequences
            ),
            trace=tuple(self._trace),
        )

    def simulate_restart(self) -> None:
        claim = self._claim_operation()
        try:
            if self._active_lease is not None:
                self._active_lease.active = False
            self._active_lease = None
            self.cut_point = DurabilityCutPoint.NONE
            self._cut_fired = False
        finally:
            self._release_operation(claim)

    def _claim_owner(self, owner_fingerprint: str) -> _OwnerLeaseV1:
        if not is_opaque_fingerprint(owner_fingerprint):
            raise JournalContractError("JOURNAL_OWNER_INVALID")
        claim = self._claim_operation()
        try:
            if self._active_lease is not None:
                raise JournalContractError("JOURNAL_OWNER_ACTIVE")
            self._lease_generation += 1
            lease = _OwnerLeaseV1(
                owner_fingerprint=owner_fingerprint,
                generation=self._lease_generation,
            )
            self._active_lease = lease
            return lease
        finally:
            self._release_operation(claim)

    def _release_owner(self, lease: _OwnerLeaseV1) -> None:
        claim = self._claim_operation()
        try:
            self._assert_owner(lease)
            lease.active = False
            self._active_lease = None
        finally:
            self._release_operation(claim)

    def _claim_operation(self) -> object:
        token = self._operation_token
        claim = self._operation_gate.pop(token, None)
        if claim is not token:
            raise JournalContractError("JOURNAL_MEDIUM_BUSY")
        return claim

    def _release_operation(self, claim: object) -> None:
        token = self._operation_token
        if claim is not token or token in self._operation_gate:
            raise JournalContractError("JOURNAL_MEDIUM_INVALID")
        self._operation_gate[token] = token

    def _assert_owner(self, lease: _OwnerLeaseV1) -> None:
        if (
            type(lease) is not _OwnerLeaseV1
            or not lease.active
            or self._active_lease is not lease
        ):
            raise JournalContractError("JOURNAL_OWNER_INVALID")

    def _write_pending(self, record: JournalRecordV1) -> None:
        self._maybe_crash(DurabilityCutPoint.BEFORE_PENDING_WRITE)
        payload = record.to_canonical_json()
        existing = self._pending.get(record.sequence)
        if existing is not None and existing != payload:
            raise JournalContractError("JOURNAL_PENDING_CONFLICT")
        if existing is None:
            self._pending[record.sequence] = payload
            self._trace.append("PENDING_WRITE")
        if self.cut_point is DurabilityCutPoint.DURING_PENDING_WRITE:
            self._pending[record.sequence] = payload[:-1]
        self._maybe_crash(DurabilityCutPoint.DURING_PENDING_WRITE)
        self._maybe_crash(DurabilityCutPoint.AFTER_PENDING_WRITE)

    def _flush_pending(
        self, record: JournalRecordV1, protocol: DurabilityProtocolV1
    ) -> None:
        self._require_pending(record)
        self._pending_barriers[record.sequence] = record.record_hash
        self._trace.append(protocol.pending_file_barrier)
        self._maybe_crash(DurabilityCutPoint.AFTER_PENDING_FILE_BARRIER)

    def _publish_no_replace(self, record: JournalRecordV1) -> None:
        self._require_pending(record)
        if self._pending_barriers.get(record.sequence) != record.record_hash:
            raise JournalContractError("JOURNAL_BARRIER_FAILED")
        payload = record.to_canonical_json()
        existing = self._published.get(record.sequence)
        if existing is not None and existing != payload:
            raise JournalContractError("JOURNAL_PUBLICATION_COLLISION")
        if existing is None:
            self._published[record.sequence] = payload
            self._trace.append("FINAL_NO_REPLACE_PUBLICATION")
        self._pending.pop(record.sequence, None)
        self._maybe_crash(DurabilityCutPoint.AFTER_NO_REPLACE_PUBLICATION)

    def _flush_published(
        self, record: JournalRecordV1, protocol: DurabilityProtocolV1
    ) -> None:
        self._require_published(record)
        self._published_barriers[record.sequence] = record.record_hash
        self._trace.append(protocol.published_file_barrier)
        self._maybe_crash(DurabilityCutPoint.AFTER_PUBLISHED_FILE_BARRIER)

    def _flush_namespace(
        self, record: JournalRecordV1, protocol: DurabilityProtocolV1
    ) -> None:
        if self._published_barriers.get(record.sequence) != record.record_hash:
            raise JournalContractError("JOURNAL_BARRIER_FAILED")
        self._namespace_barriers[record.sequence] = record.record_hash
        self._trace.append(protocol.namespace_barrier)
        self._maybe_crash(DurabilityCutPoint.AFTER_NAMESPACE_BARRIER)

    def _stable_reread(self, record: JournalRecordV1) -> None:
        self._require_published(record)
        if self._namespace_barriers.get(record.sequence) != record.record_hash:
            raise JournalContractError("JOURNAL_BARRIER_FAILED")
        self._stable_rereads[record.sequence] = record.record_hash
        self._trace.append("FINAL_STABLE_REREAD")
        self._maybe_crash(DurabilityCutPoint.AFTER_FINAL_STABLE_REREAD)

    def _require_pending(self, record: JournalRecordV1) -> None:
        if self._pending.get(record.sequence) != record.to_canonical_json():
            raise JournalContractError("JOURNAL_PENDING_CONFLICT")

    def _require_published(self, record: JournalRecordV1) -> None:
        if self._published.get(record.sequence) != record.to_canonical_json():
            raise JournalContractError("JOURNAL_PUBLICATION_COLLISION")

    def _maybe_crash(self, cut_point: DurabilityCutPoint) -> None:
        if self.cut_point is cut_point and not self._cut_fired:
            self._cut_fired = True
            raise JournalContractError("SYNTHETIC_CRASH")


def protocol_for(platform: DurabilityPlatform) -> DurabilityProtocolV1:
    if platform is DurabilityPlatform.WINDOWS:
        return DurabilityProtocolV1(
            pending_file_barrier="WINDOWS_PENDING_FILE_FLUSH",
            published_file_barrier="WINDOWS_PUBLISHED_FILE_FLUSH",
            namespace_barrier="WINDOWS_NAMESPACE_FLUSH",
        )
    if platform is DurabilityPlatform.LINUX:
        return DurabilityProtocolV1(
            pending_file_barrier="LINUX_PENDING_FILE_FSYNC",
            published_file_barrier="LINUX_PUBLISHED_FILE_FSYNC",
            namespace_barrier="LINUX_NAMESPACE_FSYNC",
        )
    raise JournalContractError("JOURNAL_MEDIUM_INVALID")


def _ordered_hashes(
    values: dict[int, str], sequences: tuple[int, ...]
) -> tuple[str, ...]:
    return tuple(
        values[sequence] for sequence in sequences if sequence in values
    )
