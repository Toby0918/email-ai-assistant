"""Consume one Issue #52 durable INTENT before a host mutation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from backend.cutover_journal import (
    JournalDirection,
    JournalEventCode,
    JournalRecordV1,
)
from backend.cutover_journal.effect_permit import (
    _consume_durable_permit,
    _release_effect_claim,
)
from backend.cutover_journal.errors import JournalContractError

from .errors import CutoverHostMutationError
from .filesystem_contracts import FilesystemMutationExpectationV1


@contextmanager
def consumed_filesystem_intent(
    *,
    intent: object,
    durable_permit: object,
    expectation: FilesystemMutationExpectationV1,
) -> Iterator[None]:
    if (
        type(intent) is not JournalRecordV1
        or type(expectation) is not FilesystemMutationExpectationV1
        or intent.event_code != JournalEventCode.INTENT.value
        or intent.direction != JournalDirection.FORWARD.value
        or intent.before_observation_fingerprint
        != expectation.before_fingerprint
        or intent.expected_after_observation_fingerprint
        != expectation.expected_after_fingerprint
    ):
        _fail()
    try:
        claim = _consume_durable_permit(
            durable_permit,
            intent=intent,
            direction=intent.direction,
            step_code=intent.step_code,
        )
    except (JournalContractError, AttributeError, TypeError):
        _fail()
    try:
        yield
    finally:
        try:
            _release_effect_claim(claim)
        except JournalContractError:
            _fail()


def _fail() -> None:
    raise CutoverHostMutationError(
        "filesystem_journal_intent_required"
    ) from None
