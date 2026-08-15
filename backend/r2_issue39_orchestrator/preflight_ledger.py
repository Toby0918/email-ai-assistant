"""Create-only confirmation and observation ledger for read-only preflights."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    ExecutionConfirmationClaimV1,
    ProductionCommandV2,
    production_action_fingerprint_v2,
)
from backend.r2_production_binding._canonical import (
    canonical_json as _binding_canonical_json,
)

from .durable_io import guard_directory, read_segment, write_segment
from .preflight_claim_validation import (
    complete_and_consume,
    validate_and_begin,
    validate_history,
)

_ROOT = Path(r"D:\IncidentArchives\email_ai_assistant\issue38")
_MAX_RECORDS = 24

@dataclass(frozen=True, slots=True, repr=False)
class _PreflightRecordV1:
    sequence: int
    kind: str
    command: str
    transition_fingerprint: str = field(repr=False)
    predecessor_fingerprint: str = field(repr=False)
    claim: ExecutionConfirmationClaimV1 | None = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    record_fingerprint: str = field(repr=False)

@dataclass(frozen=True, slots=True, repr=False)
class _PreflightLedgerV1:
    directory: Path = field(repr=False)
    binding: ApprovedCutoverBindingV3 = field(repr=False)
    owner_fingerprint: str = field(repr=False)
    records: tuple[_PreflightRecordV1, ...] = field(repr=False)

    @property
    def head(self):
        return self.records[-1].record_fingerprint if self.records else "0" * 64

def _open_preflight_ledger_v1(*, binding, package_fingerprint):
    _require_binding(binding, package_fingerprint)
    leaf = ".issue39-preflight-" + _fingerprint(
        "r2-issue39-preflight-location-v1",
        binding.binding_fingerprint + package_fingerprint,
    )
    directory = _ROOT / leaf
    owner = _owner(binding, package_fingerprint)
    if not os.path.lexists(directory):
        return _PreflightLedgerV1(directory, binding, owner, ())
    with guard_directory(directory, flush=False):
        paths = tuple(sorted(directory.iterdir(), key=lambda item: item.name))
        if len(paths) > _MAX_RECORDS:
            raise TypeError("R2_ISSUE39_PREFLIGHT_LEDGER_INVALID")
        records = []
        predecessor = "0" * 64
        for sequence, path in enumerate(paths, start=1):
            record = _parse_record(
                read_segment(path), binding, owner, sequence, predecessor
            )
            if path.name != _name(record):
                raise ValueError
            records.append(record)
            predecessor = record.record_fingerprint
    return _PreflightLedgerV1(directory, binding, owner, tuple(records))


def _append_preflight_claim_v1(
    ledger, *, claim, transition, observed_at_epoch, observed_monotonic_ns
):
    expected_action = (
        production_action_fingerprint_v2(
            ledger.binding, claim.command,
            subject_fingerprint=_resume_subject(transition, ledger.head),
        )
        if type(claim) is ExecutionConfirmationClaimV1
        and claim.command is ProductionCommandV2.RESUME
        else (
            production_action_fingerprint_v2(ledger.binding, claim.command)
            if type(claim) is ExecutionConfirmationClaimV1
            else None
        )
    )
    if (
        type(ledger) is not _PreflightLedgerV1
        or type(claim) is not ExecutionConfirmationClaimV1
        or claim.production_binding_fingerprint
        != ledger.binding.binding_fingerprint
        or claim.prior_journal_head_fingerprint != ledger.head
        or claim.transition_instance_fingerprint != transition
        or claim.claim_sequence != _claim_count(ledger) + 1
        or claim.action_fingerprint != expected_action
        or claim.journal_owner_fingerprint != ledger.owner_fingerprint
    ):
        raise TypeError("R2_ISSUE39_PREFLIGHT_LEDGER_INVALID")
    try:
        validate_and_begin(
            ledger, claim, observed_at_epoch, observed_monotonic_ns
        )
        appended = _append(
            ledger,
            kind="claim",
            command=claim.command.value,
            transition=transition,
            claim=claim,
            observation="0" * 64,
        )
        complete_and_consume(appended, claim)
        return appended
    except Exception:
        raise TypeError("R2_ISSUE39_PREFLIGHT_LEDGER_INVALID") from None


def _append_preflight_observation_v1(
    ledger, *, command, transition, observation
):
    if (
        type(ledger) is not _PreflightLedgerV1
        or not ledger.records
        or ledger.records[-1].kind != "claim"
        or ledger.records[-1].transition_fingerprint != transition
        or ledger.records[-1].command not in {command, "resume"}
        or not _is_fingerprint(observation)
    ):
        raise TypeError("R2_ISSUE39_PREFLIGHT_LEDGER_INVALID")
    return _append(
        ledger,
        kind="observation",
        command=command,
        transition=transition,
        claim=None,
        observation=observation,
    )


def _append(ledger, *, kind, command, transition, claim, observation):
    if len(ledger.records) >= _MAX_RECORDS:
        raise ValueError
    body = {
        "schema": "issue39-preflight-ledger-record-v1",
        "sequence": len(ledger.records) + 1,
        "kind": kind,
        "command": command,
        "transition_fingerprint": transition,
        "predecessor_fingerprint": ledger.head,
        "claim": None if claim is None else claim.to_mapping(),
        "observation_fingerprint": observation,
    }
    fingerprint = _record_fingerprint(body)
    payload = _canonical({**body, "record_fingerprint": fingerprint})
    record = _allocate_record(body, claim, fingerprint)
    if not os.path.lexists(ledger.directory):
        with guard_directory(ledger.directory.parent, flush=True):
            ledger.directory.mkdir(mode=0o700)
    with guard_directory(ledger.directory, flush=True):
        write_segment(ledger.directory / _name(record), payload)
        if read_segment(ledger.directory / _name(record)) != payload:
            raise ValueError
    reopened = _open_existing(
        ledger.directory, ledger.binding, ledger.owner_fingerprint
    )
    if reopened.records != (*ledger.records, record):
        raise ValueError
    return reopened


def _open_existing(directory, binding, owner):
    paths = tuple(sorted(directory.iterdir(), key=lambda item: item.name))
    records, predecessor = [], "0" * 64
    for sequence, path in enumerate(paths, start=1):
        record = _parse_record(
            read_segment(path), binding, owner, sequence, predecessor
        )
        if path.name != _name(record):
            raise ValueError
        records.append(record)
        predecessor = record.record_fingerprint
    result = _PreflightLedgerV1(directory, binding, owner, tuple(records))
    validate_history(result)
    return result


def _parse_record(payload, binding, owner, sequence, predecessor):
    source = json.loads(payload)
    if _canonical(source) != payload or set(source) != {
        "schema", "sequence", "kind", "command", "transition_fingerprint",
        "predecessor_fingerprint", "claim", "observation_fingerprint",
        "record_fingerprint",
    }:
        raise ValueError
    body = {key: source[key] for key in source if key != "record_fingerprint"}
    if (
        source["schema"] != "issue39-preflight-ledger-record-v1"
        or source["sequence"] != sequence
        or source["predecessor_fingerprint"] != predecessor
        or source["kind"] not in {"claim", "observation"}
        or not _is_fingerprint(source["transition_fingerprint"])
        or not _is_fingerprint(source["observation_fingerprint"])
        or source["record_fingerprint"] != _record_fingerprint(body)
    ):
        raise ValueError
    claim = None
    if source["kind"] == "claim":
        claim = ExecutionConfirmationClaimV1.from_json(
            _binding_canonical_json(source["claim"]), binding=binding
        )
        expected_action = (
            production_action_fingerprint_v2(
                binding, claim.command,
                subject_fingerprint=_resume_subject(
                    source["transition_fingerprint"], predecessor
                ),
            )
            if claim.command is ProductionCommandV2.RESUME
            else production_action_fingerprint_v2(binding, claim.command)
        )
        if (
            source["observation_fingerprint"] != "0" * 64
            or claim.command.value != source["command"]
            or claim.transition_instance_fingerprint
            != source["transition_fingerprint"]
            or claim.prior_journal_head_fingerprint != predecessor
            or claim.action_fingerprint != expected_action
            or claim.journal_owner_fingerprint != owner
        ):
            raise ValueError
    elif source["claim"] is not None or source["observation_fingerprint"] == "0" * 64:
        raise ValueError
    return _allocate_record(body, claim, source["record_fingerprint"])


def _allocate_record(body, claim, fingerprint):
    return _PreflightRecordV1(
        body["sequence"], body["kind"], body["command"],
        body["transition_fingerprint"], body["predecessor_fingerprint"],
        claim, body["observation_fingerprint"], fingerprint,
    )


def _claim_count(ledger):
    return sum(item.kind == "claim" for item in ledger.records)


def _name(record):
    return f"{record.sequence:06d}-{record.record_fingerprint}.p39"


def _record_fingerprint(body):
    return hashlib.sha256(
        b"r2-issue39-preflight-record-v1\0" + _canonical(body)
    ).hexdigest()


def _fingerprint(domain, value):
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + value.encode("ascii")
    ).hexdigest()


def _owner(binding, package):
    return hashlib.sha256(
        b"r2-issue39-preflight-owner-v1\0"
        + bytes.fromhex(binding.binding_fingerprint)
        + bytes.fromhex(package)
    ).hexdigest()


def _resume_subject(transition, head):
    return hashlib.sha256(
        b"r2-issue39-preflight-resume-action-v1\0"
        + bytes.fromhex(transition)
        + bytes.fromhex(head)
    ).hexdigest()


def _canonical(value):
    return (json.dumps(value, ensure_ascii=True, allow_nan=False,
                       sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def _require_binding(binding, package):
    if type(binding) is not ApprovedCutoverBindingV3 or not _is_fingerprint(package):
        raise TypeError("R2_ISSUE39_PREFLIGHT_LEDGER_INVALID")


def _is_fingerprint(value):
    return type(value) is str and len(value) == 64 and all(
        item in "0123456789abcdef" for item in value
    )
