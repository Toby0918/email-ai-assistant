"""TDD tests for the Issue #53 fresh single-use mutation gate."""

from __future__ import annotations

import copy
import pickle
import threading
import unittest

from backend.cutover_contracts import ReceiptEnvelopeV1
from backend.real_host_preflight import (
    CurrentTopologyPreflightReceiptV1,
    FinalAuditCompositionReadyReceiptV1,
    PreMutationGate,
    PreMutationGateReceiptV1,
    run_current_topology_preflight,
)
from backend.real_host_preflight.receipts import (
    _mint_current_topology_receipt,
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
        with self.assertRaises(Exception):
            object.__setattr__(gate, "_consumed", False)
        forged = object.__new__(PreMutationGate)
        with self.assertRaisesRegex(
            ValueError,
            "^REAL_HOST_GATE_REJECTED$",
        ):
            forged.evaluate(
                profile=profile,
                authorization=object(),
                operation_fingerprint=operation,
                nonce="123e4567-e89b-42d3-a456-426614174000",
                observed_at_epoch=OBSERVED_AT,
            )

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
        receipts = [
            PreMutationGate.bind(
                current_topology_receipt=run_current_topology_preflight(
                    profile=profile,
                    authorization=authorization,
                    operation_fingerprint=operation,
                    policy_fingerprint=policy,
                    observed_at_epoch=OBSERVED_AT,
                    callbacks=callbacks,
                ),
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

    def test_topology_receipt_can_bind_exactly_one_gate(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        policy = opaque_fingerprint(407)
        callbacks = topology_callbacks([])
        receipt = run_current_topology_preflight(
            profile=profile,
            authorization=sandbox_authorization(
                profile,
                operation_fingerprint=operation,
            ),
            operation_fingerprint=operation,
            policy_fingerprint=policy,
            observed_at_epoch=OBSERVED_AT,
            callbacks=callbacks,
        )

        PreMutationGate.bind(
            current_topology_receipt=receipt,
            callbacks=callbacks,
            policy_fingerprint=policy,
        )
        with self.assertRaisesRegex(
            ValueError,
            "^REAL_HOST_GATE_REJECTED$",
        ):
            PreMutationGate.bind(
                current_topology_receipt=receipt,
                callbacks=callbacks,
                policy_fingerprint=policy,
            )

    def test_topology_receipt_claim_is_atomic_across_threads(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        policy = opaque_fingerprint(407)
        callbacks = topology_callbacks([])
        receipt = run_current_topology_preflight(
            profile=profile,
            authorization=sandbox_authorization(
                profile,
                operation_fingerprint=operation,
            ),
            operation_fingerprint=operation,
            policy_fingerprint=policy,
            observed_at_epoch=OBSERVED_AT,
            callbacks=callbacks,
        )
        barrier = threading.Barrier(3)
        outcomes: list[str] = []

        def bind_once() -> None:
            barrier.wait()
            try:
                PreMutationGate.bind(
                    current_topology_receipt=receipt,
                    callbacks=callbacks,
                    policy_fingerprint=policy,
                )
            except ValueError:
                outcomes.append("rejected")
            else:
                outcomes.append("accepted")

        threads = [threading.Thread(target=bind_once) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertCountEqual(outcomes, ["accepted", "rejected"])

    def test_public_envelope_cannot_mint_or_replace_nominal_receipt(
        self,
    ) -> None:
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
        envelope = ReceiptEnvelopeV1.from_mapping(receipt.to_mapping())

        wrappers = (
            CurrentTopologyPreflightReceiptV1,
            PreMutationGateReceiptV1,
            FinalAuditCompositionReadyReceiptV1,
        )
        for wrapper in wrappers:
            with self.subTest(wrapper=wrapper.__name__):
                self.assertFalse(hasattr(wrapper, "from_envelope"))
                with self.assertRaises(TypeError):
                    wrapper(envelope)
                forged = object.__new__(wrapper)
                with self.assertRaisesRegex(
                    ValueError,
                    "^REAL_HOST_RECEIPT_INVALID$",
                ):
                    forged.to_mapping()
                for copier in (copy.copy, copy.deepcopy, pickle.dumps):
                    with self.assertRaisesRegex(
                        ValueError,
                        "^REAL_HOST_RECEIPT_INVALID$",
                    ):
                        copier(forged)
        with self.assertRaises(Exception):
            object.__setattr__(receipt, "_envelope", envelope)
        for copier in (copy.copy, copy.deepcopy, pickle.dumps):
            with self.assertRaisesRegex(
                ValueError,
                "^REAL_HOST_RECEIPT_INVALID$",
            ):
                copier(receipt)

        object.__setattr__(
            envelope,
            "receipt_fingerprint",
            opaque_fingerprint(998),
        )
        with self.assertRaisesRegex(
            ValueError,
            "^REAL_HOST_RECEIPT_INVALID$",
        ):
            _mint_current_topology_receipt(envelope)

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

        for copier in (copy.copy, copy.deepcopy, pickle.dumps):
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
