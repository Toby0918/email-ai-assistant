"""Synthetic content-free fixtures for Issue #52 journal tests."""

from __future__ import annotations

import hashlib
import json

from backend.cutover_contracts import (
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    RecoveryAuthorizationV1,
)
from backend.cutover_journal import JournalOperationBindingV1
from tests.cutover_contract_fixtures import valid_profile_body


GOVERNING_MASTER = "ae753319aa01c52c12af8952fd2ea2d975e60c0b"
ZERO_FINGERPRINT = "0" * 64


class HostileComparison:
    def __eq__(self, _other: object) -> bool:
        raise RuntimeError("hostile comparison must not run")


def opaque_fingerprint(index: int) -> str:
    return f"{index:064x}"


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def valid_operation_contracts(
    *,
    forward_phase: str = "execute",
    forward_expires_at: int = 1_800_000_610,
    recovery_expires_at: int = 1_800_003_610,
) -> tuple[
    CutoverProfileV1,
    CutoverExecutionAuthorizationV1,
    RecoveryAuthorizationV1,
]:
    profile_body = valid_profile_body()
    profile_body["governing_master_commit"] = GOVERNING_MASTER
    profile = CutoverProfileV1.create(profile_body)
    forward = CutoverExecutionAuthorizationV1.from_mapping(
        _authorization_mapping(
            authorization_type="CutoverExecutionAuthorizationV1",
            operation="cutover_execution",
            phase=forward_phase,
            profile=profile,
            expires_at_epoch=forward_expires_at,
        )
    )
    recovery = RecoveryAuthorizationV1.from_mapping(
        _authorization_mapping(
            authorization_type="RecoveryAuthorizationV1",
            operation="recovery",
            phase="rollback",
            profile=profile,
            expires_at_epoch=recovery_expires_at,
        )
    )
    return profile, forward, recovery


def valid_operation_binding(
    *, owner_index: int = 7
) -> JournalOperationBindingV1:
    profile, forward, recovery = valid_operation_contracts()
    return JournalOperationBindingV1.create(
        profile=profile,
        forward_authorization=forward,
        recovery_authorization=recovery,
        owner_fingerprint=opaque_fingerprint(owner_index),
        observed_at_epoch=1_800_000_100,
    )


def replacement_recovery_authorization() -> RecoveryAuthorizationV1:
    _profile, _forward, recovery = valid_operation_contracts()
    mapping = recovery.to_mapping()
    mapping.update(
        {
            "issued_at_epoch": 1_800_000_001,
            "not_before_epoch": 1_800_000_011,
            "expires_at_epoch": 1_800_003_611,
        }
    )
    body = dict(mapping)
    body.pop("authorization_fingerprint")
    mapping["authorization_fingerprint"] = hashlib.sha256(
        canonical_json(body)
    ).hexdigest()
    return RecoveryAuthorizationV1.from_mapping(mapping)


def _authorization_mapping(
    *,
    authorization_type: str,
    operation: str,
    phase: str,
    profile: CutoverProfileV1,
    expires_at_epoch: int,
) -> dict[str, object]:
    body = {
        "authorization_type": authorization_type,
        "operation": operation,
        "operation_fingerprint": opaque_fingerprint(201),
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_commit": profile.governing_master_commit,
        "operator_fingerprint": profile.operator_fingerprint,
        "phase": phase,
        "issued_at_epoch": 1_800_000_000,
        "not_before_epoch": 1_800_000_010,
        "expires_at_epoch": expires_at_epoch,
    }
    return {
        **body,
        "authorization_fingerprint": hashlib.sha256(
            canonical_json(body)
        ).hexdigest(),
    }


def valid_journal_record_body() -> dict[str, object]:
    return {
        "record_type": "JournalRecordV1",
        "sequence": 1,
        "previous_record_hash": ZERO_FINGERPRINT,
        "step_code": "SYNTHETIC_PREPARE",
        "direction": "FORWARD",
        "event_code": "INTENT",
        "governing_master_commit": GOVERNING_MASTER,
        "operation_fingerprint": opaque_fingerprint(1),
        "profile_fingerprint": opaque_fingerprint(2),
        "forward_authorization_fingerprint": opaque_fingerprint(3),
        "recovery_authorization_fingerprint": opaque_fingerprint(4),
        "owner_fingerprint": opaque_fingerprint(7),
        "authorization_fingerprint": opaque_fingerprint(3),
        "before_observation_fingerprint": opaque_fingerprint(5),
        "expected_after_observation_fingerprint": opaque_fingerprint(6),
        "observed_effect_fingerprint": ZERO_FINGERPRINT,
        "effect_outcome": "PENDING",
    }


def valid_bound_journal_record_body(
    binding: JournalOperationBindingV1,
) -> dict[str, object]:
    value = valid_journal_record_body()
    value.update(
        {
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
        }
    )
    return value


def journal_record_body_after(
    previous,
    *,
    event_code: str,
    step_code: str | None = None,
    direction: str | None = None,
    effect_outcome: str = "APPLIED",
    authorization_fingerprint: str | None = None,
) -> dict[str, object]:
    value = previous.to_mapping()
    value.pop("record_hash")
    value.update(
        {
            "sequence": previous.sequence + 1,
            "previous_record_hash": previous.record_hash,
            "event_code": event_code,
        }
    )
    if step_code is not None:
        value["step_code"] = step_code
    if direction is not None:
        value["direction"] = direction
    if authorization_fingerprint is not None:
        value["authorization_fingerprint"] = authorization_fingerprint
    if event_code in {"INTENT", "RESUME_BOUND"}:
        value["effect_outcome"] = "PENDING"
        value["observed_effect_fingerprint"] = ZERO_FINGERPRINT
    else:
        value["effect_outcome"] = effect_outcome
        value["observed_effect_fingerprint"] = (
            value["expected_after_observation_fingerprint"]
            if effect_outcome == "APPLIED"
            else value["before_observation_fingerprint"]
        )
    return value


def valid_observed_record_body(
    *,
    event_code: str = "EFFECT_OBSERVED",
    direction: str = "FORWARD",
    outcome: str = "APPLIED",
) -> dict[str, object]:
    value = valid_journal_record_body()
    value.update(
        {
            "sequence": 2,
            "previous_record_hash": opaque_fingerprint(8),
            "direction": direction,
            "event_code": event_code,
            "effect_outcome": outcome,
        }
    )
    if direction == "REVERSE":
        value["authorization_fingerprint"] = value[
            "recovery_authorization_fingerprint"
        ]
        before = value["before_observation_fingerprint"]
        value["before_observation_fingerprint"] = value[
            "expected_after_observation_fingerprint"
        ]
        value["expected_after_observation_fingerprint"] = before
    value["observed_effect_fingerprint"] = (
        value["expected_after_observation_fingerprint"]
        if outcome == "APPLIED"
        else value["before_observation_fingerprint"]
    )
    return value
