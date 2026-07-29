"""Issue #52 durable-permit bridge for one Issue #55 host effect."""

from __future__ import annotations

import hashlib
import json
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

from .errors import RepositoryTransactionError
from .scope_models import _SyntheticTransactionScope

_ZERO = "0" * 64


@dataclass(slots=True, repr=False)
class _Issue52EffectPermit:
    intent: JournalRecordV1 = field(repr=False)
    permit: object = field(repr=False)
    store: DurableJournalStore = field(repr=False)

    def close(self) -> None:
        self.store.close()


def issue_filesystem_effect_permit(
    scope: _SyntheticTransactionScope,
    expectation: FilesystemMutationExpectationV1,
) -> _Issue52EffectPermit:
    if (
        type(scope) is not _SyntheticTransactionScope
        or type(expectation) is not FilesystemMutationExpectationV1
    ):
        _fail()
    binding = _binding(scope)
    medium = SyntheticJournalMediumV1.empty(
        platform=DurabilityPlatform.WINDOWS
    )
    store = DurableJournalStore.begin_synthetic(
        medium=medium, binding=binding
    )
    intent = JournalRecordV1.create(
        {
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
            "before_observation_fingerprint": (
                expectation.before_fingerprint
            ),
            "expected_after_observation_fingerprint": (
                expectation.expected_after_fingerprint
            ),
            "observed_effect_fingerprint": _ZERO,
            "effect_outcome": "PENDING",
        }
    )
    permit = store.append_record(intent)
    return _Issue52EffectPermit(intent, permit, store)


def _binding(scope: _SyntheticTransactionScope):
    forward = _authorization_fingerprint(scope)
    recovery = hashlib.sha256(
        b"issue56-recovery-permit-v1\0" + bytes.fromhex(forward)
    ).hexdigest()
    body = {
        "governing_master_commit": scope.profile.governing_master_commit,
        "operator_fingerprint": scope.profile.operator_fingerprint,
        "operation_fingerprint": scope.review.operation_fingerprint,
        "profile_fingerprint": scope.profile.profile_fingerprint,
        "forward_authorization_fingerprint": forward,
        "recovery_authorization_fingerprint": recovery,
        "owner_fingerprint": scope.review.marker_identity,
    }
    fingerprint = hashlib.sha256(_canonical(body)).hexdigest()
    return JournalOperationBindingV1.from_mapping(
        {**body, "binding_fingerprint": fingerprint}
    )


def _authorization_fingerprint(scope) -> str:
    value = scope.authorization
    body = {
        "expires_at_epoch": value.expires_at_epoch,
        "operation_fingerprint": value.operation_fingerprint,
        "phase": value.phase,
        "profile_fingerprint": value.profile_fingerprint,
    }
    return hashlib.sha256(
        b"issue56-filesystem-authorization-v1\0" + _canonical(body)
    ).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _fail() -> None:
    raise RepositoryTransactionError(
        "repository_journal_bridge_invalid"
    ) from None
