"""Synthetic-only binding for an independent audit invocation."""

from __future__ import annotations

import os

from backend.cutover_composition_contracts.canonical import fingerprint

from .contracts import (
    AuditKind,
    IndependentFinalRunningHealthReceiptV1,
    IndependentStoppedLayoutAuditReceiptV1,
    _issue_receipt,
)

from .process import IndependentAuditProcess
from .sink import IndependentAuditAttestationSinkV1


class SyntheticIndependentAudit:
    __slots__ = ("_process",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticIndependentAudit requires create()")

    @classmethod
    def create(cls, **values):
        sink = IndependentAuditAttestationSinkV1.bind(
            **values,
            process_id=os.getpid(),
        )
        audit = object.__new__(cls)
        audit._process = IndependentAuditProcess.create(sink)
        return audit

    def run(self, observation):
        return self._process.run(observation)


def issue_verified_test_receipt(
    *,
    kind,
    process_id,
    journal_head_fingerprint,
    approved_identities_fingerprint,
    health_evidence_fingerprint,
    observed_at_epoch,
):
    """Issue only from synthetic binders after their process proof."""
    if type(kind) is not AuditKind or type(process_id) is not int or process_id <= 0:
        raise ValueError("R2_TEST_AUDIT_PROCESS_INVALID")
    receipt_type = (
        IndependentStoppedLayoutAuditReceiptV1
        if kind is AuditKind.STOPPED_LAYOUT
        else IndependentFinalRunningHealthReceiptV1
    )
    return _issue_receipt(
        receipt_type,
        {
            "attestation_fingerprint": fingerprint(
                "r2-test-audit-attestation-v1",
                [kind.value, process_id, journal_head_fingerprint],
            ),
            "journal_head_fingerprint": journal_head_fingerprint,
            "approved_identities_fingerprint": approved_identities_fingerprint,
            "health_evidence_fingerprint": health_evidence_fingerprint,
            "observed_at_epoch": observed_at_epoch,
            "expires_at_epoch": observed_at_epoch + 300,
            "process_id": process_id,
        },
    )


def verify_worker_attestation(
    *,
    kind,
    values,
    challenge,
    process_id,
    journal_head_fingerprint,
    approved_identities_fingerprint,
    health_evidence_fingerprint,
    observed_at_epoch,
):
    expected = {
        "attestation_fingerprint",
        "journal_head_fingerprint",
        "approved_identities_fingerprint",
        "health_evidence_fingerprint",
        "observed_at_epoch",
        "expires_at_epoch",
        "process_id",
        "challenge_response",
        "journal_entries",
    }
    bindings = (
        process_id,
        journal_head_fingerprint,
        approved_identities_fingerprint,
        health_evidence_fingerprint,
        observed_at_epoch,
    )
    if not _valid_worker_values(kind, values, expected, challenge, bindings):
        raise ValueError("R2_AUDIT_PROCESS_ATTESTATION_INVALID")
    receipt_type = (
        IndependentStoppedLayoutAuditReceiptV1
        if kind is AuditKind.STOPPED_LAYOUT
        else IndependentFinalRunningHealthReceiptV1
    )
    receipt_values = {
        name: values[name]
        for name in expected
        if name not in {"challenge_response", "journal_entries"}
    }
    return _issue_receipt(receipt_type, receipt_values)


def _valid_worker_values(kind, values, expected, challenge, bindings):
    process_id, head, identities, health, observed = bindings
    if type(values) is not dict or set(values) != expected:
        return False
    challenge_response = fingerprint(
        "r2-audit-process-challenge-v1",
        [challenge, values["attestation_fingerprint"], process_id],
    )
    return (
        type(kind) is AuditKind
        and values["process_id"] == process_id
        and values["journal_entries"] == 1
        and values["journal_head_fingerprint"] == head
        and values["approved_identities_fingerprint"] == identities
        and values["health_evidence_fingerprint"] == health
        and values["observed_at_epoch"] == observed
        and values["expires_at_epoch"] == observed + 300
        and values["challenge_response"] == challenge_response
    )
