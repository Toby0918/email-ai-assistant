"""Journal-driven execute, resume, and rollback Issue #59 root."""

from __future__ import annotations

import concurrent.futures
import dataclasses
import unittest

from backend.cutover_composition_contracts import (
    CompositionContractError,
    CompositionStage,
    ProjectContainerReceiptChainV1,
    ReceiptChainState,
)
from backend.cutover_transaction_composition import (
    CutoverTransactionComposition,
    CutoverTransactionRolesV1,
    JournalOwnerV1,
)
from tests.cutover_composition_binders import (
    TestOwnedCompositionScopeV1,
    bind_test_transaction,
)
from tests.cutover_composition_fixtures import (
    JOURNAL_OWNER,
    OBSERVED_AT,
    stage_receipt,
    synthetic_context,
)


PREFLIGHT_STAGES = (
    CompositionStage.CURRENT_TOPOLOGY,
    CompositionStage.HOST_BASELINE,
    CompositionStage.EVIDENCE_REVIEW,
    CompositionStage.EVIDENCE_PUBLICATION,
    CompositionStage.EVIDENCE_VERIFICATION,
    CompositionStage.FINAL_AUDIT_READINESS,
)
EXECUTION_STAGES = (
    CompositionStage.ACL_BASELINE,
    CompositionStage.PRE_MUTATION_GATE,
    CompositionStage.ACL_PUBLICATION,
    CompositionStage.REPOSITORY_TRANSACTION,
    CompositionStage.RUNTIME_PUBLICATION,
    CompositionStage.DATABASE_PUBLICATION,
    CompositionStage.ARTIFACT_PUBLICATION,
    CompositionStage.CONFIG_PUBLICATION,
    CompositionStage.ACTIVATION,
    CompositionStage.FINAL_AUDIT,
)
RECOVERY_STAGES = (
    CompositionStage.RECOVERY_INSPECTION,
    CompositionStage.FAILED_CONTAINER_PRESERVATION,
    CompositionStage.ROLLBACK_RESTORATION,
    CompositionStage.LEGACY_HEALTH,
)


class CutoverTransactionCompositionRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile, self.sequence, self.binding = synthetic_context()
        self.scope = TestOwnedCompositionScopeV1.create()
        self.addCleanup(self.scope.close)
        self.calls: list[CompositionStage | str] = []
        self.now = OBSERVED_AT
        self.claimed_gates: set[str] = set()
        self.owner = JournalOwnerV1(
            owner_fingerprint=JOURNAL_OWNER,
            verify_head=self._verify_head,
            claim_gate=self._claim_gate,
            now_epoch=lambda: self.now,
        )
        self.roles = self._roles()

    def test_execute_advances_exact_order_to_success(self) -> None:
        composition = self._composition(_chain(self.binding, PREFLIGHT_STAGES))

        completed = composition.execute()

        self.assertIs(completed.state, ReceiptChainState.CUTOVER_SUCCEEDED)
        self.assertEqual(
            [item for item in self.calls if item != "journal_head"],
            [*EXECUTION_STAGES, CompositionStage.CUTOVER_SUCCESS],
        )
        self.assertEqual(self.calls.count("journal_head"), 9)
        self.assertEqual(completed.receipts[-1].worktrees, 0)
        self.assertEqual(
            completed.journal_owner_fingerprint,
            JOURNAL_OWNER,
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.execute()

    def test_rollback_preserves_failed_state_before_exact_restore(self) -> None:
        initial = _chain(
            self.binding,
            (*PREFLIGHT_STAGES, *EXECUTION_STAGES[:-1]),
        )
        composition = self._composition(initial)

        recovered = composition.rollback()

        self.assertIs(recovered.state, ReceiptChainState.LEGACY_RECOVERED)
        self.assertEqual(
            [item for item in self.calls if item != "journal_head"],
            list(RECOVERY_STAGES),
        )
        self.assertEqual(recovered.receipts[-2].worktrees, 11)
        self.assertEqual(recovered.receipts[-1].worktrees, 11)
        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.rollback()

    def test_resume_accepts_only_exact_prefix_journal_continuation(self) -> None:
        initial_stages = (
            *PREFLIGHT_STAGES,
            *EXECUTION_STAGES[:4],
        )
        initial = _chain(self.binding, initial_stages)
        expected = _success_chain(self.binding)
        roles = self._roles(resume_result=expected)
        composition = self._composition(initial, roles=roles)

        resumed = composition.resume()

        self.assertIs(resumed.state, ReceiptChainState.CUTOVER_SUCCEEDED)
        self.assertEqual(self.calls[:2], ["journal_head", "resume_committed"])
        self.assertEqual(self.calls.count("journal_head"), 8)

        unrelated = _success_chain(_alternate_binding())
        rejected = self._composition(
            initial,
            roles=self._roles(resume_result=unrelated),
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            rejected.resume()

        self.calls.clear()
        wrong_owner = JournalOwnerV1(
            owner_fingerprint="f" * 64,
            verify_head=self._verify_head,
            claim_gate=self._claim_gate,
            now_epoch=lambda: self.now,
        )
        rejected = self._composition(initial, owner=wrong_owner)
        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            rejected.resume()
        self.assertEqual(self.calls, [])

    def test_stale_gate_owner_and_stage_drift_stop_before_mutation(self) -> None:
        preflight = _chain(self.binding, PREFLIGHT_STAGES)
        stale = self._roles(gate_expiry=OBSERVED_AT)
        composition = self._composition(preflight, roles=stale)
        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.execute()
        self.assertEqual(
            self.calls,
            [
                CompositionStage.ACL_BASELINE,
                CompositionStage.PRE_MUTATION_GATE,
            ],
        )

        self.calls.clear()
        wrong_owner = JournalOwnerV1(
            owner_fingerprint="f" * 64,
            verify_head=self._verify_head,
            claim_gate=self._claim_gate,
            now_epoch=lambda: self.now,
        )
        composition = self._composition(preflight, owner=wrong_owner)
        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.execute()
        self.assertNotIn(
            CompositionStage.REPOSITORY_TRANSACTION,
            self.calls,
        )

        self.calls.clear()
        self.claimed_gates.clear()
        drifted = self._roles(
            activation_stage=CompositionStage.FINAL_AUDIT
        )
        composition = self._composition(preflight, roles=drifted)
        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.execute()
        self.assertEqual(self.calls.count(CompositionStage.FINAL_AUDIT), 1)
        self.assertEqual(self.calls[-1], CompositionStage.FINAL_AUDIT)

    def test_concurrent_execute_has_one_owner_and_no_replay(self) -> None:
        composition = self._composition(_chain(self.binding, PREFLIGHT_STAGES))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(lambda _index: _attempt_execute(composition), range(2))
            )
        self.assertEqual(sorted(results), ["blocked", "success"])
        self.assertEqual(
            self.calls.count(CompositionStage.REPOSITORY_TRANSACTION),
            1,
        )

    def test_gate_is_single_use_across_compositions_with_one_owner(self) -> None:
        initial = _chain(self.binding, PREFLIGHT_STAGES)
        first = self._composition(initial)
        second = self._composition(initial)

        self.assertIs(
            first.execute().state,
            ReceiptChainState.CUTOVER_SUCCEEDED,
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            second.execute()
        self.assertEqual(
            self.calls.count(CompositionStage.REPOSITORY_TRANSACTION),
            1,
        )

    def test_authorization_expiry_is_rechecked_before_each_boundary(
        self,
    ) -> None:
        roles = self._roles()
        acl_baseline = roles.acl_baseline

        def expire_after_baseline(prior):
            receipt = acl_baseline(prior)
            self.now = self.sequence.expires_at_epoch
            return receipt

        roles = dataclasses.replace(
            roles,
            acl_baseline=expire_after_baseline,
        )
        composition = self._composition(
            _chain(self.binding, PREFLIGHT_STAGES),
            roles=roles,
        )

        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.execute()
        self.assertEqual(self.calls, [CompositionStage.ACL_BASELINE])

    def test_authorization_expiry_after_final_audit_blocks_success(self) -> None:
        roles = self._roles()
        final_audit = roles.final_audit

        def expire_after_final_audit(prior):
            receipt = final_audit(prior)
            self.now = self.sequence.expires_at_epoch
            return receipt

        composition = self._composition(
            _chain(self.binding, PREFLIGHT_STAGES),
            roles=dataclasses.replace(
                roles,
                final_audit=expire_after_final_audit,
            ),
        )

        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.execute()
        self.assertNotIn(CompositionStage.CUTOVER_SUCCESS, self.calls)

    def test_authorization_expiry_after_resume_result_is_rejected(self) -> None:
        initial = _chain(
            self.binding,
            (*PREFLIGHT_STAGES, *EXECUTION_STAGES[:4]),
        )
        expected = _success_chain(self.binding)
        roles = self._roles(resume_result=expected)
        resume_committed = roles.resume_committed

        def expire_with_result(chain):
            resumed = resume_committed(chain)
            self.now = self.sequence.expires_at_epoch
            return resumed

        composition = self._composition(
            initial,
            roles=dataclasses.replace(
                roles,
                resume_committed=expire_with_result,
            ),
        )

        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.resume()
        self.assertEqual(
            self.calls,
            ["journal_head", "resume_committed"],
        )

    def test_bound_roles_and_owner_cannot_outlive_test_owned_scope(self) -> None:
        composition = self._composition(
            _chain(self.binding, PREFLIGHT_STAGES)
        )
        self.scope.close()

        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.execute()
        self.assertEqual(self.calls, [])

    def test_rollback_verifies_existing_journal_before_any_role(self) -> None:
        owner = JournalOwnerV1(
            owner_fingerprint=JOURNAL_OWNER,
            verify_head=lambda _receipt: "f" * 64,
            claim_gate=self._claim_gate,
            now_epoch=lambda: self.now,
        )
        composition = self._composition(
            _chain(
                self.binding,
                (*PREFLIGHT_STAGES, *EXECUTION_STAGES[:-1]),
            ),
            owner=owner,
        )

        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            composition.rollback()
        self.assertEqual(self.calls, [])

    def test_constructor_and_non_nominal_roles_or_owner_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CutoverTransactionComposition()
        initial = _chain(self.binding, PREFLIGHT_STAGES)
        for roles, owner in (
            ({}, self.owner),
            (self.roles, {"owner_fingerprint": JOURNAL_OWNER}),
            (
                self.roles,
                JournalOwnerV1(
                    owner_fingerprint="g" * 64,
                    verify_head=self._verify_head,
                    claim_gate=self._claim_gate,
                    now_epoch=lambda: self.now,
                ),
            ),
        ):
            with self.subTest(roles=type(roles).__name__), self.assertRaisesRegex(
                CompositionContractError,
                "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
            ):
                self._composition(initial, roles=roles, owner=owner)

    def _composition(self, initial, *, roles=None, owner=None):
        return bind_test_transaction(
            scope=self.scope,
            binding=self.binding,
            authorization_sequence=self.sequence,
            roles=self.roles if roles is None else roles,
            journal_owner=self.owner if owner is None else owner,
            initial_chain=initial,
            observed_at_epoch=OBSERVED_AT,
        )

    def _roles(
        self,
        *,
        gate_expiry=OBSERVED_AT + 60,
        activation_stage=CompositionStage.ACTIVATION,
        resume_result=None,
    ):
        role_by_stage = {
            stage: self._role(
                activation_stage if stage is CompositionStage.ACTIVATION else stage,
                10 + index,
                valid_until_epoch=(
                    gate_expiry
                    if stage is CompositionStage.PRE_MUTATION_GATE
                    else 0
                ),
            )
            for index, stage in enumerate(
                (*EXECUTION_STAGES, *RECOVERY_STAGES)
            )
        }

        def resume_committed(_chain_value):
            self.calls.append("resume_committed")
            return resume_result

        return CutoverTransactionRolesV1(
            binding_fingerprint=self.binding.binding_fingerprint,
            acl_baseline=role_by_stage[CompositionStage.ACL_BASELINE],
            pre_mutation_gate=role_by_stage[
                CompositionStage.PRE_MUTATION_GATE
            ],
            acl_publication=role_by_stage[
                CompositionStage.ACL_PUBLICATION
            ],
            repository_transaction=role_by_stage[
                CompositionStage.REPOSITORY_TRANSACTION
            ],
            runtime_publication=role_by_stage[
                CompositionStage.RUNTIME_PUBLICATION
            ],
            database_publication=role_by_stage[
                CompositionStage.DATABASE_PUBLICATION
            ],
            artifact_publication=role_by_stage[
                CompositionStage.ARTIFACT_PUBLICATION
            ],
            config_publication=role_by_stage[
                CompositionStage.CONFIG_PUBLICATION
            ],
            activation=role_by_stage[CompositionStage.ACTIVATION],
            final_audit=role_by_stage[CompositionStage.FINAL_AUDIT],
            cutover_success=self._role(
                CompositionStage.CUTOVER_SUCCESS,
                20,
            ),
            recovery_inspection=role_by_stage[
                CompositionStage.RECOVERY_INSPECTION
            ],
            failed_container_preservation=role_by_stage[
                CompositionStage.FAILED_CONTAINER_PRESERVATION
            ],
            rollback_restoration=role_by_stage[
                CompositionStage.ROLLBACK_RESTORATION
            ],
            legacy_health=role_by_stage[CompositionStage.LEGACY_HEALTH],
            resume_committed=resume_committed,
        )

    def _role(self, stage, index, *, valid_until_epoch=0):
        def call(prior):
            self.calls.append(stage)
            return stage_receipt(
                self.binding,
                stage,
                prior,
                index,
                journal_bound=stage
                not in {
                    CompositionStage.ACL_BASELINE,
                    CompositionStage.PRE_MUTATION_GATE,
                },
                valid_until_epoch=valid_until_epoch,
            )

        return call

    def _verify_head(self, receipt):
        self.calls.append("journal_head")
        return receipt.journal_head_fingerprint

    def _claim_gate(self, receipt):
        fingerprint = receipt.receipt_fingerprint
        if fingerprint in self.claimed_gates:
            raise ValueError
        self.claimed_gates.add(fingerprint)
        return fingerprint


def _chain(binding, stages):
    receipts = []
    prior = None
    for index, stage in enumerate(stages):
        journal_bound = stage in {
            *EXECUTION_STAGES[2:],
            *RECOVERY_STAGES,
            CompositionStage.CUTOVER_SUCCESS,
        }
        receipt = stage_receipt(
            binding,
            stage,
            prior,
            index,
            journal_bound=journal_bound,
            valid_until_epoch=(
                OBSERVED_AT + 60
                if stage is CompositionStage.PRE_MUTATION_GATE
                else 0
            ),
        )
        receipts.append(receipt)
        prior = receipt
    return ProjectContainerReceiptChainV1.create(
        receipts=tuple(receipts),
        observed_at_epoch=OBSERVED_AT,
    )


def _success_chain(binding):
    stages = (
        *PREFLIGHT_STAGES,
        *EXECUTION_STAGES,
        CompositionStage.CUTOVER_SUCCESS,
    )
    return _chain(binding, stages)


def _alternate_binding():
    _profile, _sequence, binding = synthetic_context(
        operation_fingerprint="e" * 64
    )
    return binding


def _attempt_execute(composition):
    try:
        composition.execute()
    except CompositionContractError:
        return "blocked"
    return "success"


if __name__ == "__main__":
    unittest.main()
