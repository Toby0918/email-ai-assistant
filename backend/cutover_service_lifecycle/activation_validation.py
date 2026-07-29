"""Exact managed-publication and activation receipt validation."""

from __future__ import annotations

import uuid

from backend.cutover_managed_activation import ManagedActivationReceiptSetV1

from .activation_contracts import (
    NewServiceActivationReceiptV1,
    NewServiceStartRequestV1,
)
from .canonical import fail, fingerprint
from .failures import ActivationFailureKind, ServiceBoundaryFailure


def validated_publications(
    value, *, operation, profile, master, authorization
):
    if type(value) is not ManagedActivationReceiptSetV1:
        fail("service_publication_receipts_invalid")
    try:
        rebuilt = ManagedActivationReceiptSetV1.from_mapping(
            value.to_mapping()
        )
    except Exception:
        fail("service_publication_receipts_invalid")
    if (
        rebuilt != value
        or rebuilt.operation_fingerprint != operation
        or rebuilt.profile_fingerprint != profile
        or rebuilt.governing_master_commit != master
        or rebuilt.authorization_fingerprint != authorization
    ):
        fail("service_publication_receipts_invalid")
    return rebuilt


def start_request(receipts, profile):
    return NewServiceStartRequestV1.create(
        profile_fingerprint=profile,
        runtime_fingerprint=receipts.receipts[0].receipt_fingerprint,
        config_fingerprint=receipts.receipts[3].receipt_fingerprint,
        data_role_fingerprint=receipts.receipts[1].receipt_fingerprint,
        nonce=str(uuid.uuid4()),
    )


def activation_receipt(request, start, health, synthetic, result, row):
    values = (
        fingerprint(
            "issue58-start-evidence-v1",
            start.to_mapping(),
            code="service_activation_receipt_invalid",
        ),
        fingerprint(
            "issue58-health-evidence-v1",
            health.to_mapping(),
            code="service_activation_receipt_invalid",
        ),
        synthetic.request_fingerprint,
        result.result_fingerprint,
        row.data_role_fingerprint,
        request.config_fingerprint,
    )
    return NewServiceActivationReceiptV1.create(
        nonce=request.nonce,
        input_fingerprints=values,
    )


def boundary(kind: ActivationFailureKind) -> None:
    raise ServiceBoundaryFailure(kind) from None
