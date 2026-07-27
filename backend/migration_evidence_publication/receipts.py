"""Nominal content-free review receipt for Issue #54."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from weakref import WeakKeyDictionary

from .canonical import canonical_json, fingerprint
from .profile_binding import _ProfileBindings


_RECEIPT_ERROR = "MIGRATION_EVIDENCE_REVIEW_RECEIPT_INVALID"


@dataclass(frozen=True, slots=True)
class MigrationEvidenceReviewCountsV1:
    dirty_entries: int
    included_dirty_entries: int
    excluded_dirty_entries: int
    refs: int
    worktrees: int
    source_records: int
    source_bytes: int


@dataclass(frozen=True, slots=True, repr=False)
class _ReviewReceiptBinding:
    receipt_fingerprint: str
    operation_fingerprint: str
    profile_fingerprint: str
    master_fingerprint: str
    review_fingerprint: str
    selection_fingerprint: str
    git_fingerprint: str
    host_fingerprint: str
    counts_fingerprint: str
    counts: MigrationEvidenceReviewCountsV1


_RECEIPT_STATES: WeakKeyDictionary[
    object,
    _ReviewReceiptBinding,
] = WeakKeyDictionary()
_RECEIPT_STATES_LOCK = Lock()


class MigrationEvidenceReviewReceiptV1:
    """A closed receipt exposing fingerprints and aggregate counts only."""

    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated review receipt construction required")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise ValueError(_RECEIPT_ERROR)

    def __delattr__(self, _name: str) -> None:
        raise ValueError(_RECEIPT_ERROR)

    def __copy__(self) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __deepcopy__(self, _memo: object) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __reduce__(self) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __reduce_ex__(self, _protocol: int) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __getstate__(self) -> object:
        raise ValueError(_RECEIPT_ERROR)

    @property
    def receipt_fingerprint(self) -> str:
        return _receipt_binding(self).receipt_fingerprint

    @property
    def review_fingerprint(self) -> str:
        return _receipt_binding(self).review_fingerprint

    @property
    def selection_fingerprint(self) -> str:
        return _receipt_binding(self).selection_fingerprint

    @property
    def git_fingerprint(self) -> str:
        return _receipt_binding(self).git_fingerprint

    @property
    def host_fingerprint(self) -> str:
        return _receipt_binding(self).host_fingerprint

    @property
    def counts_fingerprint(self) -> str:
        return _receipt_binding(self).counts_fingerprint

    @property
    def counts(self) -> MigrationEvidenceReviewCountsV1:
        return _receipt_binding(self).counts

    def to_mapping(self) -> dict[str, object]:
        state = _receipt_binding(self)
        return _mapping(state)

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def _mint_review_receipt(
    *,
    operation_fingerprint: str,
    profile_fingerprint: str,
    master_fingerprint: str,
    review_fingerprint: str,
    bindings: _ProfileBindings,
) -> MigrationEvidenceReviewReceiptV1:
    counts = MigrationEvidenceReviewCountsV1(**bindings.counts)
    provisional = _ReviewReceiptBinding(
        receipt_fingerprint="",
        operation_fingerprint=operation_fingerprint,
        profile_fingerprint=profile_fingerprint,
        master_fingerprint=master_fingerprint,
        review_fingerprint=review_fingerprint,
        selection_fingerprint=bindings.selection_fingerprint,
        git_fingerprint=bindings.git_fingerprint,
        host_fingerprint=bindings.host_fingerprint,
        counts_fingerprint=bindings.counts_fingerprint,
        counts=counts,
    )
    receipt_fingerprint = fingerprint(
        "migration-evidence-review-receipt-v1",
        _mapping(provisional, include_receipt=False),
    )
    state = _ReviewReceiptBinding(
        receipt_fingerprint=receipt_fingerprint,
        operation_fingerprint=operation_fingerprint,
        profile_fingerprint=profile_fingerprint,
        master_fingerprint=master_fingerprint,
        review_fingerprint=review_fingerprint,
        selection_fingerprint=bindings.selection_fingerprint,
        git_fingerprint=bindings.git_fingerprint,
        host_fingerprint=bindings.host_fingerprint,
        counts_fingerprint=bindings.counts_fingerprint,
        counts=counts,
    )
    receipt = object.__new__(MigrationEvidenceReviewReceiptV1)
    with _RECEIPT_STATES_LOCK:
        _RECEIPT_STATES[receipt] = state
    return receipt


def _receipt_binding(
    receipt: object,
) -> _ReviewReceiptBinding:
    if type(receipt) is not MigrationEvidenceReviewReceiptV1:
        raise ValueError(_RECEIPT_ERROR)
    with _RECEIPT_STATES_LOCK:
        state = _RECEIPT_STATES.get(receipt)
    if state is None:
        raise ValueError(_RECEIPT_ERROR)
    return state


def _mapping(
    state: _ReviewReceiptBinding,
    *,
    include_receipt: bool = True,
) -> dict[str, object]:
    value = {
        "receipt_type": "MigrationEvidenceReviewReceiptV1",
        "status": "MIGRATION_EVIDENCE_REVIEW_ACCEPTED",
        "operation_fingerprint": state.operation_fingerprint,
        "profile_fingerprint": state.profile_fingerprint,
        "master_fingerprint": state.master_fingerprint,
        "review_fingerprint": state.review_fingerprint,
        "selection_fingerprint": state.selection_fingerprint,
        "git_fingerprint": state.git_fingerprint,
        "host_fingerprint": state.host_fingerprint,
        "counts_fingerprint": state.counts_fingerprint,
        "counts": {
            "dirty_entries": state.counts.dirty_entries,
            "included_dirty_entries": (
                state.counts.included_dirty_entries
            ),
            "excluded_dirty_entries": (
                state.counts.excluded_dirty_entries
            ),
            "refs": state.counts.refs,
            "worktrees": state.counts.worktrees,
            "source_records": state.counts.source_records,
            "source_bytes": state.counts.source_bytes,
        },
    }
    if include_receipt:
        value["receipt_fingerprint"] = state.receipt_fingerprint
    return value
