"""Confirmed, durable, read-only production preflights for Issue #39."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from backend.r2_production_binding import (
    ProductionCommandV2,
    confirm_execution_confirmation_v1,
    prepare_execution_confirmation_v1,
    production_action_fingerprint_v2,
)

from .action_catalog import Issue39ProductionActionCatalogV1
from .closure_binding import _Issue39ClosureBindingV1
from .confirmation_context import display_confirmation_context_v1
from .preflight_ledger import (
    _append_preflight_claim_v1,
    _append_preflight_observation_v1,
    _open_preflight_ledger_v1,
)
from .preflight_observers import observe_fixed
from .preflight_progress import (
    AFTER,
    BEFORE,
    RECOVERY,
    Issue39PreflightReceiptV1,
    receipt,
    resume_subject,
    subject_fingerprint,
    transition,
    validated_progress,
)
from .preparation import Issue39PrepareStatusV1, Issue39PreparedExecutionV1
from .production_evidence import Issue39EvidencePackageV1


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39PreflightPortsV1:
    confirm: object = field(repr=False)
    observe: object = field(repr=False)
    open_ledger: object = field(repr=False)


def run_fixed_issue39_preflight_v1(
    prepared, closure, catalog, package, phase, prior=None
):
    return _run_issue39_preflight_v1(
        prepared=prepared, closure=closure, catalog=catalog,
        package=package, phase=phase, prior=prior,
        ports=_production_ports(prepared, closure, catalog, package),
    )


def _run_issue39_preflight_v1(
    *, prepared, closure, catalog, package, phase, prior=None, ports
):
    _require_inputs(prepared, closure, catalog, package, phase, prior, ports)
    commands = {
        "before_evidence": BEFORE,
        "after_evidence": AFTER,
        "recovery": RECOVERY,
    }[phase]
    subject = subject_fingerprint(prepared, closure, catalog)
    ledger = ports.open_ledger(
        binding=closure.production, package_fingerprint=subject
    )
    completed = validated_progress(ledger, subject)
    prior_count = 3 if phase == "after_evidence" else 5
    if prior is not None and prior != receipt(
        subject, ledger, completed, prior_count
    ):
        raise TypeError("R2_ISSUE39_PREFLIGHT_DRIFT")
    for command in commands:
        ledger = _run_command(
            ports, ledger, subject, command, completed
        )
        completed = validated_progress(ledger, subject)
    count = {"before_evidence": 3, "after_evidence": 5, "recovery": 6}[phase]
    return receipt(subject, ledger, completed, count)


def _run_command(ports, ledger, subject, command, completed):
    current = transition(subject, command)
    if command.value in completed:
        if ports.observe(command) != completed[command.value]:
            raise TypeError("R2_ISSUE39_PREFLIGHT_DRIFT")
        return ledger
    pending = ledger.records[-1] if (
        ledger.records and ledger.records[-1].kind == "claim"
    ) else None
    actual = ProductionCommandV2.RESUME if pending else command
    if pending and pending.transition_fingerprint != current:
        raise TypeError("R2_ISSUE39_PREFLIGHT_LEDGER_INVALID")
    claim, clock = ports.confirm(actual, command, current, ledger)
    ledger = _append_preflight_claim_v1(
        ledger, claim=claim, transition=current, **clock
    )
    observation = ports.observe(command)
    if not _fingerprint(observation):
        raise TypeError("R2_ISSUE39_PREFLIGHT_OBSERVATION_INVALID")
    return _append_preflight_observation_v1(
        ledger, command=command.value, transition=current,
        observation=observation,
    )


def _production_ports(prepared, closure, catalog, package):
    subject = subject_fingerprint(prepared, closure, catalog)
    owner = _hash(
        b"r2-issue39-preflight-owner-v1\0"
        + bytes.fromhex(closure.production.binding_fingerprint)
        + bytes.fromhex(subject)
    )

    def confirm(actual, command, current, ledger):
        sequence = sum(item.kind == "claim" for item in ledger.records) + 1
        action = production_action_fingerprint_v2(
            closure.production,
            actual,
            **({"subject_fingerprint": resume_subject(current, ledger.head)}
               if actual is ProductionCommandV2.RESUME else {}),
        )
        candidate = prepare_execution_confirmation_v1(
            binding=closure.production,
            closure_manifest_fingerprint=closure.manifest.manifest_fingerprint,
            solo_maintainer_attestation_receipt_fingerprint=closure.receipt.receipt_fingerprint,
            command=actual, action_fingerprint=action,
            journal_owner_fingerprint=owner,
            prior_journal_head_fingerprint=ledger.head,
            transition_instance_fingerprint=current,
            remaining_reverse_plan_fingerprint="0" * 64,
            claim_sequence=sequence,
        )
        display_confirmation_context_v1(
            phase="preflight",
            operation=command.value,
            command=actual,
            direction="none",
            current_state=(
                "PREFLIGHT_CLAIM_PENDING"
                if actual is ProductionCommandV2.RESUME
                else "READY_TO_OBSERVE"
            ),
            sequence=sequence,
            total=6,
        )
        claim = confirm_execution_confirmation_v1(candidate=candidate)
        return claim, {
            "observed_at_epoch": int(time.time()),
            "observed_monotonic_ns": time.monotonic_ns(),
        }

    return _Issue39PreflightPortsV1(
        confirm, lambda value: observe_fixed(value, prepared, catalog, package),
        _open_preflight_ledger_v1)


def _require_inputs(prepared, closure, catalog, package, phase, prior, ports):
    if (
        type(prepared) is not Issue39PreparedExecutionV1
        or prepared.status is not Issue39PrepareStatusV1.VERIFIED
        or type(closure) is not _Issue39ClosureBindingV1
        or type(catalog) is not Issue39ProductionActionCatalogV1
        or phase not in {"before_evidence", "after_evidence", "recovery"}
        or (phase == "before_evidence" and package is not None)
        or (phase != "before_evidence" and type(package) is not Issue39EvidencePackageV1)
        or (phase != "before_evidence" and type(prior) is not Issue39PreflightReceiptV1)
        or type(ports) is not _Issue39PreflightPortsV1
        or not all(callable(getattr(ports, name)) for name in (
            "confirm", "observe", "open_ledger"
        ))
    ):
        raise TypeError("R2_ISSUE39_PREFLIGHT_INVALID")


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _fingerprint(value):
    return type(value) is str and len(value) == 64 and all(
        item in "0123456789abcdef" for item in value
    )
