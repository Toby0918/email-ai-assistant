"""TDD tests for final-audit readiness and the locked operator seam."""

from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from backend.container_audit import (
    AuditObject,
    AuditObjectKind,
    ContainerAuditAdapters,
    TrustedAuditPolicy,
    WorktreeRelationship,
    run_container_audit,
)

from backend.real_host_preflight import (
    BoundAuditCallbackV1,
    CurrentTopologyPreflightReceiptV1,
    FinalAuditCallbacksV1,
    FinalAuditCompositionReadyReceiptV1,
    FinalAuditCompositionV1,
    PreMutationGateReceiptV1,
    prepare_final_audit_composition,
    prove_final_audit_composition_ready,
    real_host_preflight_operator_entry,
)
from tests.container_audit_fixtures import (
    SequenceAdapter,
    opaque,
    valid_audit_inputs,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT,
    sandbox_authorization,
    valid_profile,
)


class FinalAuditCompositionTests(unittest.TestCase):
    def test_composition_requires_validated_factory(self) -> None:
        with self.assertRaises(TypeError):
            FinalAuditCompositionV1(
                _policy=object(),
                _adapters=object(),
                policy_fingerprint=opaque_fingerprint(1),
                composition_fingerprint=opaque_fingerprint(2),
            )

    def test_readiness_composes_seven_callbacks_without_running_audit(
        self,
    ) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        authorization = sandbox_authorization(
            profile,
            phase="final_audit_readiness",
            operation_fingerprint=operation,
        )
        policy, _adapters = valid_audit_inputs()
        calls: list[str] = []

        def forbidden_reader() -> object:
            calls.append("called")
            raise AssertionError("readiness must not call an adapter")

        callbacks = FinalAuditCallbacksV1(
            filesystem=_bound(1, forbidden_reader),
            acl=_bound(2, forbidden_reader),
            volume=_bound(3, forbidden_reader),
            git=_bound(4, forbidden_reader),
            worktree=_bound(5, forbidden_reader),
            runtime=_bound(6, forbidden_reader),
            sqlite=_bound(7, forbidden_reader),
        )
        composition = prepare_final_audit_composition(
            policy=policy,
            callbacks=callbacks,
        )

        receipt = prove_final_audit_composition_ready(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation,
            observed_at_epoch=OBSERVED_AT,
            composition=composition,
        )

        self.assertIs(type(receipt), FinalAuditCompositionReadyReceiptV1)
        self.assertEqual(calls, [])
        mapping = receipt.to_mapping()
        self.assertEqual(
            mapping["details"],
            {"observation_kind": "final_audit_readiness"},
        )
        self.assertNotIn(b"container_audit_passed", receipt.to_canonical_json())

    def test_readiness_receipt_rejects_exact_class_retyping(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        policy, _adapters = valid_audit_inputs()
        callbacks = FinalAuditCallbacksV1(
            filesystem=_bound(1, lambda: None),
            acl=_bound(2, lambda: None),
            volume=_bound(3, lambda: None),
            git=_bound(4, lambda: None),
            worktree=_bound(5, lambda: None),
            runtime=_bound(6, lambda: None),
            sqlite=_bound(7, lambda: None),
        )

        for target_type in (
            CurrentTopologyPreflightReceiptV1,
            PreMutationGateReceiptV1,
        ):
            with self.subTest(target=target_type.__name__):
                receipt = prove_final_audit_composition_ready(
                    profile=profile,
                    authorization=sandbox_authorization(
                        profile,
                        phase="final_audit_readiness",
                        operation_fingerprint=operation,
                    ),
                    operation_fingerprint=operation,
                    observed_at_epoch=OBSERVED_AT,
                    composition=prepare_final_audit_composition(
                        policy=policy,
                        callbacks=callbacks,
                    ),
                )
                object.__setattr__(
                    receipt,
                    "__class__",
                    target_type,
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "^REAL_HOST_RECEIPT_INVALID$",
                ):
                    receipt.to_mapping()

    def test_real_operator_entry_is_zero_argument_and_default_locked(
        self,
    ) -> None:
        self.assertEqual(
            tuple(
                inspect.signature(
                    real_host_preflight_operator_entry
                ).parameters
            ),
            (),
        )
        result = real_host_preflight_operator_entry()
        self.assertEqual(
            result.status.value,
            "BLOCKED_NO_APPROVED_COMMAND",
        )
        self.assertEqual((result.counts.blocked, result.counts.executed), (1, 0))
        with self.assertRaises(TypeError):
            real_host_preflight_operator_entry(
                sandbox_authorization(valid_profile())
            )

    def test_bridge_runs_the_unchanged_audit_with_exact_seven_callbacks(
        self,
    ) -> None:
        policy, adapters = valid_audit_inputs()
        callbacks = FinalAuditCallbacksV1(
            filesystem=_bound(11, adapters.filesystem),
            acl=_bound(12, adapters.acl),
            volume=_bound(13, adapters.volume),
            git=_bound(14, adapters.git),
            worktree=_bound(15, adapters.worktree),
            runtime=_bound(16, adapters.runtime),
            sqlite=_bound(17, adapters.sqlite),
        )

        result = prepare_final_audit_composition(
            policy=policy,
            callbacks=callbacks,
        ).run()

        self.assertEqual(result.status.value, "container_audit_passed")
        self.assertEqual((result.counts.accepted, result.counts.rejected), (1, 0))

    def test_callback_cannot_relax_captured_clean_worktree_policy(
        self,
    ) -> None:
        control_policy, control_adapters = _dirty_worktree_inputs()
        control = run_container_audit(
            policy=control_policy,
            adapters=control_adapters,
        )
        self.assertEqual(control.status.value, "container_audit_failed")

        policy, adapters = _dirty_worktree_inputs()

        def malicious_filesystem() -> object:
            object.__setattr__(
                policy,
                "require_clean_worktrees",
                False,
            )
            return adapters.filesystem()

        callbacks = FinalAuditCallbacksV1(
            filesystem=_bound(21, malicious_filesystem),
            acl=_bound(22, adapters.acl),
            volume=_bound(23, adapters.volume),
            git=_bound(24, adapters.git),
            worktree=_bound(25, adapters.worktree),
            runtime=_bound(26, adapters.runtime),
            sqlite=_bound(27, adapters.sqlite),
        )

        result = prepare_final_audit_composition(
            policy=policy,
            callbacks=callbacks,
        ).run()

        self.assertFalse(policy.require_clean_worktrees)
        self.assertEqual(result.status.value, "container_audit_failed")

    def test_tampered_bound_callback_cannot_issue_readiness(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        policy, adapters = valid_audit_inputs()
        callback = _bound(1, adapters.filesystem)
        callbacks = FinalAuditCallbacksV1(
            filesystem=callback,
            acl=_bound(2, adapters.acl),
            volume=_bound(3, adapters.volume),
            git=_bound(4, adapters.git),
            worktree=_bound(5, adapters.worktree),
            runtime=_bound(6, adapters.runtime),
            sqlite=_bound(7, adapters.sqlite),
        )
        composition = prepare_final_audit_composition(
            policy=policy,
            callbacks=callbacks,
        )
        for replacement in (object(), lambda: object()):
            with self.subTest(callable=callable(replacement)):
                object.__setattr__(callback, "reader", replacement)
                with self.assertRaisesRegex(
                    ValueError,
                    "^FINAL_AUDIT_COMPOSITION_REJECTED$",
                ):
                    prove_final_audit_composition_ready(
                        profile=profile,
                        authorization=sandbox_authorization(
                            profile,
                            phase="final_audit_readiness",
                            operation_fingerprint=operation,
                        ),
                        operation_fingerprint=operation,
                        observed_at_epoch=OBSERVED_AT,
                        composition=composition,
                    )


def _bound(index: int, reader: object) -> BoundAuditCallbackV1:
    return BoundAuditCallbackV1.create(
        binding_fingerprint=opaque_fingerprint(600 + index),
        reader=reader,
    )


def _dirty_worktree_inputs(
) -> tuple[TrustedAuditPolicy, ContainerAuditAdapters]:
    policy, adapters = valid_audit_inputs()
    git = adapters.git.first
    volume = adapters.volume.first
    worktrees = adapters.worktree.first
    worktree = AuditObject(
        identity=opaque(950),
        kind=AuditObjectKind.DIRECTORY,
        volume_identity=policy.volume_identity,
    )
    approval = opaque(951)
    relationship = WorktreeRelationship(
        approval_id=approval,
        worktree=worktree,
        common_directory_identity=git.common_directory.identity,
        direct_child_of_worktrees=True,
        linked=True,
        branch_attached=True,
        clean=False,
        content_observed=False,
    )
    return (
        replace(policy, approved_worktrees=(approval,)),
        replace(
            adapters,
            worktree=SequenceAdapter(
                replace(worktrees, relationships=(relationship,)),
                replace(worktrees, relationships=(relationship,)),
            ),
            volume=SequenceAdapter(
                replace(
                    volume,
                    bound_identities=tuple(
                        sorted((*volume.bound_identities, worktree.identity))
                    ),
                ),
                replace(
                    volume,
                    bound_identities=tuple(
                        sorted((*volume.bound_identities, worktree.identity))
                    ),
                ),
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
