"""Journal-first execution of fixed synthetic filesystem effects."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from backend.cutover_host_mutation.errors import CutoverHostMutationError
from backend.cutover_host_mutation.filesystem_contracts import (
    FilesystemMutationObservationV1,
)
from backend.cutover_host_mutation.windows_filesystem import (
    _create_test_directory_primitive,
    _create_test_move_primitive,
)

from .durable_store import _RepositoryJournalStore
from .errors import RepositoryTransactionError
from .issue52_bridge import issue_filesystem_effect_permit
from .journal_types import (
    ForwardBoundary,
    RepositoryJournalDirection,
    RepositoryMutationKind,
    ReverseBoundary,
)
from .scope_models import _SyntheticTransactionScope
from .stable_observation import (
    filesystem_observation,
    locked_filesystem_observation,
)
from .transaction_types import (
    SyntheticCrashGap,
    SyntheticFailureSelectorV1,
    SyntheticTransactionDirection,
)


@dataclass(slots=True, repr=False)
class _TransactionExecutor:
    scope: _SyntheticTransactionScope = field(repr=False)
    journal: _RepositoryJournalStore = field(repr=False)
    selector: SyntheticFailureSelectorV1 = field(repr=False)
    direction: SyntheticTransactionDirection
    observed_at_epoch: int = field(repr=False)
    mutation_count: int = 0

    def move(
        self,
        *,
        boundary: ForwardBoundary | ReverseBoundary, source: Path,
        target: Path,
        kind: RepositoryMutationKind = RepositoryMutationKind.PHYSICAL_MOVE,
    ) -> object:
        try:
            primitive = _create_test_move_primitive(
                root=Path(self.scope.review.scenario.root),
                marker=Path(self.scope.review.scenario.marker),
                authorization=self.scope.authorization,
                profile=self.scope.profile,
                source=source,
                target_parent=target.parent,
                target=target,
                observed_at_epoch=self.observed_at_epoch,
            )
            expectation = primitive.expectation
            intent = self._intent(
                boundary, kind,
                expectation.before_fingerprint,
                expectation.expected_after_fingerprint,
            )
            permit = issue_filesystem_effect_permit(
                self.scope, expectation
            )
            try:
                observation = primitive.move_object(
                    intent=permit.intent,
                    durable_permit=permit.permit,
                )
                effect_intent = permit.intent.record_hash
            finally:
                permit.close()
        except CutoverHostMutationError:
            _fail("repository_transaction_failed")
        self._after_effect(boundary)
        identity = _filesystem_observation_fingerprint(
            observation, expectation, effect_intent
        )
        self._finish(
            intent,
            boundary,
            filesystem_observation(target, kind, identity),
            stable_context=lambda: locked_filesystem_observation(
                target, kind
            ),
        )
        return observation

    def create_directory(
        self,
        *,
        boundary: ForwardBoundary | ReverseBoundary,
        target: Path,
        kind: RepositoryMutationKind = (
            RepositoryMutationKind.CREATE_DIRECTORY
        ),
    ) -> object:
        try:
            primitive = _create_test_directory_primitive(
                root=Path(self.scope.review.scenario.root),
                marker=Path(self.scope.review.scenario.marker),
                authorization=self.scope.authorization,
                profile=self.scope.profile,
                parent=target.parent,
                target=target,
                observed_at_epoch=self.observed_at_epoch,
            )
            expectation = primitive.expectation
            intent = self._intent(
                boundary, kind, expectation.before_fingerprint,
                expectation.expected_after_fingerprint,
            )
            permit = issue_filesystem_effect_permit(
                self.scope, expectation
            )
            try:
                observation = primitive.create_directory(
                    intent=permit.intent,
                    durable_permit=permit.permit,
                )
                effect_intent = permit.intent.record_hash
            finally:
                permit.close()
        except CutoverHostMutationError:
            _fail("repository_transaction_failed")
        self._after_effect(boundary)
        identity = _filesystem_observation_fingerprint(
            observation, expectation, effect_intent
        )
        self._finish(
            intent,
            boundary,
            filesystem_observation(target, kind, identity),
            stable_context=lambda: locked_filesystem_observation(
                target, kind
            ),
        )
        return observation

    def fixed_effect(
        self,
        *,
        boundary: ForwardBoundary | ReverseBoundary,
        kind: RepositoryMutationKind,
        before: str,
        expected: str,
        effect: Callable[[], object],
        observation: Callable[[object], str],
        stable_observation: Callable[[], str],
    ) -> object:
        intent = self._intent(boundary, kind, before, expected)
        try:
            result = effect()
        except RepositoryTransactionError:
            raise
        except Exception:
            _fail("repository_transaction_failed")
        self._after_effect(boundary)
        self._finish(
            intent,
            boundary,
            observation(result),
            stable_context=lambda: _value_context(stable_observation),
        )
        return result

    def verify(
        self,
        *,
        boundary: ForwardBoundary | ReverseBoundary,
        material: str,
        verification: Callable[[], object],
    ) -> object:
        before = _fingerprint("verify-before", material)
        expected = _fingerprint("verify-after", material)
        return self.fixed_effect(
            boundary=boundary,
            kind=RepositoryMutationKind.VERIFY,
            before=before,
            expected=expected,
            effect=verification,
            observation=lambda _result: _fingerprint(
                "verify-observed", material
            ),
            stable_observation=lambda: _stable_verification(
                verification, material
            ),
        )

    def _intent(self, boundary, kind, before, expected):
        self.mutation_count += 1
        intent = self.journal.append_intent(
            direction=RepositoryJournalDirection(self.direction.value),
            boundary=boundary,
            kind=kind,
            mutation_index=self.mutation_count,
            before_fingerprint=before,
            expected_after_fingerprint=expected,
        )
        self._cut(boundary, SyntheticCrashGap.AFTER_INTENT)
        return intent

    def _after_effect(self, boundary) -> None:
        self._cut(boundary, SyntheticCrashGap.AFTER_EFFECT)

    def _finish(
        self,
        intent,
        boundary,
        actual: str,
        *,
        stable_context,
    ) -> None:
        observed = self.journal.append_observed(intent, actual)
        self._cut(boundary, SyntheticCrashGap.AFTER_OBSERVED)
        with stable_context() as stable:
            if stable != actual:
                _fail("repository_stable_reread_failed")
            self.journal.append_committed(intent, observed)
        self._cut(boundary, SyntheticCrashGap.AFTER_COMMITTED)

    def _cut(self, boundary, gap) -> None:
        if self.selector.matches(
            self.direction, boundary, self.mutation_count, gap
        ):
            _fail("repository_transaction_interrupted")


def _fingerprint(domain: str, material: str) -> str:
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + material.encode("ascii")
    ).hexdigest()


@contextmanager
def _value_context(callback):
    yield callback()


def _stable_verification(verification, material: str) -> str:
    verification()
    return _fingerprint("verify-observed", material)


def _filesystem_observation_fingerprint(
    observation: object,
    expectation: object,
    effect_intent_fingerprint: str,
) -> str:
    if (
        type(observation) is not FilesystemMutationObservationV1
        or observation.kind is not expectation.kind
        or observation.journal_intent_fingerprint
        != effect_intent_fingerprint
        or observation.journal_effect_fingerprint
        != expectation.expected_after_fingerprint
        or observation.no_replace is not True
        or observation.reparse_free is not True
    ):
        _fail("repository_observation_invalid")
    return observation.target_identity_fingerprint


def _fail(code: str) -> None:
    raise RepositoryTransactionError(code) from None
