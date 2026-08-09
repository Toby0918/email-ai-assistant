"""Deterministic UTF-8 Markdown renderer for the final R2 operator runbook."""

from __future__ import annotations

import hashlib

from backend.r2_production_binding.catalog import command_catalog_v2
from backend.r2_transaction_journal_v2._canonical import fingerprint

from .state_machine import (
    operator_package_semantics_fingerprint_v2,
    operator_state_machine_v2,
)
from .review_registry import (
    blocker_resolution_fingerprint_v2,
    decision_registry_fingerprint_v2,
    issue38_decision_registry_v2,
    r1_blocker_resolution_registry_v2,
)


def render_r2_operator_runbook_v2():
    catalog = command_catalog_v2()
    rules = operator_state_machine_v2()
    lines = [
        "---", "last_update: 2026-08-07", "status: active",
        'owner: "@tobyWang"', "review_cycle: as_needed",
        "source_type: operation_guide", "---", "",
        "# Final R2 Operator Runbook", "",
        "Generated from the latent R2 command catalog and state machine; do not hand edit command semantics.",
        "",
        f"- Catalog fingerprint: `{_catalog_fingerprint()}`",
        f"- State-machine fingerprint: `{_state_fingerprint()}`",
        f"- Package-semantics fingerprint: `{operator_package_semantics_fingerprint_v2()}`",
        f"- Decision-registry fingerprint: `{decision_registry_fingerprint_v2()}`",
        f"- R1-blocker-resolution fingerprint: `{blocker_resolution_fingerprint_v2()}`",
        "- Issue #110 production result: `DORMANT_NO_ISSUE39_APPROVAL` before argv, TTY, confirmation, Adapter, journal, callback, or host access.",
        "- Assurance model: `SOLE_MAINTAINER_SELF_REVIEW`; Issue #39 authority count: `0`.",
        "", "## Latent command catalog", "",
        "| # | Surface | Verb | Command | Effect | Non-authorizing catalog acknowledgement | Max operations |",
        "| ---: | --- | --- | --- | --- | --- | ---: |",
    ]
    lines.extend(_command_line(item) for item in catalog)
    lines.extend(["", "## Latent post-approval state machine", "", "| Phase | Allowed commands | Next phases | Required evidence |", "| --- | --- | --- | --- |"])
    lines.extend(_state_line(item) for item in rules)
    lines.extend(_review_sections())
    lines.extend(_fixed_sections())
    return ("\n".join(lines) + "\n").encode("utf-8")


def runbook_document_fingerprint_v2():
    document = render_r2_operator_runbook_v2()
    return hashlib.sha256(b"r2-operator-runbook-document-v2\0" + document).hexdigest()


def _catalog_fingerprint():
    return fingerprint("r2-operator-command-catalog-v2", [item.to_mapping() for item in command_catalog_v2()])


def _state_fingerprint():
    return fingerprint("r2-operator-state-machine-v2", [item.to_mapping() for item in operator_state_machine_v2()])


def _command_line(item):
    return f"| {item.ordinal + 1} | `{item.surface.value}` | `{item.verb}` | `{item.command.value}` | `{item.effect.value}` | `{item.acknowledgement}` | {item.max_operations} |"


def _state_line(item):
    commands = ", ".join(f"`{value}`" for value in item.allowed_commands) or "none"
    next_phases = ", ".join(f"`{value.value}`" for value in item.next_phases) or "terminal"
    evidence = ", ".join(f"`{value}`" for value in item.required_evidence)
    return f"| `{item.phase.value}` | {commands} | {next_phases} | {evidence} |"


def _review_sections():
    lines = [
        "", "## Issue #38 decision registry", "",
        "Every row is re-reviewed exactly once against the frozen final master; historical R1 values are not current authority.",
        "", "| # | Decision ID | Decision | R2 completion proof |",
        "| ---: | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.ordinal + 1} | `{item.decision_id}` | {item.title} | {item.completion_proof} |"
        for item in issue38_decision_registry_v2()
    )
    lines.extend([
        "", "## R1 blocker completion map", "",
        "| Historical blocker | Blocker class | R2 completion proof |",
        "| --- | --- | --- |",
    ])
    lines.extend(
        f"| Issue #{item.issue} | {item.blocker_class} | {item.completion_proof} |"
        for item in r1_blocker_resolution_registry_v2()
    )
    return lines


def _fixed_sections():
    return [
        "", "## Issue #110 reachability boundary", "",
        "All ten catalog commands are latent. Every fixed production verb returns `DORMANT_NO_ISSUE39_APPROVAL` before reading argv, TTY, clock, acknowledgement, confirmation, bootstrap, Adapter, journal, callback, environment, file, or artifact state.",
        "", "No Solo Maintainer closure manifest, attestation receipt, hosted check, CI result, runbook, bootstrap object, environment value, file, argument, acknowledgement, or synthetic marker can unlock a production root. Issue #38 approval and a separate Issue #39 code allowlist are required before any future wiring.",
        "", "## Execution Confirmation boundary", "",
        "A future action uses exactly one fresh, single-use `ExecutionConfirmationClaimV1` bound to the V3 production binding, closure manifest and attestation, exact command/action, current journal head, next sequence, transition, and remaining reverse plan.",
        "", "The future exact acknowledgement is `CONFIRM_R2_ISSUE39_EXECUTION_V1_NOT_CLOSURE_ATTESTATION`. A claim must be durably appended before one Adapter attempt and becomes consumed by that attempt even on failure. The Issue #110 executable graph cannot reach preparation, confirmation, append, Adapter acquisition, or invocation.",
        "", "## Forward and recovery rules", "",
        "After a future separate enablement, each invocation accepts exactly one catalog verb and at most one operation. A crash requires two-read `recovery-inspection`; exact PRE requires a new Execution Confirmation, exact POST commits without replay, and ambiguity incident-stops. Rollback is journal-derived LIFO, preserves the failed Container first, and ends only at `LEGACY_FLAT_LAYOUT_RESTORED`.",
        "", "## Retention and no-deletion rule", "",
        "After forward, resume, rollback, or recovery, reconcile the deterministic object-level retention ledger. Original, new, partial, failed, evidence, and journal artifacts remain tracked with zero deletion capability, zero overwrite/prune/automatic-expiry capability, and zero private payload fields.",
        "", "## Drift and decision boundary", "",
        "Reject a stale final master, stale source-package hash, mixed V3 binding, changed catalog/state-machine fingerprint, unknown verb, or historical R1 package semantics. This document, Hosted Evidence, CI, synthetic evidence, Solo Maintainer Attestation, and closure receipts are never Issue #38 approval or Issue #39 execution authority.",
        "", "The verifier can establish only `ELIGIBLE_FOR_ISSUE38_FINAL_REVIEW`. Issue #38 remains a separate fresh decision and Issue #39 remains blocked.",
    ]
