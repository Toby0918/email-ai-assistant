"""Public contract tests for Issue #70 R2 vocabulary expansion."""

from __future__ import annotations

import unittest

from backend.cutover_composition_contracts import (
    ApprovedCutoverBindingV1,
    AuthorizationDomain,
    CompositionContractError,
    FinalCutoverOutcome,
    JournalFactKind,
    ManagedPublicationUnit,
    PendingEffectState,
    R2CutoverReceiptV1,
    R2JournalBoundary,
    TwoStartLifecycleState,
    UNBOUND_FINGERPRINT,
    authorization_domain_for_phase,
    managed_publication_boundaries,
)
from backend.cutover_composition_contracts.authorization_sequence import (
    AuthorizationSequenceV1,
)
from tests.cutover_composition_fixtures import synthetic_context
from tests.cutover_contract_fixtures import opaque_fingerprint


class R2CutoverContractVocabularyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile, self.sequence, _legacy_binding = synthetic_context()
        self.binding = ApprovedCutoverBindingV1.create(
            profile=self.profile,
            operation_fingerprint=opaque_fingerprint(7001),
            authorization_sequence=_sequence_for_operation(
                self.profile,
                opaque_fingerprint(7001),
            ),
        )

    def test_approved_binding_is_derived_from_reviewed_profile_and_sequence(self) -> None:
        profile_mapping = self.profile.to_mapping()
        binding = self.binding.to_mapping()

        self.assertEqual(binding["binding_type"], "ApprovedCutoverBindingV1")
        self.assertEqual(
            binding["legacy_source_anchor_fingerprint"],
            profile_mapping["role_selections"]["legacy_source"],
        )
        self.assertEqual(
            binding["managed_main_root_fingerprint"],
            profile_mapping["role_selections"]["repository_root"],
        )
        self.assertEqual(
            binding["expected_inherited_dacl_projection_fingerprint"],
            profile_mapping["acl_policy"]["policy_fingerprint"],
        )
        self.assertNotIn("path", " ".join(binding).lower())
        self.assertNotIn("override", " ".join(binding).lower())
        self.assertNotIn("fallback", " ".join(binding).lower())

    def test_binding_canonical_json_round_trip_rejects_unknown_and_duplicate_fields(self) -> None:
        payload = self.binding.to_canonical_json()
        round_trip = ApprovedCutoverBindingV1.from_json(
            payload,
            profile=self.profile,
            authorization_sequence=_sequence_for_operation(
                self.profile,
                opaque_fingerprint(7001),
            ),
        )
        self.assertEqual(round_trip, self.binding)

        unknown = payload[:-1] + b',"path":"synthetic"}'
        duplicate = (
            payload[:-1]
            + b',"binding_type":"ApprovedCutoverBindingV1"}'
        )
        for hostile in (unknown, duplicate):
            with self.subTest(payload=hostile):
                with self.assertRaisesRegex(
                    CompositionContractError,
                    "R2_APPROVED_CUTOVER_BINDING_INVALID",
                ):
                    ApprovedCutoverBindingV1.from_json(
                        hostile,
                        profile=self.profile,
                        authorization_sequence=_sequence_for_operation(
                            self.profile,
                            opaque_fingerprint(7001),
                        ),
                    )

    def test_four_authorization_domains_are_nominal_and_phase_closed(self) -> None:
        self.assertEqual(
            {item.value for item in AuthorizationDomain},
            {"preflight", "evidence", "execution", "recovery"},
        )
        expected = {
            "current_topology_preflight": AuthorizationDomain.PREFLIGHT,
            "independent_stopped_layout_audit": AuthorizationDomain.PREFLIGHT,
            "independent_final_running_audit": AuthorizationDomain.PREFLIGHT,
            "evidence_publication": AuthorizationDomain.EVIDENCE,
            "execute": AuthorizationDomain.EXECUTION,
            "resume": AuthorizationDomain.EXECUTION,
            "rollback": AuthorizationDomain.RECOVERY,
            "legacy_recovery": AuthorizationDomain.RECOVERY,
        }
        for phase, domain in expected.items():
            with self.subTest(phase=phase):
                self.assertIs(authorization_domain_for_phase(phase), domain)
        self.assertIsNone(authorization_domain_for_phase("receipt"))
        self.assertIsNone(authorization_domain_for_phase(1))

    def test_vocabulary_names_every_independent_managed_publication_boundary(self) -> None:
        expected = {
            ManagedPublicationUnit.RUNTIME: (
                R2JournalBoundary.RUNTIME_PREPARE,
                R2JournalBoundary.RUNTIME_PUBLISH,
            ),
            ManagedPublicationUnit.DATABASE: (
                R2JournalBoundary.DATABASE_PREPARE,
                R2JournalBoundary.DATABASE_PUBLISH,
            ),
            ManagedPublicationUnit.CRX: (
                R2JournalBoundary.CRX_PREPARE,
                R2JournalBoundary.CRX_PUBLISH,
            ),
            ManagedPublicationUnit.CONFIG: (
                R2JournalBoundary.CONFIG_PREPARE,
                R2JournalBoundary.CONFIG_PUBLISH,
            ),
        }
        self.assertEqual(managed_publication_boundaries(), expected)
        self.assertNotIn(
            "managed_publication",
            {item.value for item in R2JournalBoundary},
        )

    def test_vocabulary_covers_quiescence_audits_two_starts_and_recovery(self) -> None:
        boundaries = {item.value for item in R2JournalBoundary}
        self.assertTrue(
            {
                "legacy_service_quiescence_intent",
                "legacy_service_quiescence_effect",
                "legacy_service_quiescence_committed",
                "stopped_layout_audit",
                "final_running_audit",
                "validation_start_a",
                "validation_stop_a",
                "final_start_b",
                "pending_effect_classification",
                "failed_container_preservation",
                "legacy_flat_layout_restored",
                "cutover_success",
            }.issubset(boundaries)
        )
        self.assertEqual(
            {item.value for item in PendingEffectState},
            {
                "EFFECT_ABSENT_EXACT",
                "EFFECT_PRESENT_EXACT",
                "EFFECT_AMBIGUOUS",
            },
        )
        self.assertEqual(
            {item.value for item in FinalCutoverOutcome},
            {
                "CUTOVER_SUCCESS",
                "LEGACY_FLAT_LAYOUT_RESTORED",
                "INCIDENT_STOP",
            },
        )
        self.assertEqual(
            tuple(item.value for item in TwoStartLifecycleState),
            (
                "LEGACY_STOPPED",
                "VALIDATION_START_A_RUNNING",
                "VALIDATION_START_A_STOPPED",
                "STOPPED_LAYOUT_AUDITED",
                "FINAL_START_B_RUNNING",
                "FINAL_RUNNING_AUDITED",
                "CUTOVER_SUCCESS",
            ),
        )

    def test_receipt_is_canonical_content_free_evidence_and_never_authority(self) -> None:
        receipt = _receipt(
            self.binding,
            boundary=R2JournalBoundary.RUNTIME_PREPARE,
            fact_kind=JournalFactKind.COMMITTED,
        )
        payload = receipt.to_canonical_json()
        self.assertEqual(
            R2CutoverReceiptV1.from_json(payload, binding=self.binding),
            receipt,
        )
        public = receipt.to_mapping()
        self.assertEqual(
            set(public),
            {
                "receipt_type",
                "binding_fingerprint",
                "boundary",
                "fact_kind",
                "prior_receipt_fingerprint",
                "observation_fingerprint",
                "journal_owner_fingerprint",
                "prior_journal_head_fingerprint",
                "journal_head_fingerprint",
                "pending_effect_state",
                "final_outcome",
                "accepted",
                "rejected",
                "worktrees",
                "provider_attempts",
                "receipt_fingerprint",
            },
        )
        self.assertFalse(isinstance(receipt, AuthorizationSequenceV1))
        self.assertNotIn("synthetic", repr(receipt).lower())
        self.assertNotIn("path", repr(receipt).lower())

    def test_receipt_rejects_unknown_constructor_fields_and_duplicate_json(self) -> None:
        with self.assertRaisesRegex(
            CompositionContractError,
            "R2_CUTOVER_RECEIPT_INVALID",
        ):
            _receipt(
                self.binding,
                boundary=R2JournalBoundary.RUNTIME_PREPARE,
                fact_kind=JournalFactKind.COMMITTED,
                path=opaque_fingerprint(7099),
            )

        receipt = _receipt(
            self.binding,
            boundary=R2JournalBoundary.RUNTIME_PREPARE,
            fact_kind=JournalFactKind.COMMITTED,
        )
        duplicate = (
            receipt.to_canonical_json()[:-1]
            + b',"receipt_type":"R2CutoverReceiptV1"}'
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "R2_CUTOVER_RECEIPT_INVALID",
        ):
            R2CutoverReceiptV1.from_json(duplicate, binding=self.binding)

    def test_pending_classification_requires_exact_tri_state_only(self) -> None:
        for state in PendingEffectState:
            receipt = _receipt(
                self.binding,
                boundary=R2JournalBoundary.PENDING_EFFECT_CLASSIFICATION,
                fact_kind=JournalFactKind.PENDING_CLASSIFIED,
                pending_effect_state=state,
            )
            self.assertIs(receipt.pending_effect_state, state)
        with self.assertRaisesRegex(
            CompositionContractError,
            "R2_CUTOVER_RECEIPT_INVALID",
        ):
            _receipt(
                self.binding,
                boundary=R2JournalBoundary.PENDING_EFFECT_CLASSIFICATION,
                fact_kind=JournalFactKind.PENDING_CLASSIFIED,
            )

    def test_final_outcome_is_bound_to_its_exact_terminal_boundary(self) -> None:
        cases = (
            (
                R2JournalBoundary.CUTOVER_SUCCESS,
                FinalCutoverOutcome.CUTOVER_SUCCESS,
            ),
            (
                R2JournalBoundary.LEGACY_FLAT_LAYOUT_RESTORED,
                FinalCutoverOutcome.LEGACY_FLAT_LAYOUT_RESTORED,
            ),
            (
                R2JournalBoundary.INCIDENT_STOP,
                FinalCutoverOutcome.INCIDENT_STOP,
            ),
        )
        for boundary, outcome in cases:
            with self.subTest(boundary=boundary):
                receipt = _receipt(
                    self.binding,
                    boundary=boundary,
                    fact_kind=JournalFactKind.FINAL_OUTCOME,
                    final_outcome=outcome,
                )
                self.assertIs(receipt.final_outcome, outcome)

        with self.assertRaisesRegex(
            CompositionContractError,
            "R2_CUTOVER_RECEIPT_INVALID",
        ):
            _receipt(
                self.binding,
                boundary=R2JournalBoundary.RUNTIME_PUBLISH,
                fact_kind=JournalFactKind.FINAL_OUTCOME,
                final_outcome=FinalCutoverOutcome.CUTOVER_SUCCESS,
            )


def _sequence_for_operation(profile, operation_fingerprint):
    from backend.cutover_composition_contracts.authorization_sequence import (
        AUTHORIZATION_PHASES,
        _create_test_authorization_sequence,
    )
    from backend.cutover_contracts import TestSandboxAuthorizationV1

    observed_at = 1_900_000_000
    authorizations = tuple(
        TestSandboxAuthorizationV1.create(
            profile_fingerprint=profile.profile_fingerprint,
            operation_fingerprint=operation_fingerprint,
            phase=phase,
            expires_at_epoch=observed_at + 300,
        )
        for _kind, _operation, phase in AUTHORIZATION_PHASES
    )
    return _create_test_authorization_sequence(
        profile=profile,
        operation_fingerprint=operation_fingerprint,
        authorizations=authorizations,
        observed_at_epoch=observed_at,
    )


def _receipt(
    binding,
    *,
    boundary,
    fact_kind,
    pending_effect_state=None,
    final_outcome=None,
    **extra,
):
    return R2CutoverReceiptV1.create(
        binding=binding,
        boundary=boundary,
        fact_kind=fact_kind,
        prior_receipt_fingerprint=UNBOUND_FINGERPRINT,
        observation_fingerprint=opaque_fingerprint(7020),
        journal_owner_fingerprint=opaque_fingerprint(7021),
        prior_journal_head_fingerprint=UNBOUND_FINGERPRINT,
        journal_head_fingerprint=opaque_fingerprint(7022),
        pending_effect_state=pending_effect_state,
        final_outcome=final_outcome,
        accepted=1,
        rejected=0,
        worktrees=(
            11
            if boundary
            in {
                R2JournalBoundary.WORKTREE_RECONSTRUCTION,
                R2JournalBoundary.WORKTREE_ROLLBACK,
            }
            else 0
        ),
        provider_attempts=0,
        **extra,
    )


if __name__ == "__main__":
    unittest.main()
