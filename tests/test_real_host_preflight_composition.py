"""TDD tests for final-audit readiness and the locked operator seam."""

from __future__ import annotations

import inspect
import unittest

from backend.real_host_preflight import (
    BoundAuditCallbackV1,
    FinalAuditCallbacksV1,
    FinalAuditCompositionReadyReceiptV1,
    FinalAuditCompositionV1,
    prepare_final_audit_composition,
    prove_final_audit_composition_ready,
    real_host_preflight_operator_entry,
)
from tests.container_audit_fixtures import valid_audit_inputs
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


if __name__ == "__main__":
    unittest.main()
