"""Shared deterministic fixtures for dormant Execution Confirmation V1."""

from types import SimpleNamespace
from unittest.mock import patch

import backend.r2_production_binding.execution_confirmation as confirmation
from backend.r2_production_binding import (
    ExecutionConfirmationCandidateV1,
    ExecutionConfirmationClaimV1,
    ProductionCommandV2,
    confirm_execution_confirmation_v1,
    prepare_execution_confirmation_v1,
    production_action_fingerprint_v2,
)
from backend.r2_production_composition import build_production_binding_candidate_v1
from backend.r2_solo_maintainer_closure import FinalMasterBindingV1
from backend.r2_transaction_journal_v2 import (
    R2JournalGenesisV2,
    R2TransactionJournalV2,
)


ACKNOWLEDGEMENT = "CONFIRM_R2_ISSUE39_EXECUTION_V1_NOT_CLOSURE_ATTESTATION"
CLOSURE_MANIFEST = "8" * 64
SOLO_ATTESTATION = "9" * 64


class FakeExecutionClock:
    def __init__(
        self,
        *,
        prepared_at_epoch,
        prepared_monotonic_ns,
        confirmed_at_epoch,
        confirmed_monotonic_ns,
    ):
        self._wall_values = [prepared_at_epoch, confirmed_at_epoch]
        self._monotonic_values = [prepared_monotonic_ns, confirmed_monotonic_ns]

    def wall_epoch(self):
        return self._wall_values.pop(0)

    def monotonic_ns(self):
        return self._monotonic_values.pop(0)

    def set_confirmation(self, *, wall_epoch, monotonic_ns):
        self._wall_values[:] = [wall_epoch]
        self._monotonic_values[:] = [monotonic_ns]


class FakeExecutionConsole:
    def __init__(
        self,
        *,
        supplied_fingerprint=None,
        supplied_acknowledgement=ACKNOWLEDGEMENT,
        identity_after=None,
        pending_input=False,
    ):
        self.expected_fingerprint = None
        self.supplied_fingerprint = supplied_fingerprint
        self.supplied_acknowledgement = supplied_acknowledgement
        self.identity_after = identity_after
        self.pending_input = pending_input
        self.displayed = []
        self.fingerprint_read_count = 0
        self.acknowledgement_read_count = 0
        self.snapshot_count = 0
        self.pending_check_count = 0

    def snapshot(self):
        self.snapshot_count += 1
        if self.snapshot_count == 1 or self.identity_after is None:
            return (("stdin", 0, 10), ("stdout", 1, 11), ("stderr", 2, 12))
        return self.identity_after

    def display_confirmation(self, fingerprint, acknowledgement):
        self.displayed.extend((fingerprint, acknowledgement))

    def read_candidate_fingerprint(self):
        self.fingerprint_read_count += 1
        return (
            self.expected_fingerprint
            if self.supplied_fingerprint is None
            else self.supplied_fingerprint
        )

    def read_acknowledgement(self):
        self.acknowledgement_read_count += 1
        return self.supplied_acknowledgement

    def require_no_pending_input(self):
        self.pending_check_count += 1
        if self.pending_input:
            raise ValueError("pending input")


def final_master_binding(
    *,
    commit: str = "a" * 40,
) -> FinalMasterBindingV1:
    return FinalMasterBindingV1.create(
        final_commit_oid=commit,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )


def production_binding():
    return build_production_binding_candidate_v1(
        final_master_binding=final_master_binding(),
    )


def execution_candidate(
    binding=None,
    *,
    command=ProductionCommandV2.EXECUTE,
    action_fingerprint=None,
    closure_manifest=CLOSURE_MANIFEST,
    solo_attestation=SOLO_ATTESTATION,
    prior_head="3" * 64,
    journal_owner="2" * 64,
    transition="4" * 64,
    remaining_reverse_plan="0" * 64,
    claim_sequence=1,
    prepared_at_epoch=100,
    prepared_monotonic_ns=1_000_000_000,
    confirmed_at_epoch=102,
    confirmed_monotonic_ns=3_000_000_000,
    supplied_fingerprint=None,
    supplied_acknowledgement=ACKNOWLEDGEMENT,
    console_identity_after=None,
    pending_input=False,
) -> ExecutionConfirmationCandidateV1:
    value = binding or production_binding()
    action = action_fingerprint or production_action_fingerprint_v2(
        value,
        command,
    )
    clock = FakeExecutionClock(
        prepared_at_epoch=prepared_at_epoch,
        prepared_monotonic_ns=prepared_monotonic_ns,
        confirmed_at_epoch=confirmed_at_epoch,
        confirmed_monotonic_ns=confirmed_monotonic_ns,
    )
    console = FakeExecutionConsole(
        supplied_fingerprint=supplied_fingerprint,
        supplied_acknowledgement=supplied_acknowledgement,
        identity_after=console_identity_after,
        pending_input=pending_input,
    )
    ports = SimpleNamespace(clock=clock, console=console)
    with patch.object(
        confirmation,
        "_fixed_execution_confirmation_ports",
        return_value=ports,
        create=True,
    ):
        candidate = prepare_execution_confirmation_v1(
            binding=value,
            closure_manifest_fingerprint=closure_manifest,
            solo_maintainer_attestation_receipt_fingerprint=solo_attestation,
            command=command,
            action_fingerprint=action,
            journal_owner_fingerprint=journal_owner,
            prior_journal_head_fingerprint=prior_head,
            transition_instance_fingerprint=transition,
            remaining_reverse_plan_fingerprint=remaining_reverse_plan,
            claim_sequence=claim_sequence,
        )
    console.expected_fingerprint = candidate.candidate_fingerprint
    return candidate


def execution_claim(
    binding=None,
    *,
    candidate=None,
    confirmed_at_epoch=102,
    confirmed_monotonic_ns=3_000_000_000,
) -> ExecutionConfirmationClaimV1:
    value = candidate or execution_candidate(
        binding,
        confirmed_at_epoch=confirmed_at_epoch,
        confirmed_monotonic_ns=confirmed_monotonic_ns,
    )
    value._runtime.clock.set_confirmation(
        wall_epoch=confirmed_at_epoch,
        monotonic_ns=confirmed_monotonic_ns,
    )
    return confirm_execution_confirmation_v1(candidate=value)


def appended_execution_claim(
    binding,
    *,
    command,
    subject_fingerprint=None,
    action_factory=None,
    journal_owner="3" * 64,
    transition="5" * 64,
    remaining_reverse_plan="0" * 64,
):
    journal = _test_journal(binding, journal_owner)
    action = (
        action_factory(journal.current_head_fingerprint)
        if action_factory is not None
        else production_action_fingerprint_v2(
            binding,
            command,
            subject_fingerprint=subject_fingerprint,
        )
    )
    candidate = execution_candidate(
        binding,
        command=command,
        action_fingerprint=action,
        journal_owner=journal_owner,
        prior_head=journal.current_head_fingerprint,
        transition=transition,
        remaining_reverse_plan=remaining_reverse_plan,
        claim_sequence=2,
    )
    claim = execution_claim(binding, candidate=candidate)
    journal.append_execution_confirmation_claim(
        claim=claim,
        transition_instance_fingerprint=transition,
        observed_at_epoch=103,
        observed_monotonic_ns=4_000_000_000,
    )
    return claim


def _test_journal(binding, journal_owner):
    review = "a" * 64
    pre_genesis_head = "b" * 64
    candidate = execution_candidate(
        binding,
        command=ProductionCommandV2.EVIDENCE_PUBLICATION,
        action_fingerprint=production_action_fingerprint_v2(
            binding,
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            subject_fingerprint=review,
        ),
        journal_owner=journal_owner,
        prior_head=pre_genesis_head,
        transition=review,
    )
    genesis = R2JournalGenesisV2.create(
        binding=binding,
        reviewed_evidence_fingerprint=review,
        evidence_identity_fingerprint="c" * 64,
        package_fingerprint="d" * 64,
        manifest_fingerprint=CLOSURE_MANIFEST,
        journal_owner_fingerprint=journal_owner,
        genesis_nonce="e" * 64,
        pre_genesis_head_fingerprint=pre_genesis_head,
        execution_confirmation_claim=execution_claim(binding, candidate=candidate),
    )
    return R2TransactionJournalV2.create(
        binding=binding,
        genesis=genesis,
        observed_at_epoch=103,
        observed_monotonic_ns=4_000_000_000,
    )
