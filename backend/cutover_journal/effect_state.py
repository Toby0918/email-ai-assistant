"""Exact synthetic observations and effects for transaction proofs."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._canonical import is_opaque_fingerprint
from .errors import JournalContractError
from .journal_types import JournalDirection, JournalStepCode


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticEffectSnapshotV1:
    initial_observation_fingerprint: str = field(repr=False)
    prepared_observation_fingerprint: str = field(repr=False)
    published_observation_fingerprint: str = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    identity_mapping_intact: bool
    forward_invocations: int
    reverse_invocations: int


@dataclass(slots=True, init=False, repr=False)
class SyntheticEffectStateV1:
    _initial: str
    _prepared: str
    _published: str
    _observation: str
    _identity_mapping_intact: bool
    _forward_invocations: int
    _reverse_invocations: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticEffectStateV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        initial_observation_fingerprint: str,
        prepared_observation_fingerprint: str,
        published_observation_fingerprint: str,
    ) -> SyntheticEffectStateV1:
        return cls.from_restart(
            initial_observation_fingerprint=(
                initial_observation_fingerprint
            ),
            prepared_observation_fingerprint=(
                prepared_observation_fingerprint
            ),
            published_observation_fingerprint=(
                published_observation_fingerprint
            ),
            current_observation_fingerprint=(
                initial_observation_fingerprint
            ),
            identity_mapping_intact=True,
            forward_invocations=0,
            reverse_invocations=0,
        )

    @classmethod
    def from_restart(
        cls,
        *,
        initial_observation_fingerprint: str,
        prepared_observation_fingerprint: str,
        published_observation_fingerprint: str,
        current_observation_fingerprint: str,
        identity_mapping_intact: bool,
        forward_invocations: int = 0,
        reverse_invocations: int = 0,
    ) -> SyntheticEffectStateV1:
        observations = (
            initial_observation_fingerprint,
            prepared_observation_fingerprint,
            published_observation_fingerprint,
            current_observation_fingerprint,
        )
        if (
            not all(is_opaque_fingerprint(value) for value in observations)
            or len(set(observations[:3])) != 3
            or type(identity_mapping_intact) is not bool
            or not _valid_count(forward_invocations)
            or not _valid_count(reverse_invocations)
        ):
            raise JournalContractError("JOURNAL_EFFECT_STATE_INVALID")
        state = object.__new__(cls)
        state._initial = initial_observation_fingerprint
        state._prepared = prepared_observation_fingerprint
        state._published = published_observation_fingerprint
        state._observation = current_observation_fingerprint
        state._identity_mapping_intact = identity_mapping_intact
        state._forward_invocations = forward_invocations
        state._reverse_invocations = reverse_invocations
        return state

    @property
    def observation_fingerprint(self) -> str:
        return self._observation

    @property
    def forward_invocations(self) -> int:
        return self._forward_invocations

    @property
    def reverse_invocations(self) -> int:
        return self._reverse_invocations

    def snapshot(self) -> SyntheticEffectSnapshotV1:
        return SyntheticEffectSnapshotV1(
            initial_observation_fingerprint=self._initial,
            prepared_observation_fingerprint=self._prepared,
            published_observation_fingerprint=self._published,
            observation_fingerprint=self._observation,
            identity_mapping_intact=self._identity_mapping_intact,
            forward_invocations=self._forward_invocations,
            reverse_invocations=self._reverse_invocations,
        )

    def _transition_for(self, step_code: str) -> tuple[str, str]:
        if step_code == JournalStepCode.SYNTHETIC_PREPARE.value:
            return self._initial, self._prepared
        if step_code == JournalStepCode.SYNTHETIC_PUBLISH.value:
            return self._prepared, self._published
        raise JournalContractError("JOURNAL_TRANSITION_INVALID")

    def _apply(
        self,
        *,
        direction: str,
        step_code: str,
        intent: object,
        durable_permit: object,
    ) -> None:
        from .journal_record import JournalRecordV1
        from .effect_permit import _consume_durable_permit
        from .effect_permit import _release_effect_claim

        if type(intent) is not JournalRecordV1:
            raise JournalContractError("JOURNAL_EFFECT_PERMIT_INVALID")
        before, after = self._transition_for(step_code)
        if direction == JournalDirection.REVERSE.value:
            before, after = after, before
        if (
            not self._identity_mapping_intact
            or intent.direction != direction
            or intent.step_code != step_code
            or intent.before_observation_fingerprint != before
            or intent.expected_after_observation_fingerprint != after
            or self._observation != before
            or (
                direction == JournalDirection.FORWARD.value
                and self._forward_invocations >= 1_000_000
            )
            or (
                direction == JournalDirection.REVERSE.value
                and self._reverse_invocations >= 1_000_000
            )
        ):
            raise JournalContractError("JOURNAL_OBSERVATION_AMBIGUOUS")
        claim = _consume_durable_permit(
            durable_permit,
            intent=intent,
            direction=direction,
            step_code=step_code,
        )
        try:
            self._observation = after
            if direction == JournalDirection.FORWARD.value:
                self._forward_invocations += 1
            elif direction == JournalDirection.REVERSE.value:
                self._reverse_invocations += 1
            else:
                raise JournalContractError("JOURNAL_TRANSITION_INVALID")
        finally:
            _release_effect_claim(claim)


def _valid_count(value: object) -> bool:
    return type(value) is int and 0 <= value <= 1_000_000
