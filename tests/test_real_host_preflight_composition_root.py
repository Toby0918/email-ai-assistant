"""Fixed read-only RealHostPreflightComposition behavior."""

from __future__ import annotations

import unittest

from backend.cutover_composition_contracts import (
    CompositionContractError,
    CompositionStage,
    ProjectContainerReceiptChainV1,
    ReceiptChainState,
)
from backend.real_host_preflight_composition import (
    RealHostPreflightComposition,
    RealHostPreflightRolesV1,
)
from tests.cutover_composition_binders import (
    TestOwnedCompositionScopeV1,
    bind_test_preflight,
)
from tests.cutover_composition_fixtures import (
    OBSERVED_AT,
    stage_receipt,
    synthetic_context,
)


class RealHostPreflightCompositionRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile, self.sequence, self.binding = synthetic_context()
        self.scope = TestOwnedCompositionScopeV1.create()
        self.addCleanup(self.scope.close)
        self.calls: list[CompositionStage] = []
        self.roles = RealHostPreflightRolesV1(
            binding_fingerprint=self.binding.binding_fingerprint,
            current_topology=self._role(CompositionStage.CURRENT_TOPOLOGY, 1),
            host_baseline=self._role(CompositionStage.HOST_BASELINE, 2),
            evidence_review=self._role(CompositionStage.EVIDENCE_REVIEW, 3),
            evidence_verification=self._role(
                CompositionStage.EVIDENCE_VERIFICATION, 5
            ),
            final_audit_readiness=self._role(
                CompositionStage.FINAL_AUDIT_READINESS, 6
            ),
            recovery_inspection=self._role(
                CompositionStage.RECOVERY_INSPECTION,
                18,
                journal_bound=True,
            ),
        )

    def test_fixed_read_only_sequence_reaches_preflight_ready(self) -> None:
        composition = self._composition()

        topology = composition.run_current_topology()
        baseline = composition.collect_host_baseline()
        review = composition.review_evidence()
        publication = stage_receipt(
            self.binding,
            CompositionStage.EVIDENCE_PUBLICATION,
            review,
            4,
        )
        verified = composition.verify_evidence(publication)
        ready = composition.prove_final_audit_readiness()
        chain = composition.receipt_chain()

        self.assertIs(chain.state, ReceiptChainState.PREFLIGHT_READY)
        self.assertEqual(
            self.calls,
            [
                CompositionStage.CURRENT_TOPOLOGY,
                CompositionStage.HOST_BASELINE,
                CompositionStage.EVIDENCE_REVIEW,
                CompositionStage.EVIDENCE_VERIFICATION,
                CompositionStage.FINAL_AUDIT_READINESS,
            ],
        )
        self.assertEqual(
            tuple(
                item.stage
                for item in (topology, baseline, review, publication, verified, ready)
            ),
            tuple(item.stage for item in chain.receipts),
        )

    def test_recovery_inspection_is_separate_and_exactly_bound(self) -> None:
        composition = self._composition()
        prior = stage_receipt(
            self.binding,
            CompositionStage.ACTIVATION,
            None,
            17,
            journal_bound=True,
        )

        inspected = composition.inspect_recovery(prior)

        self.assertIs(inspected.stage, CompositionStage.RECOVERY_INSPECTION)
        self.assertEqual(
            inspected.prior_receipt_fingerprint,
            prior.receipt_fingerprint,
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "^REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED$",
        ):
            composition.inspect_recovery(prior)

        _profile, _sequence, alternate = synthetic_context(
            operation_fingerprint="e" * 64
        )
        unrelated = stage_receipt(
            alternate,
            CompositionStage.ACTIVATION,
            None,
            17,
            journal_bound=True,
        )
        separate = self._composition()
        with self.assertRaisesRegex(
            CompositionContractError,
            "^REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED$",
        ):
            separate.inspect_recovery(unrelated)

    def test_wrong_order_role_drift_and_expiry_fail_closed(self) -> None:
        composition = self._composition()
        with self.assertRaisesRegex(
            CompositionContractError,
            "^REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED$",
        ):
            composition.collect_host_baseline()

        bad_roles = RealHostPreflightRolesV1(
            binding_fingerprint=self.binding.binding_fingerprint,
            current_topology=self._role(CompositionStage.HOST_BASELINE, 2),
            host_baseline=self._role(CompositionStage.HOST_BASELINE, 2),
            evidence_review=self._role(CompositionStage.EVIDENCE_REVIEW, 3),
            evidence_verification=self._role(
                CompositionStage.EVIDENCE_VERIFICATION, 5
            ),
            final_audit_readiness=self._role(
                CompositionStage.FINAL_AUDIT_READINESS, 6
            ),
            recovery_inspection=self._role(
                CompositionStage.RECOVERY_INSPECTION,
                18,
                journal_bound=True,
            ),
        )
        drifted = self._composition(roles=bad_roles)
        with self.assertRaisesRegex(
            CompositionContractError,
            "^REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED$",
        ):
            drifted.run_current_topology()

        _profile, expired, binding = synthetic_context(
            expires_at_epoch=OBSERVED_AT + 1
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "^REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED$",
        ):
            bind_test_preflight(
                scope=self.scope,
                binding=binding,
                authorization_sequence=expired,
                roles=self.roles,
                observed_at_epoch=OBSERVED_AT + 1,
            )

    def test_public_constructor_and_non_nominal_roles_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            RealHostPreflightComposition()
        with self.assertRaisesRegex(
            CompositionContractError,
            "^REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED$",
        ):
            bind_test_preflight(
                scope=self.scope,
                binding=self.binding,
                authorization_sequence=self.sequence,
                roles={"current_topology": self._role(
                    CompositionStage.CURRENT_TOPOLOGY, 1
                )},
                observed_at_epoch=OBSERVED_AT,
            )

    def test_bound_roles_cannot_outlive_test_owned_scope(self) -> None:
        composition = self._composition()
        self.scope.close()

        with self.assertRaisesRegex(
            CompositionContractError,
            "^REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED$",
        ):
            composition.run_current_topology()
        self.assertEqual(self.calls, [])

    def _composition(self, *, roles=None):
        return bind_test_preflight(
            scope=self.scope,
            binding=self.binding,
            authorization_sequence=self.sequence,
            roles=roles or self.roles,
            observed_at_epoch=OBSERVED_AT,
        )

    def _role(self, stage, index, *, journal_bound=False):
        def call(prior):
            self.calls.append(stage)
            return stage_receipt(
                self.binding,
                stage,
                prior,
                index,
                journal_bound=journal_bound,
            )

        return call


if __name__ == "__main__":
    unittest.main()
