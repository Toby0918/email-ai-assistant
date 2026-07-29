"""Consume one durable journal INTENT before the Container ACL effect."""

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


@contextmanager
def consumed_acl_intent(
    *,
    intent: object,
    durable_permit: object,
    before_fingerprint: str,
    expected_after_fingerprint: str,
) -> Iterator[None]:
    if (
        type(intent) is not JournalRecordV1
        or intent.event_code != JournalEventCode.INTENT.value
        or intent.direction != JournalDirection.FORWARD.value
        or intent.before_observation_fingerprint != before_fingerprint
        or intent.expected_after_observation_fingerprint
        != expected_after_fingerprint
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
    raise CutoverHostMutationError("acl_journal_intent_required") from None
