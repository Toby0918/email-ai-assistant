"""Closed preflight order, transitions, and prefix receipts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from backend.r2_production_binding import ProductionCommandV2


BEFORE = (
    ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
    ProductionCommandV2.HOST_BASELINE,
    ProductionCommandV2.EVIDENCE_REVIEW,
)
AFTER = (
    ProductionCommandV2.EVIDENCE_VERIFICATION,
    ProductionCommandV2.FINAL_AUDIT_READINESS,
)
RECOVERY = (ProductionCommandV2.RECOVERY_INSPECTION,)
ALL = (*BEFORE, *AFTER, *RECOVERY)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39PreflightReceiptV1:
    subject_fingerprint: str = field(repr=False)
    ledger_head_fingerprint: str = field(repr=False)
    observation_fingerprints: tuple[str, ...] = field(repr=False)
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("Issue39PreflightReceiptV1 is observer-owned")


def validated_progress(ledger, subject):
    result = {}
    cursor = 0
    while cursor < len(ledger.records):
        claim = ledger.records[cursor]
        if claim.kind != "claim" or len(result) >= len(ALL):
            _invalid()
        command = ALL[len(result)]
        expected = transition(subject, command)
        if claim.transition_fingerprint != expected or claim.command != command.value:
            _invalid()
        cursor += 1
        while cursor < len(ledger.records) and ledger.records[cursor].kind == "claim":
            resumed = ledger.records[cursor]
            if (
                resumed.command != ProductionCommandV2.RESUME.value
                or resumed.transition_fingerprint != expected
            ):
                _invalid()
            cursor += 1
        if cursor == len(ledger.records):
            break
        observation = ledger.records[cursor]
        if (
            observation.kind != "observation"
            or observation.command != command.value
            or observation.transition_fingerprint != expected
        ):
            _invalid()
        result[command.value] = observation.observation_fingerprint
        cursor += 1
    return result


def subject_fingerprint(prepared, closure, catalog):
    return _hash(
        b"r2-issue39-preflight-subject-v1\0"
        + bytes.fromhex(prepared.prepare_fingerprint)
        + bytes.fromhex(closure.production.binding_fingerprint)
        + bytes.fromhex(catalog.catalog_fingerprint)
    )


def transition(subject, command):
    return _hash(
        b"r2-issue39-preflight-transition-v1\0"
        + bytes.fromhex(subject) + command.value.encode("ascii")
    )


def resume_subject(transition_fingerprint, head):
    return _hash(
        b"r2-issue39-preflight-resume-action-v1\0"
        + bytes.fromhex(transition_fingerprint) + bytes.fromhex(head)
    )


def receipt(subject, ledger, completed, count):
    observations = tuple(completed[command.value] for command in ALL[:count])
    head = _prefix_head(ledger, count)
    body = json.dumps(
        {
            "subject_fingerprint": subject,
            "ledger_head_fingerprint": head,
            "observation_fingerprints": list(observations),
        },
        sort_keys=True, separators=(",", ":"),
    ).encode("ascii")
    value = object.__new__(Issue39PreflightReceiptV1)
    for name, item in (
        ("subject_fingerprint", subject),
        ("ledger_head_fingerprint", head),
        ("observation_fingerprints", observations),
        ("receipt_fingerprint", _hash(b"r2-issue39-preflight-receipt-v1\0" + body)),
    ):
        object.__setattr__(value, name, item)
    return value


def _prefix_head(ledger, count):
    observations = 0
    for record in ledger.records:
        if record.kind == "observation":
            observations += 1
            if observations == count:
                return record.record_fingerprint
    _invalid()


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _invalid():
    raise TypeError("R2_ISSUE39_PREFLIGHT_LEDGER_INVALID")
