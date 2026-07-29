"""Create-only content-free journal files inside the bound sandbox."""
from __future__ import annotations
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import RepositoryTransactionError
from .journal_chain import verify_journal_chain
from .journal_record import RepositoryJournalRecordV1
from .journal_types import (
    ForwardBoundary,
    RepositoryJournalDirection,
    RepositoryJournalEvent,
    RepositoryJournalOutcome,
    RepositoryMutationKind,
    ReverseBoundary,
)
from .scope_models import _SyntheticTransactionScope

_ZERO = "0" * 64
_MAX_RECORDS = 1_000


@dataclass(slots=True, init=False, repr=False)
class _RepositoryJournalStore:
    _scope: _SyntheticTransactionScope = field(repr=False)
    _root: Path = field(repr=False)
    _records: list[RepositoryJournalRecordV1] = field(repr=False)
    _authorization_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("repository journal requires bound scope")

    @classmethod
    def begin(
        cls, scope: object
    ) -> _RepositoryJournalStore:
        store = cls._new(scope)
        if any(store._root.iterdir()):
            _fail()
        return store

    @classmethod
    def open_verified(
        cls, scope: object
    ) -> _RepositoryJournalStore:
        store = cls._new(scope)
        store._records.extend(_load_records(store._root))
        _verify_chain(store._records, store)
        return store

    @classmethod
    def _new(cls, scope: object) -> _RepositoryJournalStore:
        if type(scope) is not _SyntheticTransactionScope:
            _fail()
        root = Path(scope.review.scenario.journal_root)
        if not root.is_dir() or root.is_symlink():
            _fail()
        value = object.__new__(cls)
        value._scope = scope
        value._root = root
        value._records = []
        value._authorization_fingerprint = _authorization_fingerprint(scope)
        return value

    def append_intent(
        self,
        *,
        direction: RepositoryJournalDirection,
        boundary: ForwardBoundary | ReverseBoundary,
        kind: RepositoryMutationKind,
        mutation_index: int,
        before_fingerprint: str,
        expected_after_fingerprint: str,
    ) -> RepositoryJournalRecordV1:
        return self._append(
            direction=direction,
            boundary=boundary,
            kind=kind,
            mutation_index=mutation_index,
            before=before_fingerprint,
            expected=expected_after_fingerprint,
            observed=_ZERO,
            event=RepositoryJournalEvent.INTENT,
            outcome=RepositoryJournalOutcome.PENDING,
        )

    def append_applied(
        self, intent: object, observed_effect_fingerprint: object
    ) -> tuple[RepositoryJournalRecordV1, RepositoryJournalRecordV1]:
        observed = self.append_observed(
            intent, observed_effect_fingerprint
        )
        committed = self.append_committed(intent, observed)
        return observed, committed

    def append_observed(
        self,
        intent: object,
        observed_effect_fingerprint: object,
    ) -> RepositoryJournalRecordV1:
        if (
            type(intent) is not RepositoryJournalRecordV1
            or intent.event != RepositoryJournalEvent.INTENT.value
            or not self._records
            or self._records[-1] is not intent
            or not _is_fingerprint(observed_effect_fingerprint)
            or observed_effect_fingerprint == _ZERO
        ):
            _fail()
        common = {
            "direction": RepositoryJournalDirection(intent.direction),
            "boundary": _boundary(intent),
            "kind": RepositoryMutationKind(intent.mutation_kind),
            "mutation_index": intent.mutation_index,
            "before": intent.before_observation_fingerprint,
            "expected": intent.expected_after_observation_fingerprint,
            "observed": observed_effect_fingerprint,
            "outcome": RepositoryJournalOutcome.APPLIED,
        }
        return self._append(
            event=RepositoryJournalEvent.OBSERVED, **common
        )

    def append_aborted(
        self, intent: object
    ) -> RepositoryJournalRecordV1:
        if (
            type(intent) is not RepositoryJournalRecordV1
            or intent.event != RepositoryJournalEvent.INTENT.value
            or not self._records
            or self._records[-1] is not intent
        ):
            _fail()
        return self._append(
            direction=RepositoryJournalDirection(intent.direction),
            boundary=_boundary(intent),
            kind=RepositoryMutationKind(intent.mutation_kind),
            mutation_index=intent.mutation_index,
            before=intent.before_observation_fingerprint,
            expected=intent.expected_after_observation_fingerprint,
            observed=intent.before_observation_fingerprint,
            event=RepositoryJournalEvent.ABORTED,
            outcome=RepositoryJournalOutcome.NOT_APPLIED,
        )

    def append_committed(
        self,
        intent: object,
        observed: object,
    ) -> RepositoryJournalRecordV1:
        if (
            type(intent) is not RepositoryJournalRecordV1
            or type(observed) is not RepositoryJournalRecordV1
            or not self._records
            or self._records[-1] is not observed
            or observed.event != RepositoryJournalEvent.OBSERVED.value
            or observed.mutation_index != intent.mutation_index
            or observed.boundary != intent.boundary
            or observed.direction != intent.direction
        ):
            _fail()
        return self._append(
            direction=RepositoryJournalDirection(intent.direction),
            boundary=_boundary(intent),
            kind=RepositoryMutationKind(intent.mutation_kind),
            mutation_index=intent.mutation_index,
            before=intent.before_observation_fingerprint,
            expected=intent.expected_after_observation_fingerprint,
            observed=observed.observed_effect_fingerprint,
            event=RepositoryJournalEvent.COMMITTED,
            outcome=RepositoryJournalOutcome.APPLIED,
        )

    def verified_records(
        self,
    ) -> tuple[RepositoryJournalRecordV1, ...]:
        records = _load_records(self._root)
        _verify_chain(records, self)
        if records != tuple(self._records):
            _fail()
        return tuple(self._records)

    def _append(self, **values) -> RepositoryJournalRecordV1:
        sequence = len(self._records) + 1
        if sequence > _MAX_RECORDS:
            _fail()
        record = RepositoryJournalRecordV1.create(
            {
                "schema_version": 1,
                "sequence": sequence,
                "previous_record_hash": (
                    self._records[-1].record_hash
                    if self._records else _ZERO
                ),
                "direction": values["direction"].value,
                "boundary": values["boundary"].value,
                "mutation_kind": values["kind"].value,
                "mutation_index": values["mutation_index"],
                "operation_fingerprint": (
                    self._scope.review.operation_fingerprint
                ),
                "profile_fingerprint": (
                    self._scope.profile.profile_fingerprint
                ),
                "governing_master_commit": (
                    self._scope.profile.governing_master_commit
                ),
                "authorization_fingerprint": (
                    self._authorization_fingerprint
                ),
                "owner_fingerprint": (
                    self._scope.review.marker_identity
                ),
                "before_observation_fingerprint": values["before"],
                "expected_after_observation_fingerprint": values["expected"],
                "observed_effect_fingerprint": values["observed"],
                "event": values["event"].value,
                "outcome": values["outcome"].value,
            }
        )
        _publish_durable(self._root, record)
        self._records.append(record)
        return record


def _publish_durable(
    root: Path, record: RepositoryJournalRecordV1
) -> None:
    name = f"{record.sequence:06d}-{record.record_hash}.json"
    path = root / name
    payload = record.to_canonical_json()
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.read_bytes() != payload:
            _fail()
    except (FileExistsError, OSError):
        _fail()


def _load_records(root: Path) -> tuple[RepositoryJournalRecordV1, ...]:
    paths = tuple(sorted(root.iterdir(), key=lambda item: item.name))
    if len(paths) > _MAX_RECORDS:
        _fail()
    records: list[RepositoryJournalRecordV1] = []
    for index, path in enumerate(paths, start=1):
        if not path.is_file() or path.is_symlink():
            _fail()
        try:
            record = RepositoryJournalRecordV1.from_json(path.read_bytes())
        except RepositoryTransactionError:
            _fail()
        expected = f"{index:06d}-{record.record_hash}.json"
        if path.name != expected or record.sequence != index:
            _fail()
        records.append(record)
    return tuple(records)


def _verify_chain(records, store) -> None:
    verify_journal_chain(
        records,
        operation=store._scope.review.operation_fingerprint,
        profile=store._scope.profile.profile_fingerprint,
        authorization=store._authorization_fingerprint,
        owner=store._scope.review.marker_identity,
    )


def _authorization_fingerprint(scope) -> str:
    authorization = scope.authorization
    payload = (
        authorization.profile_fingerprint
        + authorization.operation_fingerprint
        + authorization.phase
        + str(authorization.expires_at_epoch)
    ).encode("ascii")
    return hashlib.sha256(b"issue56-test-authorization-v1\0" + payload).hexdigest()


def _is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _boundary(intent):
    if intent.direction == RepositoryJournalDirection.FORWARD.value:
        return ForwardBoundary(intent.boundary)
    return ReverseBoundary(intent.boundary)


def _fail() -> None:
    raise RepositoryTransactionError("repository_journal_invalid") from None
