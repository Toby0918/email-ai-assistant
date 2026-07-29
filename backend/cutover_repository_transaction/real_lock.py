"""Real repository transaction construction remains locked before Issue #39."""

from __future__ import annotations

from backend.cutover_host_mutation.operator_entry import (
    MutationConstructorResult,
    MutationConstructorStatus,
    locked_real_mutation_constructor,
)

_MASTER = "96fceda6e85316dd6b17ef516adf96491d28cb6d"


def locked_real_repository_transaction_constructor(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
) -> MutationConstructorResult:
    if getattr(profile, "governing_master_commit", None) != _MASTER:
        return MutationConstructorResult(
            status=MutationConstructorStatus.BLOCKED_AUTHORIZATION_INVALID,
            blocked=1,
            constructed=0,
        )
    return locked_real_mutation_constructor(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )


__all__ = ["locked_real_repository_transaction_constructor"]
