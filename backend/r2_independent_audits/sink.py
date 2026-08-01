"""Pre-bound single-use append capability for an independent audit."""

from __future__ import annotations

import hashlib
import json
import os
import secrets

from backend.cutover_composition_contracts.canonical import is_fingerprint

from .contracts import (
    AuditDisposition,
    AuditKind,
    IndependentAuditObservationV1,
    IndependentAuditResult,
    IndependentFinalRunningHealthReceiptV1,
    IndependentStoppedLayoutAuditReceiptV1,
)


class IndependentAuditAttestationSinkV1:
    __slots__ = (
        "_append",
        "_binding",
        "_consumed",
        "_health",
        "_head",
        "_identities",
        "_kind",
        "_now",
        "_observed",
        "_operation",
        "_process_id",
        "_sink_nonce",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("IndependentAuditAttestationSinkV1 requires bind()")

    def __reduce__(self):
        raise TypeError("INDEPENDENT_AUDIT_SINK_NOT_TRANSFERABLE")

    @classmethod
    def bind(cls, **values):
        expected = {
            "kind",
            "operation_fingerprint",
            "approved_binding_fingerprint",
            "journal_head_fingerprint",
            "approved_identities_fingerprint",
            "health_evidence_fingerprint",
            "observed_at_epoch",
            "process_id",
            "now",
            "append_attestation",
        }
        fingerprints = tuple(
            values.get(name)
            for name in (
                "operation_fingerprint",
                "approved_binding_fingerprint",
                "journal_head_fingerprint",
                "approved_identities_fingerprint",
                "health_evidence_fingerprint",
            )
        )
        if (
            type(values) is not dict
            or set(values) != expected
            or type(values["kind"]) is not AuditKind
            or not all(is_fingerprint(value) for value in fingerprints)
            or type(values["observed_at_epoch"]) is not int
            or values["observed_at_epoch"] < 0
            or type(values["process_id"]) is not int
            or values["process_id"] <= 0
            or not callable(values["now"])
            or not callable(values["append_attestation"])
        ):
            raise ValueError("R2_INDEPENDENT_AUDIT_SINK_BINDING_INVALID")
        sink = object.__new__(cls)
        sink._kind = values["kind"]
        sink._operation = fingerprints[0]
        sink._binding = fingerprints[1]
        sink._head = fingerprints[2]
        sink._identities = fingerprints[3]
        sink._health = fingerprints[4]
        sink._observed = values["observed_at_epoch"]
        sink._process_id = values["process_id"]
        sink._now = values["now"]
        sink._append = values["append_attestation"]
        sink._sink_nonce = secrets.token_hex(32)
        sink._consumed = False
        return sink

    def attest(self, observation: object) -> IndependentAuditResult:
        if not self._consume():
            return IndependentAuditResult(AuditDisposition.INCIDENT_STOP, None)
        if type(observation) is not IndependentAuditObservationV1:
            return IndependentAuditResult(AuditDisposition.INCIDENT_STOP, None)
        now = self._now()
        if (
            type(now) is not int
            or now < self._observed
            or os.getpid() != self._process_id
        ):
            return IndependentAuditResult(AuditDisposition.INCIDENT_STOP, None)
        if now > self._observed + 300:
            return IndependentAuditResult(AuditDisposition.EXPIRED, None)
        if (
            observation.audit_kind is not self._kind
            or observation.operation_fingerprint != self._operation
            or observation.approved_binding_fingerprint != self._binding
            or observation.observed_at_epoch != self._observed
            or not observation.unambiguous
        ):
            return IndependentAuditResult(AuditDisposition.INCIDENT_STOP, None)
        if not self._matched(observation):
            return IndependentAuditResult(
                AuditDisposition.ROLLBACK_REQUIRED, None
            )
        attestation = self._attestation()
        try:
            self._append(attestation)
        except Exception:
            return IndependentAuditResult(AuditDisposition.INCIDENT_STOP, None)
        return IndependentAuditResult(
            AuditDisposition.ATTESTED,
            self._make_receipt(attestation["attestation_fingerprint"]),
        )

    def _consume(self) -> bool:
        if self._consumed:
            return False
        self._consumed = True
        return True

    def _matched(self, observation: IndependentAuditObservationV1) -> bool:
        return (
            observation.journal_head_fingerprint == self._head
            and observation.approved_identities_fingerprint == self._identities
            and observation.health_evidence_fingerprint == self._health
        )

    def _make_receipt(self, attestation_fingerprint: str):
        receipt_type = (
            IndependentStoppedLayoutAuditReceiptV1
            if self._kind is AuditKind.STOPPED_LAYOUT
            else IndependentFinalRunningHealthReceiptV1
        )
        receipt = object.__new__(receipt_type)
        values = {
            "attestation_fingerprint": attestation_fingerprint,
            "journal_head_fingerprint": self._head,
            "approved_identities_fingerprint": self._identities,
            "observed_at_epoch": self._observed,
            "expires_at_epoch": self._observed + 300,
            "process_id": self._process_id,
        }
        if self._kind is AuditKind.FINAL_RUNNING_HEALTH:
            values["health_evidence_fingerprint"] = self._health
        for name, value in values.items():
            object.__setattr__(receipt, name, value)
        return receipt

    def _attestation(self) -> dict[str, object]:
        material = json.dumps(
            {
                "kind": self._kind.value,
                "operation": self._operation,
                "binding": self._binding,
                "head": self._head,
                "identities": self._identities,
                "health": self._health,
                "observed": self._observed,
                "process": self._process_id,
                "sink": self._sink_nonce,
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return {
            "attestation_type": "IndependentAuditAttestationV1",
            "audit_kind": self._kind.value,
            "attestation_fingerprint": hashlib.sha256(material).hexdigest(),
            "observed_at_epoch": self._observed,
            "expires_at_epoch": self._observed + 300,
        }
