"""Unified append-only journal and read-only inspection for Issue #93."""

from __future__ import annotations

import json
import unittest

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    ExecutionConfirmationClaimV1,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    production_action_fingerprint_v2,
)
from backend.r2_solo_maintainer_closure import FinalMasterBindingV1
from backend.r2_transaction_journal_v2 import (
    EffectClassificationV2,
    JournalV2Error,
    R2JournalGenesisV2,
    R2StateObservationV2,
    R2TransactionJournalV2,
    inspect_pending_transition_v2,
)
from tests.r2_execution_confirmation_fixture import (
    execution_candidate,
    execution_claim,
)


NOW = 2_300_000_000
OWNER = "7" * 64
PRE_HEAD = "8" * 64
REVIEW = "9" * 64
TRANSITION = "a" * 64
PRE_STATE = "b" * 64
POST_STATE = "c" * 64
CLOSURE_MANIFEST = "d" * 64
ATTESTATION_RECEIPT = "e" * 64
OBSERVED_MONOTONIC_NS = 4_000_000_000


def _live_append_observation():
    return {
        "observed_at_epoch": NOW + 1,
        "observed_monotonic_ns": OBSERVED_MONOTONIC_NS,
    }


class R2TransactionJournalV2Tests(unittest.TestCase):
    def setUp(self):
        self.binding = _binding()
        self.genesis = _genesis(self.binding)

    def test_genesis_confirmation_is_bound_to_the_created_journal(self):
        journal = R2TransactionJournalV2.create(
            binding=self.binding,
            genesis=self.genesis,
            **_live_append_observation(),
        )
        claim = journal.genesis.execution_confirmation_claim

        self.assertEqual(claim._attempt_state.phase, "APPENDED")
        restarted = R2TransactionJournalV2.from_framed_bytes(
            journal.to_framed_bytes(), binding=self.binding
        )
        self.assertIsNone(restarted.genesis.execution_confirmation_claim._attempt_state)

    def test_fresh_process_reconstructs_one_authoritative_chain(self):
        journal = self._pending()
        journal = journal.append_effect_observation(
            transition_instance_fingerprint=TRANSITION,
            observed_state_fingerprint=POST_STATE,
            classification=EffectClassificationV2.EFFECT_PRESENT_EXACT,
        )
        journal = journal.append_commit(
            transition_instance_fingerprint=TRANSITION,
            committed_state_fingerprint=POST_STATE,
        )

        restarted = R2TransactionJournalV2.from_framed_bytes(
            journal.to_framed_bytes(), binding=self.binding
        )
        self.assertEqual(restarted, journal)
        self.assertEqual(restarted.record_count, 5)
        self.assertEqual(len(restarted.execution_confirmation_claims), 2)
        self.assertEqual(restarted.current_head_fingerprint, journal.current_head_fingerprint)
        self.assertEqual(
            restarted.next_legal_action,
            "CLAIM_FRESH_EXECUTION_CONFIRMATION_OR_TERMINAL",
        )
        self.assertEqual(restarted.journal_owner_fingerprint, OWNER)

    def test_read_only_inspection_classifies_pre_post_and_ambiguous(self):
        journal = self._pending()
        original_bytes = journal.to_framed_bytes()
        original_head = journal.current_head_fingerprint
        cases = (
            (
                EffectClassificationV2.EFFECT_ABSENT_EXACT,
                PRE_STATE,
                True,
                False,
                "RETRY_WITH_FRESH_EXECUTION_CONFIRMATION",
            ),
            (
                EffectClassificationV2.EFFECT_PRESENT_EXACT,
                POST_STATE,
                False,
                True,
                "COMMIT_WITH_FRESH_EXECUTION_CONFIRMATION",
            ),
            (
                EffectClassificationV2.EFFECT_AMBIGUOUS,
                "d" * 64,
                False,
                False,
                "INCIDENT_STOP",
            ),
        )
        for classification, state, pre, post, next_action in cases:
            first = _observation(journal, state, pre=pre, post=post)
            second = R2StateObservationV2.from_json(first.to_canonical_json())
            receipt = inspect_pending_transition_v2(
                journal=journal,
                first_observation=first,
                second_observation=second,
            )
            with self.subTest(classification=classification.value):
                self.assertIs(receipt.classification, classification)
                self.assertEqual(receipt.next_legal_action, next_action)
                self.assertEqual(receipt.mutation_count, 0)
                self.assertEqual(receipt.journal_append_count, 0)
                self.assertEqual(
                    type(receipt).from_json(
                        receipt.to_canonical_json(),
                        binding=self.binding,
                        journal=journal,
                    ),
                    receipt,
                )
                self.assertEqual(journal.to_framed_bytes(), original_bytes)
                self.assertEqual(journal.current_head_fingerprint, original_head)

    def test_every_journal_cut_point_reconstructs_and_reports_next_action(self):
        journal = R2TransactionJournalV2.create(
            binding=self.binding, genesis=self.genesis,
            **_live_append_observation(),
        )
        states = [(journal, "CLAIM_FRESH_EXECUTION_CONFIRMATION")]
        journal = journal.append_execution_confirmation_claim(
            claim=_claim(self.binding, journal.current_head_fingerprint),
            transition_instance_fingerprint=TRANSITION,
            observed_at_epoch=NOW + 1,
            observed_monotonic_ns=OBSERVED_MONOTONIC_NS,
        )
        states.append((journal, "APPEND_INTENT"))
        journal = journal.append_intent(
            transition_instance_fingerprint=TRANSITION,
            pre_state_fingerprint=PRE_STATE,
            post_state_fingerprint=POST_STATE,
        )
        states.append((journal, "READ_ONLY_INSPECTION"))
        journal = journal.append_effect_observation(
            transition_instance_fingerprint=TRANSITION,
            observed_state_fingerprint=POST_STATE,
            classification=EffectClassificationV2.EFFECT_PRESENT_EXACT,
        )
        states.append((journal, "APPEND_COMMIT"))
        journal = journal.append_commit(
            transition_instance_fingerprint=TRANSITION,
            committed_state_fingerprint=POST_STATE,
        )
        states.append((journal, "CLAIM_FRESH_EXECUTION_CONFIRMATION_OR_TERMINAL"))

        for value, next_action in states:
            restarted = R2TransactionJournalV2.from_framed_bytes(
                value.to_framed_bytes(), binding=self.binding
            )
            with self.subTest(record_count=value.record_count):
                self.assertEqual(restarted.next_legal_action, next_action)
                self.assertEqual(restarted.current_head_fingerprint, value.current_head_fingerprint)

    def test_confirmation_binds_closure_current_head_sequence_action_and_single_use(self):
        journal = R2TransactionJournalV2.create(
            binding=self.binding, genesis=self.genesis,
            **_live_append_observation(),
        )
        head = journal.current_head_fingerprint
        claim = _claim(self.binding, head)

        self.assertEqual(claim.closure_manifest_fingerprint, CLOSURE_MANIFEST)
        self.assertEqual(
            claim.solo_maintainer_attestation_receipt_fingerprint,
            ATTESTATION_RECEIPT,
        )
        self.assertEqual(claim.prior_journal_head_fingerprint, head)
        self.assertEqual(claim.claim_sequence, 2)
        self.assertEqual(claim.action_fingerprint, "1" * 64)
        self.assertEqual(claim.transition_instance_fingerprint, TRANSITION)
        self.assertEqual(claim.single_use, 1)
        self.assertEqual(claim.execution_confirmation_count, 1)
        self.assertEqual(claim.replay_count, 0)

        appended = journal.append_execution_confirmation_claim(
            claim=claim,
            transition_instance_fingerprint=TRANSITION,
            observed_at_epoch=NOW + 1,
            observed_monotonic_ns=OBSERVED_MONOTONIC_NS,
        )
        self.assertEqual(appended.execution_confirmation_claims[-1], claim)
        self.assertEqual(claim._attempt_state.phase, "APPENDED")
        with self.assertRaises(AttributeError):
            claim._attempt_state.phase = "APPENDED"
        with self.assertRaisesRegex(JournalV2Error, "R2_JOURNAL_V2_INVALID"):
            appended.append_execution_confirmation_claim(
                claim=claim,
                transition_instance_fingerprint=TRANSITION,
                observed_at_epoch=NOW + 1,
                observed_monotonic_ns=OBSERVED_MONOTONIC_NS,
            )

    def test_live_append_requires_fresh_wall_and_monotonic_observation(self):
        stale_observations = (
            (NOW + 290, OBSERVED_MONOTONIC_NS),
            (NOW + 1, 301_000_000_000),
            (NOW - 1, OBSERVED_MONOTONIC_NS),
            (NOW + 1, 2_999_999_999),
        )
        for observed_at, observed_monotonic in stale_observations:
            journal = R2TransactionJournalV2.create(
                binding=self.binding,
                genesis=_genesis(self.binding),
                **_live_append_observation(),
            )
            claim = _claim(self.binding, journal.current_head_fingerprint)
            with self.subTest(
                observed_at=observed_at,
                observed_monotonic=observed_monotonic,
            ):
                with self.assertRaisesRegex(
                    JournalV2Error,
                    "R2_JOURNAL_V2_INVALID",
                ):
                    journal.append_execution_confirmation_claim(
                        claim=claim,
                        transition_instance_fingerprint=TRANSITION,
                        observed_at_epoch=observed_at,
                        observed_monotonic_ns=observed_monotonic,
                    )
                with self.assertRaises(JournalV2Error):
                    journal.append_execution_confirmation_claim(
                        claim=claim,
                        transition_instance_fingerprint=TRANSITION,
                        observed_at_epoch=NOW + 1,
                        observed_monotonic_ns=OBSERVED_MONOTONIC_NS,
                    )

    def test_historical_reconstruction_does_not_restore_live_claim_capability(self):
        journal = R2TransactionJournalV2.create(
            binding=self.binding,
            genesis=self.genesis,
            **_live_append_observation(),
        )
        claim = _claim(self.binding, journal.current_head_fingerprint)
        appended = journal.append_execution_confirmation_claim(
            claim=claim,
            transition_instance_fingerprint=TRANSITION,
            observed_at_epoch=NOW + 1,
            observed_monotonic_ns=OBSERVED_MONOTONIC_NS,
        )

        restarted = R2TransactionJournalV2.from_framed_bytes(
            appended.to_framed_bytes(),
            binding=self.binding,
        )
        historical = restarted.execution_confirmation_claims[-1]
        self.assertEqual(historical, claim)
        self.assertIsNone(historical._attempt_state)
        with self.assertRaisesRegex(JournalV2Error, "R2_JOURNAL_V2_INVALID"):
            journal.append_execution_confirmation_claim(
                claim=historical,
                transition_instance_fingerprint=TRANSITION,
                observed_at_epoch=NOW + 1,
                observed_monotonic_ns=OBSERVED_MONOTONIC_NS,
            )

    def test_torn_unknown_duplicate_predecessor_owner_and_replay_fail_closed(self):
        journal = self._pending()
        framed = journal.to_framed_bytes()
        malformed = [framed[:-1], framed + b"0"]
        for field, value in (
            ("record_type", "UNKNOWN"),
            ("record_sequence", 1),
            ("predecessor_head_fingerprint", "e" * 64),
            ("journal_owner_fingerprint", "f" * 64),
        ):
            malformed.append(_tamper_last_frame(framed, field, value))
        for payload in malformed:
            with self.subTest(suffix=payload[-12:]):
                with self.assertRaisesRegex(JournalV2Error, "R2_JOURNAL_V2_INVALID"):
                    R2TransactionJournalV2.from_framed_bytes(
                        payload, binding=self.binding
                    )

        fresh = R2TransactionJournalV2.create(
            binding=self.binding, genesis=_genesis(self.binding),
            **_live_append_observation(),
        )
        replay = _claim(self.binding, fresh.current_head_fingerprint)
        first = fresh.append_execution_confirmation_claim(
            claim=replay,
            transition_instance_fingerprint=TRANSITION,
            observed_at_epoch=NOW + 1,
            observed_monotonic_ns=OBSERVED_MONOTONIC_NS,
        )
        with self.assertRaisesRegex(JournalV2Error, "R2_JOURNAL_V2_INVALID"):
            first.append_execution_confirmation_claim(
                claim=replay,
                transition_instance_fingerprint=TRANSITION,
                observed_at_epoch=NOW + 1,
                observed_monotonic_ns=OBSERVED_MONOTONIC_NS,
            )

    def _pending(self):
        journal = R2TransactionJournalV2.create(
            binding=self.binding, genesis=self.genesis,
            **_live_append_observation(),
        )
        journal = journal.append_execution_confirmation_claim(
            claim=_claim(self.binding, journal.current_head_fingerprint),
            transition_instance_fingerprint=TRANSITION,
            observed_at_epoch=NOW + 1,
            observed_monotonic_ns=OBSERVED_MONOTONIC_NS,
        )
        return journal.append_intent(
            transition_instance_fingerprint=TRANSITION,
            pre_state_fingerprint=PRE_STATE,
            post_state_fingerprint=POST_STATE,
        )


def _observation(journal, state, *, pre, post):
    return R2StateObservationV2.create(
        binding_fingerprint=journal.binding_fingerprint,
        journal_head_fingerprint=journal.current_head_fingerprint,
        transition_instance_fingerprint=TRANSITION,
        observed_state_fingerprint=state,
        identity_fingerprint="1" * 64,
        byte_fingerprint="2" * 64,
        pre_state_match=pre,
        post_state_match=post,
    )


def _tamper_last_frame(payload, field, value):
    frames = _frames(payload)
    body = json.loads(frames[-1].decode("ascii"))
    body[field] = value
    body.pop("head_fingerprint", None)
    canonical = _canonical(body)
    body["head_fingerprint"] = __import__("hashlib").sha256(
        b"r2-journal-record-v2\0" + canonical
    ).hexdigest()
    frames[-1] = _canonical(body)
    return b"".join(f"{len(frame):08x}:".encode("ascii") + frame + b"\n" for frame in frames)


def _frames(payload):
    values = []
    cursor = 0
    while cursor < len(payload):
        size = int(payload[cursor:cursor + 8], 16)
        start = cursor + 9
        values.append(payload[start:start + size])
        cursor = start + size + 1
    return values


def _genesis(binding):
    claim = _confirmed_claim(
        binding=binding,
        command=ProductionCommandV2.EVIDENCE_PUBLICATION,
        action_fingerprint=production_action_fingerprint_v2(
            binding,
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            subject_fingerprint=REVIEW,
        ),
        head=PRE_HEAD,
        transition=REVIEW,
        remaining_reverse_plan_fingerprint="0" * 64,
        claim_sequence=1,
        confirmed_at_epoch=NOW - 80,
    )
    return R2JournalGenesisV2.create(
        binding=binding,
        reviewed_evidence_fingerprint=REVIEW,
        evidence_identity_fingerprint="5" * 64,
        package_fingerprint="6" * 64,
        manifest_fingerprint="d" * 64,
        journal_owner_fingerprint=OWNER,
        genesis_nonce="e" * 64,
        pre_genesis_head_fingerprint=PRE_HEAD,
        execution_confirmation_claim=claim,
    )


def _claim(binding, head):
    return _confirmed_claim(
        binding=binding,
        command=ProductionCommandV2.EXECUTE,
        action_fingerprint="1" * 64,
        head=head,
        transition=TRANSITION,
        remaining_reverse_plan_fingerprint="0" * 64,
        claim_sequence=2,
        confirmed_at_epoch=NOW,
    )


def _confirmed_claim(
    *,
    binding,
    command,
    action_fingerprint,
    head,
    transition,
    remaining_reverse_plan_fingerprint,
    claim_sequence,
    confirmed_at_epoch,
):
    candidate = execution_candidate(
        binding,
        command=command,
        action_fingerprint=action_fingerprint,
        closure_manifest=CLOSURE_MANIFEST,
        solo_attestation=ATTESTATION_RECEIPT,
        journal_owner=OWNER,
        prior_head=head,
        transition=transition,
        remaining_reverse_plan=remaining_reverse_plan_fingerprint,
        claim_sequence=claim_sequence,
        prepared_at_epoch=confirmed_at_epoch - 10,
        confirmed_at_epoch=confirmed_at_epoch,
    )
    claim = execution_claim(
        binding,
        candidate=candidate,
        confirmed_at_epoch=confirmed_at_epoch,
    )
    if type(claim) is not ExecutionConfirmationClaimV1:
        raise AssertionError("expected exact execution confirmation claim")
    return claim


def _binding():
    final = FinalMasterBindingV1.create(
        final_commit_oid="1" * 40,
        final_tree_oid="2" * 40,
        source_package_fingerprint="3" * 64,
        runbook_fingerprint="4" * 64,
        workflow_fingerprint="5" * 64,
    )
    return ApprovedCutoverBindingV3.create(
        final_master_binding=final,
        operation_fingerprint="6" * 64,
        operator_role_fingerprints={
            role: f"{index + 10:064x}" for index, role in enumerate(OperatorRoleV2)
        },
        production_role_fingerprints={
            role: f"{index + 30:064x}" for index, role in enumerate(ProductionRoleV2)
        },
    )


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


if __name__ == "__main__":
    unittest.main()
