"""Fixed live Execution Confirmation adapter for Issue #39 catalog actions."""

from __future__ import annotations

import time

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    ProductionCommandV2,
    confirm_execution_confirmation_v1,
    prepare_execution_confirmation_v1,
)
from backend.r2_transaction_journal_v2 import EffectClassificationV2

from .action_runner import (
    _confirmation_action_fingerprint,
    _confirmation_context,
)
from .action_recovery_state import transition_context
from .closure_binding import _Issue39ClosureBindingV1
from .confirmation_context import display_confirmation_context_v1


class FixedIssue39ActionConfirmerV1:
    __slots__ = ("_closure", "_binding", "_catalog", "_last_clock")

    def __init__(self, *args, **kwargs):
        raise TypeError("FixedIssue39ActionConfirmerV1 requires create()")

    @classmethod
    def create(cls, *, closure, catalog):
        if type(closure) is not _Issue39ClosureBindingV1:
            raise TypeError("R2_ISSUE39_CONFIRMATION_BINDING_INVALID")
        binding = closure.production
        if type(binding) is not ApprovedCutoverBindingV3:
            raise TypeError("R2_ISSUE39_CONFIRMATION_BINDING_INVALID")
        value = object.__new__(cls)
        value._closure = closure
        value._binding = binding
        value._catalog = catalog
        value._last_clock = None
        return value

    def confirm(self, action, journal, command):
        transition, remaining = _confirmation_context(
            self._catalog, action, journal, command
        )
        candidate = prepare_execution_confirmation_v1(
            binding=self._binding,
            closure_manifest_fingerprint=(
                self._closure.manifest.manifest_fingerprint
            ),
            solo_maintainer_attestation_receipt_fingerprint=(
                self._closure.receipt.receipt_fingerprint
            ),
            command=command,
            action_fingerprint=_confirmation_action_fingerprint(
                action, journal, command, transition, remaining
            ),
            journal_owner_fingerprint=journal.journal_owner_fingerprint,
            prior_journal_head_fingerprint=journal.current_head_fingerprint,
            transition_instance_fingerprint=transition,
            remaining_reverse_plan_fingerprint=remaining,
            claim_sequence=len(journal.execution_confirmation_claims) + 1,
        )
        direction, current_state = _action_display_state(
            self._catalog, action, journal, command
        )
        display_confirmation_context_v1(
            phase="catalog",
            operation=action.action_name,
            command=command,
            direction=direction,
            current_state=current_state,
            sequence=action.sequence,
            total=self._catalog.action_count,
        )
        claim = confirm_execution_confirmation_v1(candidate=candidate)
        self._last_clock = {
            "observed_at_epoch": int(time.time()),
            "observed_monotonic_ns": time.monotonic_ns(),
        }
        return claim

    def clock(self):
        if type(self._last_clock) is not dict:
            raise TypeError("R2_ISSUE39_CONFIRMATION_CLOCK_INVALID")
        return dict(self._last_clock)

    def confirm_terminal(
        self, catalog, journal, state, transition, action_fingerprint
    ):
        if catalog is not self._catalog:
            raise TypeError("R2_ISSUE39_CONFIRMATION_BINDING_INVALID")
        command = (
            ProductionCommandV2.RESUME
            if state.value == "CUTOVER_SUCCESS"
            else ProductionCommandV2.ROLLBACK
        )
        candidate = prepare_execution_confirmation_v1(
            binding=self._binding,
            closure_manifest_fingerprint=(
                self._closure.manifest.manifest_fingerprint
            ),
            solo_maintainer_attestation_receipt_fingerprint=(
                self._closure.receipt.receipt_fingerprint
            ),
            command=command,
            action_fingerprint=action_fingerprint,
            journal_owner_fingerprint=journal.journal_owner_fingerprint,
            prior_journal_head_fingerprint=journal.current_head_fingerprint,
            transition_instance_fingerprint=transition,
            remaining_reverse_plan_fingerprint="0" * 64,
            claim_sequence=len(journal.execution_confirmation_claims) + 1,
        )
        succeeded = state.value == "CUTOVER_SUCCESS"
        display_confirmation_context_v1(
            phase="terminal",
            operation=(
                "cutover_success_seal"
                if succeeded
                else "legacy_restoration_seal"
            ),
            command=command,
            direction="none",
            current_state=(
                "FINAL_AUDIT_EXACT" if succeeded else "LEGACY_AUDIT_EXACT"
            ),
            sequence=catalog.action_count + 1,
            total=catalog.action_count + 1,
        )
        claim = confirm_execution_confirmation_v1(candidate=candidate)
        self._last_clock = {
            "observed_at_epoch": int(time.time()),
            "observed_monotonic_ns": time.monotonic_ns(),
        }
        return claim


def _action_display_state(catalog, action, journal, command):
    if not any(action is item for item in catalog.actions):
        raise TypeError("R2_ISSUE39_CONFIRMATION_CONTEXT_INVALID")
    if command is ProductionCommandV2.ROLLBACK:
        return "rollback", "POST_STATE_EXACT"
    if command is not ProductionCommandV2.RESUME:
        return "forward", "PRE_STATE_EXACT"
    try:
        record = journal.records[-1]
        _matched, direction = transition_context(
            catalog, record.transition_instance_fingerprint
        )
        states = {
            EffectClassificationV2.EFFECT_ABSENT_EXACT: "EFFECT_ABSENT_EXACT",
            EffectClassificationV2.EFFECT_PRESENT_EXACT: "EFFECT_PRESENT_EXACT",
            EffectClassificationV2.EFFECT_PARTIAL_RESUMABLE: (
                "EFFECT_PARTIAL_RESUMABLE"
            ),
        }
        return direction, states[record.effect_classification]
    except (AttributeError, IndexError, KeyError, ValueError):
        raise TypeError("R2_ISSUE39_CONFIRMATION_CONTEXT_INVALID") from None
