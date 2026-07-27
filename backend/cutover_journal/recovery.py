"""Read-only restart inspection and deterministic classification."""

from __future__ import annotations

import hashlib

from ._canonical import (
    ZERO_FINGERPRINT,
    canonical_json,
)
from .contracts_bridge import (
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    RecoveryAuthorizationV1,
)
from .durability import JournalMediumSnapshotV1
from .effect_state import SyntheticEffectSnapshotV1
from .effect_guard import (
    assert_chain_effect_binding,
    assert_effect_snapshot_intact,
    assert_pending_observation,
)
from .journal_chain import (
    VerifiedJournalChainV1,
    verify_synthetic_journal_snapshot,
)
from .operation_binding import JournalOperationBindingV1
from .recovery_classifier import classify_restart
from .recovery_types import (
    JournalOperationCountsV1,
    JournalOperationPhase,
    JournalOperationResultV1,
    JournalOperationStatus,
)


def inspect_restart(
    *,
    snapshot: object,
    binding: JournalOperationBindingV1,
    profile: CutoverProfileV1,
    effect_snapshot: SyntheticEffectSnapshotV1,
    resume_authorization: CutoverExecutionAuthorizationV1 | None,
    recovery_authorization: RecoveryAuthorizationV1 | None,
    observed_at_epoch: int,
) -> JournalOperationResultV1:
    """Classify exact synthetic restart state without claiming ownership."""
    raw_counts = _raw_counts(snapshot)
    try:
        _assert_context(binding, profile, effect_snapshot)
        chain = verify_synthetic_journal_snapshot(
            snapshot,
            binding=binding,
        )
        assert_chain_effect_binding(chain, effect_snapshot)
        assert_pending_observation(chain, effect_snapshot)
        counts = _chain_counts(chain, raw_counts[1], rejected=0)
        status, phase = classify_restart(
            chain=chain,
            pending=raw_counts[1],
            effect=effect_snapshot,
            binding=binding,
            profile=profile,
            resume=resume_authorization,
            recovery=recovery_authorization,
            epoch=observed_at_epoch,
        )
        return _result(
            status,
            phase,
            counts,
            binding=binding,
            chain=chain,
            observation=effect_snapshot.observation_fingerprint,
        )
    except Exception:
        counts = JournalOperationCountsV1(
            records=raw_counts[0],
            pending=raw_counts[1],
            forward_committed=0,
            reverse_committed=0,
            rejected=1,
        )
        return _incident_result(counts)


def _assert_context(
    binding: object,
    profile: object,
    effect: object,
) -> None:
    if (
        type(binding) is not JournalOperationBindingV1
        or type(profile) is not CutoverProfileV1
        or type(effect) is not SyntheticEffectSnapshotV1
    ):
        raise ValueError
    intact_binding = JournalOperationBindingV1.from_mapping(
        binding.to_mapping()
    )
    intact_profile = CutoverProfileV1.from_mapping(profile.to_mapping())
    if (
        intact_binding.profile_fingerprint
        != intact_profile.profile_fingerprint
        or intact_binding.governing_master_commit
        != intact_profile.governing_master_commit
        or intact_binding.operator_fingerprint
        != intact_profile.operator_fingerprint
    ):
        raise ValueError
    assert_effect_snapshot_intact(effect)


def _chain_counts(
    chain: VerifiedJournalChainV1,
    pending: int,
    *,
    rejected: int,
) -> JournalOperationCountsV1:
    return JournalOperationCountsV1(
        records=chain.record_count,
        pending=pending,
        forward_committed=chain.forward_committed,
        reverse_committed=chain.reverse_committed,
        rejected=rejected,
    )


def _raw_counts(snapshot: object) -> tuple[int, int]:
    if type(snapshot) is not JournalMediumSnapshotV1:
        return 0, 0
    records = snapshot.published_records
    pending = snapshot.pending_records
    if type(records) is not tuple or type(pending) is not tuple:
        return 0, 0
    return min(len(records), 1_000_000), min(len(pending), 1_000_000)


def _result(
    status: JournalOperationStatus,
    phase: JournalOperationPhase,
    counts: JournalOperationCountsV1,
    *,
    binding: JournalOperationBindingV1,
    chain: VerifiedJournalChainV1,
    observation: str,
) -> JournalOperationResultV1:
    body = {
        "status": status.value,
        "phase": phase.value,
        "counts": counts.to_mapping(),
        "binding_fingerprint": binding.binding_fingerprint,
        "head_hash": chain.head_hash,
        "observation_fingerprint": observation,
    }
    receipt = hashlib.sha256(
        canonical_json(body, code="JOURNAL_RESULT_INVALID")
    ).hexdigest()
    return JournalOperationResultV1._create(
        status=status,
        receipt_fingerprint=receipt,
        phase=phase,
        counts=counts,
    )


def _incident_result(
    counts: JournalOperationCountsV1,
) -> JournalOperationResultV1:
    body = {
        "status": JournalOperationStatus.INCIDENT_STOP.value,
        "phase": JournalOperationPhase.CHAIN_VERIFICATION.value,
        "counts": counts.to_mapping(),
        "binding_fingerprint": ZERO_FINGERPRINT,
        "head_hash": ZERO_FINGERPRINT,
        "observation_fingerprint": ZERO_FINGERPRINT,
    }
    receipt = hashlib.sha256(
        canonical_json(body, code="JOURNAL_RESULT_INVALID")
    ).hexdigest()
    return JournalOperationResultV1._create(
        status=JournalOperationStatus.INCIDENT_STOP,
        receipt_fingerprint=receipt,
        phase=JournalOperationPhase.CHAIN_VERIFICATION,
        counts=counts,
    )
