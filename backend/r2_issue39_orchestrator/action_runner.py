"""Durable append-before-effect execution of the fixed Issue #39 catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    ProductionCommandV2,
)
from backend.r2_transaction_journal_v2 import (
    EffectClassificationV2,
    R2TransactionJournalV2,
    TerminalStateV2,
)
from .action_catalog import (
    Issue39ProductionActionCatalogV1,
    Issue39ProductionActionV1,
)
from .durable_ledger import (
    Issue39LedgerStatusV1,
    _reopen_issue39_ledger_v1,
)
from .action_fingerprints import (
    confirmation_action_fingerprint as _confirmation_action_fingerprint,
    confirmation_context as _confirmation_context,
    inspection_fingerprint as _inspection_fingerprint,
    reverse_transition as _reverse_transition,
)
from .action_runner_support import (
    attempt_token as _attempt_token,
    committed_actions as _committed_actions,
    fingerprint as _fingerprint,
    persist as _persist,
    require_confirmation_claim as _require_confirmation_claim,
    stable_observation as _stable_observation,
)


class Issue39ActionRunStatusV1(str, Enum):
    SUCCEEDED = "ISSUE39_ACTION_CATALOG_SUCCEEDED"
    LEGACY_RECOVERED = "ISSUE39_ACTION_CATALOG_LEGACY_RECOVERED"
    SAFE_ABORT = "ISSUE39_ACTION_CATALOG_SAFE_ABORT"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, repr=False)
class Issue39ActionRunResultV1:
    status: Issue39ActionRunStatusV1
    committed: int
    reversed: int
    host_actions: int
    journal: R2TransactionJournalV2 | None = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39ActionRunnerPortsV1:
    confirm: object = field(repr=False)
    observe: object = field(repr=False)
    apply: object = field(repr=False)
    reverify: object = field(repr=False)
    recovery_inspect: object = field(repr=False)
    clock: object = field(repr=False)
    confirm_terminal: object = field(repr=False)
    terminal_audit: object = field(repr=False)
    legacy_audit: object = field(repr=False)
    partial: object = field(repr=False)
    evidence: object = field(default=None, repr=False)


def _run_issue39_action_catalog_v1(*, catalog, binding, location, ports):
    """Run or resume one fixed catalog; all injected ports are internal-only."""

    try:
        _require_inputs(catalog, binding, ports)
        reopened = _reopen_issue39_ledger_v1(location=location, binding=binding)
        if reopened.status is not Issue39LedgerStatusV1.VERIFIED:
            raise ValueError
        return _run_verified_journal(
            catalog, binding, location, ports, reopened.journal
        )
    except _SafeAbort as error:
        try:
            from .action_recovery import _recover

            return _recover(catalog, binding, location, ports, error.journal)
        except Exception:
            return _result(
                Issue39ActionRunStatusV1.INCIDENT_STOP,
                _committed_actions(catalog, error.journal), (), error.journal,
            )
    except Exception:
        from .action_failure import recover_after_failure

        return recover_after_failure(catalog, binding, location, ports)


def _run_verified_journal(catalog, binding, location, ports, journal):
    from .action_recovery import _has_reverse_activity, _recover, _resolve_pending
    from .terminal_seal import terminal_claim_pending, terminal_complete

    completed = terminal_complete(catalog, journal, ports)
    if completed is not None:
        return _completed_result(catalog, journal, completed)
    pending = terminal_claim_pending(catalog, journal)
    if pending is not None:
        journal = _finish_terminal(
            catalog, binding, location, ports, journal, pending
        )
        return _completed_result(catalog, journal, pending)
    journal = _resolve_pending(catalog, binding, location, ports, journal)
    if _has_reverse_activity(catalog, journal):
        return _recover(catalog, binding, location, ports, journal)
    committed = _committed_actions(catalog, journal)
    for action in catalog.actions[len(committed):]:
        journal = _run_forward(action, binding, location, ports, journal)
        committed = (*committed, action)
    journal = _start_terminal(
        catalog, binding, location, ports, journal,
        TerminalStateV2.CUTOVER_SUCCESS,
    )
    return _result(Issue39ActionRunStatusV1.SUCCEEDED, committed, (), journal)


def _completed_result(catalog, journal, state):
    committed = _committed_actions(catalog, journal)
    if state is TerminalStateV2.CUTOVER_SUCCESS:
        return _result(Issue39ActionRunStatusV1.SUCCEEDED, committed, (), journal)
    if state is not TerminalStateV2.LEGACY_FLAT_LAYOUT_RESTORED:
        raise ValueError
    return _result(
        Issue39ActionRunStatusV1.LEGACY_RECOVERED,
        committed, _reversed_terminal_actions(catalog, journal), journal,
    )


def _run_forward(action, binding, location, ports, journal):
    ports.reverify(action, "forward")
    if _stable_observation(ports, action) != action.pre_state_fingerprint:
        raise ValueError
    command = ProductionCommandV2(action.command)
    claim = ports.confirm(action, journal, command)
    _require_confirmation_claim(
        catalog=None,
        action=action,
        binding=binding,
        journal=journal,
        command=command,
        claim=claim,
    )
    pending = journal.append_execution_confirmation_claim(
        claim=claim,
        transition_instance_fingerprint=action.action_fingerprint,
        **ports.clock(),
    ).append_intent(
        transition_instance_fingerprint=action.action_fingerprint,
        pre_state_fingerprint=action.pre_state_fingerprint,
        post_state_fingerprint=action.post_state_fingerprint,
    )
    _persist(location, binding, journal, pending)
    ports.reverify(action, "forward")
    try:
        applied = ports.apply(action, "forward", _attempt_token(pending))
    except Exception:
        observed = _stable_observation(ports, action)
        if observed == action.pre_state_fingerprint:
            classified = pending.append_recovery_classification(
                transition_instance_fingerprint=action.action_fingerprint,
                observed_state_fingerprint=observed,
                classification=EffectClassificationV2.EFFECT_ABSENT_EXACT,
                inspection_receipt_fingerprint=_inspection_fingerprint(action, observed),
            )
            _persist(location, binding, pending, classified)
            raise _SafeAbort(classified)
        raise
    return _complete_forward(
        action, binding, location, ports, pending, applied
    )


def _complete_forward(action, binding, location, ports, pending, applied):
    if action.host_effect and (
        _stable_observation(ports, action) != action.post_state_fingerprint
    ):
        raise ValueError
    if not action.host_effect and applied != action.post_state_fingerprint:
        raise ValueError
    from .action_runner_support import effect_evidence

    evidence = effect_evidence(
        ports, action, "forward", action.post_state_fingerprint
    )
    complete = pending.append_effect_observation(
        transition_instance_fingerprint=action.action_fingerprint,
        observed_state_fingerprint=action.post_state_fingerprint,
        classification=EffectClassificationV2.EFFECT_PRESENT_EXACT,
        evidence_receipt_fingerprint=evidence,
    ).append_commit(
        transition_instance_fingerprint=action.action_fingerprint,
        committed_state_fingerprint=action.post_state_fingerprint,
        evidence_receipt_fingerprint=evidence,
    )
    _persist(location, binding, pending, complete)
    return complete


def _start_terminal(catalog, binding, location, ports, journal, state):
    from .terminal_seal import (
        append_terminal,
        require_terminal_claim,
        terminal_confirmation_action,
        terminal_transition,
    )

    ports.reverify(None, "terminal")
    audit = (
        ports.terminal_audit(catalog, journal.current_head_fingerprint)
        if state is TerminalStateV2.CUTOVER_SUCCESS
        else ports.legacy_audit(catalog, journal.current_head_fingerprint)
    )
    transition = terminal_transition(catalog, state)
    action_fingerprint = terminal_confirmation_action(
        catalog, journal, audit, state
    )
    claim = ports.confirm_terminal(
        catalog, journal, state, transition, action_fingerprint
    )
    require_terminal_claim(catalog, journal, claim, audit, state)
    pending = journal.append_execution_confirmation_claim(
        claim=claim,
        transition_instance_fingerprint=transition,
        **ports.clock(),
    )
    complete = append_terminal(catalog, pending, audit, state)
    _persist(location, binding, journal, complete)
    return complete


def _finish_terminal(catalog, binding, location, ports, journal, state):
    from .terminal_seal import append_terminal

    ports.reverify(None, "terminal")
    audit = (
        ports.terminal_audit(
            catalog,
            journal.records[-1].execution_confirmation_claim.prior_journal_head_fingerprint,
        )
        if state is TerminalStateV2.CUTOVER_SUCCESS
        else ports.legacy_audit(
            catalog,
            journal.records[-1].execution_confirmation_claim.prior_journal_head_fingerprint,
        )
    )
    complete = append_terminal(catalog, journal, audit, state)
    _persist(location, binding, journal, complete)
    return complete


def _require_inputs(catalog, binding, ports):
    if (
        type(catalog) is not Issue39ProductionActionCatalogV1
        or type(binding) is not ApprovedCutoverBindingV3
        or type(ports) is not _Issue39ActionRunnerPortsV1
        or not all(callable(getattr(ports, name)) for name in (
            "confirm", "observe", "apply", "reverify",
            "recovery_inspect", "clock",
            "confirm_terminal",
            "terminal_audit", "legacy_audit",
            "partial",
        ))
    ):
        raise TypeError


def _result(status, committed, reversed_actions, journal):
    effects = sum(action.host_effect for action in (*committed, *reversed_actions))
    return Issue39ActionRunResultV1(
        status, len(committed), len(reversed_actions),
        effects, journal,
    )


class _SafeAbort(Exception):
    def __init__(self, journal):
        self.journal = journal

def _reversed_terminal_actions(catalog, journal):
    from .action_recovery import _reversed_actions

    return _reversed_actions(catalog, journal)
