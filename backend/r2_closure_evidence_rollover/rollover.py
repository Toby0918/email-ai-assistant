"""Deep module coordinating one fresh historical closure evidence rollover."""

from __future__ import annotations

import time

from .contracts import (
    ClosureEvidenceRolloverCandidateV1,
    ClosureEvidenceRolloverError,
    ClosureEvidenceRolloverReceiptV1,
    ClosureEvidenceRolloverStateV1,
    RolloverErrorCode,
)
from .repository import FixedRolloverRepository
from .storage import FixedClosureEvidenceStorage


class _WallClock:
    def wall_epoch(self) -> int:
        return int(time.time())

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()


class ClosureEvidenceRollover:
    """Prepare and consume one exact, short-lived, no-clobber rollover candidate."""

    def __init__(self) -> None:
        self._repository = FixedRolloverRepository()
        self._storage = FixedClosureEvidenceStorage()
        self._clock = _WallClock()
        self._candidate = None
        self._prepared_monotonic_ns = None
        self._spent = False

    def prepare(self) -> ClosureEvidenceRolloverCandidateV1:
        if self._candidate is not None or self._spent:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
        state, _observation = self._derive_state()
        candidate = ClosureEvidenceRolloverCandidateV1.create(
            state, self._clock.wall_epoch()
        )
        prepared_monotonic = self._clock.monotonic_ns()
        if type(prepared_monotonic) is not int or prepared_monotonic < 0:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STALE)
        self._candidate = candidate
        self._prepared_monotonic_ns = prepared_monotonic
        return candidate

    def execute(self, exact_candidate_fingerprint: str) -> ClosureEvidenceRolloverReceiptV1:
        candidate = self._candidate
        if self._spent or type(candidate) is not ClosureEvidenceRolloverCandidateV1:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
        if exact_candidate_fingerprint != candidate.candidate_fingerprint:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.FINGERPRINT_REJECTED)
        self._require_fresh(candidate)
        self._spent = True
        state, observation = self._derive_state()
        self._require_same_state(candidate, state)

        commit_epoch = []

        def before_commit() -> None:
            fresh_state, _fresh_observation = self._derive_state()
            self._require_same_state(candidate, fresh_state)
            observed = self._require_fresh(candidate)
            commit_epoch.append(observed)

        self._storage.commit(observation, before_commit)
        if len(commit_epoch) != 1:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
        return ClosureEvidenceRolloverReceiptV1.create(candidate, commit_epoch[0])

    def _derive_state(self):
        evidence = self._storage.collect()
        repository = self._repository.collect(
            evidence.historical_commit_oid, evidence.historical_tree_oid
        )
        return ClosureEvidenceRolloverStateV1.create(
            repository=repository, evidence=evidence
        ), evidence

    @staticmethod
    def _require_same_state(candidate, state) -> None:
        if state.state_fingerprint != candidate.state_fingerprint:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)

    def _require_fresh(self, candidate) -> int:
        wall = self._clock.wall_epoch()
        monotonic = self._clock.monotonic_ns()
        prepared = self._prepared_monotonic_ns
        elapsed = monotonic - prepared if type(prepared) is int else -1
        if (
            type(wall) is not int
            or type(monotonic) is not int
            or wall < candidate.prepared_at_epoch
            or wall >= candidate.expires_at_epoch
            or elapsed < 0
            or elapsed >= 300_000_000_000
        ):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STALE)
        return wall
