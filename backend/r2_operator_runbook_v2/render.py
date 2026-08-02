"""Deterministic UTF-8 Markdown renderer for the final R2 operator runbook."""

from __future__ import annotations

import hashlib

from backend.r2_production_binding.catalog import command_catalog_v2
from backend.r2_transaction_journal_v2._canonical import fingerprint

from .state_machine import (
    operator_package_semantics_fingerprint_v2,
    operator_state_machine_v2,
)


def render_r2_operator_runbook_v2():
    catalog = command_catalog_v2()
    rules = operator_state_machine_v2()
    lines = [
        "---", "last_update: 2026-08-02", "status: active",
        'owner: "@tobyWang"', "review_cycle: as_needed",
        "source_type: operation_guide", "---", "",
        "# Final R2 Operator Runbook", "",
        "Generated from the executable R2 command catalog and state machine; do not hand edit command semantics.",
        "",
        f"- Catalog fingerprint: `{_catalog_fingerprint()}`",
        f"- State-machine fingerprint: `{_state_fingerprint()}`",
        f"- Package-semantics fingerprint: `{operator_package_semantics_fingerprint_v2()}`",
        "- Default production result: `DORMANT_NO_EXTERNAL_ISSUER` until separately supplied valid authority.",
        "", "## Executable command catalog", "",
        "| # | Surface | Verb | Command | Effect | Acknowledgement | Max operations |",
        "| ---: | --- | --- | --- | --- | --- | ---: |",
    ]
    lines.extend(_command_line(item) for item in catalog)
    lines.extend(["", "## State machine", "", "| Phase | Allowed commands | Next phases | Required evidence |", "| --- | --- | --- | --- |"])
    lines.extend(_state_line(item) for item in rules)
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


def _fixed_sections():
    return [
        "", "## Forward and recovery rules", "",
        "Each invocation accepts exactly one catalog verb and at most one operation. `execute`, `resume`, and `rollback` require fresh single-use authority bound to the current unified-journal head and exact remaining plan.",
        "", "A crash requires two-read `recovery-inspection`. Exact PRE requires fresh authority; exact POST commits without replay; ambiguity incident-stops. Rollback is journal-derived LIFO, preserves the failed Container first, and ends only at `LEGACY_FLAT_LAYOUT_RESTORED`.",
        "", "## Retention and no-deletion rule", "",
        "After forward, resume, rollback, or recovery, reconcile the deterministic object-level retention ledger. Original, new, partial, failed, evidence, and journal artifacts remain tracked with zero deletion capability, zero overwrite/prune/automatic-expiry capability, and zero private payload fields.",
        "", "## Drift and authority boundary", "",
        "Reject a stale final master, stale source-package hash, mixed binding, changed catalog/state-machine fingerprint, unknown verb, or historical R1 package semantics. This document, CI, synthetic evidence, and closure receipts are never execution authority.",
        "", "Human final review and Issue #38 approval remain separate manual decisions. Issue #39 remains blocked until that approval.",
    ]
