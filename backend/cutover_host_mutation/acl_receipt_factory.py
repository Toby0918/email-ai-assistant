"""Closed content-free ACL receipt construction."""

from __future__ import annotations

from .receipts import (
    AclApplyReceiptV1,
    AclBaselineReceiptV1,
    AclCompatibilityReceiptV1,
    AclPostVerifyReceiptV1,
)
from .roles import AclFailureCode, AclReceiptStatus


def baseline_receipt(state, captured):
    return AclBaselineReceiptV1.create(
        status=AclReceiptStatus.ACCEPTED,
        failure_code=AclFailureCode.NONE,
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=(
            captured.observation.observation_fingerprint
        ),
        accepted=1,
        rejected=0,
        observed_objects=1,
    )


def compatibility_receipt(state, observation, compatible):
    return AclCompatibilityReceiptV1.create(
        status=(
            AclReceiptStatus.ACCEPTED
            if compatible
            else AclReceiptStatus.REJECTED
        ),
        failure_code=(
            AclFailureCode.NONE
            if compatible
            else AclFailureCode.COMPATIBILITY_REJECTED
        ),
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=observation.observation_fingerprint,
        accepted=1 if compatible else 0,
        rejected=0 if compatible else 1,
        observed_objects=observation.descriptors_observed,
    )


def apply_receipt(state, observation):
    return AclApplyReceiptV1.create(
        status=AclReceiptStatus.ACCEPTED,
        failure_code=AclFailureCode.NONE,
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=observation,
        accepted=1,
        rejected=0,
        observed_objects=1,
    )


def post_receipt(state, observation, count):
    return AclPostVerifyReceiptV1.create(
        status=AclReceiptStatus.ACCEPTED,
        failure_code=AclFailureCode.NONE,
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=observation,
        accepted=1,
        rejected=0,
        observed_objects=count,
    )


def rejected_compare(state, failure):
    return AclPostVerifyReceiptV1.create(
        status=AclReceiptStatus.REJECTED,
        failure_code=failure,
        profile_fingerprint=state.profile_fingerprint,
        authorization_fingerprint=state.authorization_fingerprint,
        policy_fingerprint=state.policy.policy_fingerprint,
        observation_fingerprint=state.root_identity,
        accepted=0,
        rejected=1,
        observed_objects=0,
    )
