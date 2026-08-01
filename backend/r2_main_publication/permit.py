"""Issue #52 durable permit bridge for one Issue #74 host effect."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from backend.cutover_host_mutation.filesystem_contracts import (
    FilesystemMutationExpectationV1,
)
from backend.cutover_journal import (
    DurabilityPlatform,
    DurableJournalStore,
    JournalOperationBindingV1,
    JournalRecordV1,
    SyntheticJournalMediumV1,
)

from .canonical import canonical

_ZERO = "0" * 64


@dataclass(slots=True, repr=False)
class HostEffectPermit:
    intent: JournalRecordV1 = field(repr=False)
    permit: object = field(repr=False)
    store: DurableJournalStore = field(repr=False)

    def close(self) -> None:
        self.store.close()


def issue_host_effect_permit(
    *,
    profile,
    authorization,
    owner_fingerprint: str,
    expectation: FilesystemMutationExpectationV1,
) -> HostEffectPermit:
    binding = _binding(profile, authorization, owner_fingerprint)
    store = DurableJournalStore.begin_synthetic(
        medium=SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.WINDOWS
        ),
        binding=binding,
    )
    intent = JournalRecordV1.create(_intent_body(binding, expectation))
    return HostEffectPermit(intent, store.append_record(intent), store)


def _binding(profile, authorization, owner):
    forward = _authorization_fingerprint(authorization)
    recovery = hashlib.sha256(
        b"issue74-recovery-authorization-v1\0" + bytes.fromhex(forward)
    ).hexdigest()
    body = {
        "governing_master_commit": profile.governing_master_commit,
        "operator_fingerprint": profile.operator_fingerprint,
        "operation_fingerprint": authorization.operation_fingerprint,
        "profile_fingerprint": profile.profile_fingerprint,
        "forward_authorization_fingerprint": forward,
        "recovery_authorization_fingerprint": recovery,
        "owner_fingerprint": owner,
    }
    value = hashlib.sha256(canonical(body)).hexdigest()
    return JournalOperationBindingV1.from_mapping(
        {**body, "binding_fingerprint": value}
    )


def _intent_body(binding, expectation) -> dict[str, object]:
    return {
        "record_type": "JournalRecordV1",
        "sequence": 1,
        "previous_record_hash": _ZERO,
        "step_code": "SYNTHETIC_PREPARE",
        "direction": "FORWARD",
        "event_code": "INTENT",
        "governing_master_commit": binding.governing_master_commit,
        "operation_fingerprint": binding.operation_fingerprint,
        "profile_fingerprint": binding.profile_fingerprint,
        "forward_authorization_fingerprint": (
            binding.forward_authorization_fingerprint
        ),
        "recovery_authorization_fingerprint": (
            binding.recovery_authorization_fingerprint
        ),
        "owner_fingerprint": binding.owner_fingerprint,
        "authorization_fingerprint": (
            binding.forward_authorization_fingerprint
        ),
        "before_observation_fingerprint": expectation.before_fingerprint,
        "expected_after_observation_fingerprint": (
            expectation.expected_after_fingerprint
        ),
        "observed_effect_fingerprint": _ZERO,
        "effect_outcome": "PENDING",
    }


def _authorization_fingerprint(value) -> str:
    body = {
        "expires_at_epoch": value.expires_at_epoch,
        "operation_fingerprint": value.operation_fingerprint,
        "phase": value.phase,
        "profile_fingerprint": value.profile_fingerprint,
    }
    return hashlib.sha256(
        b"issue74-filesystem-authorization-v1\0" + canonical(body)
    ).hexdigest()
