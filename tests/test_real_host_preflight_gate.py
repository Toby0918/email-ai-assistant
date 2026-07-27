"""TDD tests for the Issue #53 fresh single-use mutation gate."""

from __future__ import annotations

import copy
import unittest

from backend.real_host_preflight import (
    PreMutationGate,
    PreMutationGateReceiptV1,
    run_current_topology_preflight,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT,
    sandbox_authorization,
    topology_callbacks,
    valid_profile,
)


class PreMutationGateTests(unittest.TestCase):
    def test_gate_requires_validated_binding_and_cannot_be_reset(self) -> None:
        with self.assertRaises(TypeError):
            PreMutationGate()

        profile = valid_profile()
        operation = opaque_fingerprint(201)
        callbacks = topology_callbacks([])
        receipt = run_current_topology_preflight(
            profile=profile,
            authorization=sandbox_authorization(
                profile,
                operation_fingerprint=operation,
            ),
            operation_fingerprint=operation,
            policy_fingerprint=opaque_fingerprint(407),
            observed_at_epoch=OBSERVED_AT,
            callbacks=callbacks,
        )
        gate = PreMutationGate.bind(
            current_topology_receipt=receipt,
            callbacks=callbacks,
            policy_fingerprint=opaque_fingerprint(407),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^REAL_HOST_GATE_REJECTED$",
        ):
            gate._consumed = False

    def test_stale_prior_receipt_is_consumed_before_callbacks(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        authorization = sandbox_authorization(
            profile,
            operation_fingerprint=operation,
        )
        calls: list[str] = []
        callbacks = topology_callbacks(calls)
        topology_receipt = run_current_topology_preflight(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation,
            policy_fingerprint=opaque_fingerprint(407),
            observed_at_epoch=OBSERVED_AT,
            callbacks=callbacks,
        )
        gate = PreMutationGate.bind(
            current_topology_receipt=topology_receipt,
            callbacks=callbacks,
            policy_fingerprint=opaque_fingerprint(407),
        )
        calls_before_gate = tuple(calls)

        with self.assertRaisesRegex(
            ValueError,
            "^REAL_HOST_GATE_REJECTED$",
        ):
            gate.evaluate(
                profile=profile,
                authorization=authorization,
                operation_fingerprint=operation,
                nonce="123e4567-e89b-42d3-a456-426614174000",
                observed_at_epoch=OBSERVED_AT + 60,
            )

        self.assertEqual(tuple(calls), calls_before_gate)
        with self.assertRaisesRegex(ValueError, "^REAL_HOST_GATE_REJECTED$"):
            gate.evaluate(
                profile=profile,
                authorization=authorization,
                operation_fingerprint=operation,
                nonce="123e4567-e89b-42d3-a456-426614174000",
                observed_at_epoch=OBSERVED_AT + 1,
            )

    def test_different_uuid4_nonces_produce_different_receipts(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        policy = opaque_fingerprint(407)
        authorization = sandbox_authorization(
            profile,
            operation_fingerprint=operation,
        )
        callbacks = topology_callbacks([])
        topology_receipt = run_current_topology_preflight(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation,
            policy_fingerprint=policy,
            observed_at_epoch=OBSERVED_AT,
            callbacks=callbacks,
        )
        receipts = [
            PreMutationGate.bind(
                current_topology_receipt=topology_receipt,
                callbacks=callbacks,
                policy_fingerprint=policy,
            ).evaluate(
                profile=profile,
                authorization=authorization,
                operation_fingerprint=operation,
                nonce=nonce,
                observed_at_epoch=OBSERVED_AT + 1,
            )
            for nonce in (
                "123e4567-e89b-42d3-a456-426614174000",
                "123e4567-e89b-42d3-a456-426614174001",
            )
        ]
        self.assertNotEqual(
            receipts[0].receipt_fingerprint,
            receipts[1].receipt_fingerprint,
        )

    def test_gate_cannot_be_copied_into_replayable_state(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        authorization = sandbox_authorization(
            profile,
            operation_fingerprint=operation,
        )
        callbacks = topology_callbacks([])
        topology_receipt = run_current_topology_preflight(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation,
            policy_fingerprint=opaque_fingerprint(407),
            observed_at_epoch=OBSERVED_AT,
            callbacks=callbacks,
        )
        gate = PreMutationGate.bind(
            current_topology_receipt=topology_receipt,
            callbacks=callbacks,
            policy_fingerprint=opaque_fingerprint(407),
        )

        for copier in (copy.copy, copy.deepcopy):
            with self.subTest(copier=copier.__name__):
                with self.assertRaisesRegex(
                    ValueError,
                    "^REAL_HOST_GATE_REJECTED$",
                ):
                    copier(gate)

    def test_gate_repeats_every_check_binds_nonce_and_consumes_once(
        self,
    ) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        policy = opaque_fingerprint(407)
        authorization = sandbox_authorization(
            profile,
            operation_fingerprint=operation,
        )
        calls: list[str] = []
        callbacks = topology_callbacks(calls)
        topology_receipt = run_current_topology_preflight(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation,
            policy_fingerprint=policy,
            observed_at_epoch=OBSERVED_AT,
            callbacks=callbacks,
        )
        gate = PreMutationGate.bind(
            current_topology_receipt=topology_receipt,
            callbacks=callbacks,
            policy_fingerprint=policy,
        )

        receipt = gate.evaluate(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation,
            nonce="123e4567-e89b-42d3-a456-426614174000",
            observed_at_epoch=OBSERVED_AT + 1,
        )

        self.assertIs(type(receipt), PreMutationGateReceiptV1)
        self.assertEqual(
            calls[-7:],
            [
                "source_root",
                "target_parent",
                "finance_root",
                "target_absence",
                "git",
                "acl",
                "volume",
            ],
        )
        self.assertEqual(
            receipt.to_mapping()["details"],
            {"observation_kind": "pre_mutation_gate"},
        )
        calls_before_replay = tuple(calls)
        with self.assertRaisesRegex(
            ValueError,
            "^REAL_HOST_GATE_REJECTED$",
        ):
            gate.evaluate(
                profile=profile,
                authorization=authorization,
                operation_fingerprint=operation,
                nonce="123e4567-e89b-42d3-a456-426614174000",
                observed_at_epoch=OBSERVED_AT + 2,
            )
        self.assertEqual(tuple(calls), calls_before_replay)


if __name__ == "__main__":
    unittest.main()
