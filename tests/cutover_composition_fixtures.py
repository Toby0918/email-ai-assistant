"""Synthetic content-free fixtures for Issue #59 composition tests."""

from __future__ import annotations

from backend.cutover_composition_contracts import (
    CompositionBindingV1,
    CompositionStage,
    CompositionStageReceiptV1,
    UNBOUND_FINGERPRINT,
)
from backend.cutover_composition_contracts.authorization_sequence import (
    AUTHORIZATION_PHASES,
    _create_test_authorization_sequence,
)
from backend.cutover_contracts import CutoverProfileV1, TestSandboxAuthorizationV1
from tests.cutover_contract_fixtures import (
    opaque_fingerprint,
    valid_profile_body,
)


OBSERVED_AT = 1_900_000_000
OPERATION = opaque_fingerprint(9501)
JOURNAL_OWNER = opaque_fingerprint(9502)


def synthetic_context(
    *,
    expires_at_epoch: int = OBSERVED_AT + 300,
    operation_fingerprint: str = OPERATION,
):
    body = valid_profile_body()
    body["governing_master_commit"] = (
        "4dd5183c7cb2731f519b0516516d9c0eb4490804"
    )
    profile = CutoverProfileV1.create(body)
    authorizations = tuple(
        TestSandboxAuthorizationV1.create(
            profile_fingerprint=profile.profile_fingerprint,
            operation_fingerprint=operation_fingerprint,
            phase=phase,
            expires_at_epoch=expires_at_epoch,
        )
        for _kind, _operation, phase in AUTHORIZATION_PHASES
    )
    sequence = _create_test_authorization_sequence(
        profile=profile,
        operation_fingerprint=operation_fingerprint,
        authorizations=authorizations,
        observed_at_epoch=OBSERVED_AT,
    )
    binding = CompositionBindingV1.create(
        profile=profile,
        operation_fingerprint=operation_fingerprint,
        authorization_sequence=sequence,
    )
    return profile, sequence, binding


def stage_receipt(
    binding,
    stage: CompositionStage,
    prior: object,
    index: int,
    *,
    journal_bound: bool = False,
    valid_until_epoch: int = 0,
) -> CompositionStageReceiptV1:
    prior_fingerprint = (
        prior.receipt_fingerprint
        if type(prior) is CompositionStageReceiptV1
        else UNBOUND_FINGERPRINT
    )
    return CompositionStageReceiptV1.create(
        binding=binding,
        stage=stage,
        prior_receipt_fingerprint=prior_fingerprint,
        observation_fingerprint=opaque_fingerprint(9600 + index),
        journal_owner_fingerprint=(
            JOURNAL_OWNER if journal_bound else UNBOUND_FINGERPRINT
        ),
        prior_journal_head_fingerprint=(
            prior.journal_head_fingerprint
            if journal_bound
            and type(prior) is CompositionStageReceiptV1
            and prior.journal_owner_fingerprint != UNBOUND_FINGERPRINT
            else UNBOUND_FINGERPRINT
        ),
        journal_head_fingerprint=(
            opaque_fingerprint(9700 + index)
            if journal_bound
            else UNBOUND_FINGERPRINT
        ),
        valid_until_epoch=valid_until_epoch,
        accepted=1,
        rejected=0,
        worktrees=(
            11
            if stage
            in {
                CompositionStage.REPOSITORY_TRANSACTION,
                CompositionStage.ROLLBACK_RESTORATION,
                CompositionStage.LEGACY_HEALTH,
            }
            else 0
        ),
        provider_attempts=0,
    )
