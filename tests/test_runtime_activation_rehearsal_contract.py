"""Public contract tests for the synthetic activation rehearsal."""

from __future__ import annotations

from dataclasses import MISSING, fields
import inspect
import unittest

from backend.runtime_activation_rehearsal import (
    COMPLETED_RESULT,
    FAILED_RESULT,
    ManagedActivationAdapters,
    ManagedActivationStatus,
    rehearse_managed_runtime_activation,
)


class RuntimeActivationRehearsalContractTests(unittest.TestCase):
    def test_public_seam_is_keyword_only_and_pathless(self) -> None:
        signature = inspect.signature(
            rehearse_managed_runtime_activation
        )

        self.assertEqual(tuple(signature.parameters), ("adapters",))
        self.assertEqual(
            signature.parameters["adapters"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertIs(
            signature.parameters["adapters"].default,
            inspect.Parameter.empty,
        )
        for forbidden in (
            "path",
            "root",
            "source",
            "target",
            "environment",
            "policy",
            "fail_at",
        ):
            self.assertNotIn(forbidden, signature.parameters)

    def test_adapter_bundle_has_exactly_five_required_fields(self) -> None:
        adapter_fields = fields(ManagedActivationAdapters)

        self.assertEqual(
            tuple(field.name for field in adapter_fields),
            (
                "runtime",
                "filesystem",
                "database",
                "lifecycle",
                "probe",
            ),
        )
        self.assertTrue(
            all(
                field.default is MISSING
                and field.default_factory is MISSING
                for field in adapter_fields
            )
        )

    def test_public_results_are_fixed_and_aggregate_only(self) -> None:
        self.assertEqual(
            COMPLETED_RESULT.status,
            ManagedActivationStatus.COMPLETED,
        )
        self.assertEqual(COMPLETED_RESULT.counts.completed, 1)
        self.assertEqual(COMPLETED_RESULT.counts.failed, 0)
        self.assertEqual(
            FAILED_RESULT.status,
            ManagedActivationStatus.FAILED,
        )
        self.assertEqual(FAILED_RESULT.counts.completed, 0)
        self.assertEqual(FAILED_RESULT.counts.failed, 1)
        self.assertEqual(
            tuple(field.name for field in fields(COMPLETED_RESULT)),
            ("status", "counts"),
        )
        self.assertEqual(
            tuple(field.name for field in fields(COMPLETED_RESULT.counts)),
            ("completed", "failed"),
        )
        for forbidden in (
            "path",
            "hash",
            "identity",
            "exception",
            "diagnostic",
            "version",
        ):
            self.assertNotIn(forbidden, repr(COMPLETED_RESULT).lower())
            self.assertNotIn(forbidden, repr(FAILED_RESULT).lower())

    def test_invalid_bundle_fails_without_invoking_capabilities(self) -> None:
        class HostileBundle:
            @property
            def runtime(self) -> object:
                raise AssertionError("capability was inspected")

        result = rehearse_managed_runtime_activation(
            adapters=HostileBundle(),
        )

        self.assertEqual(result, FAILED_RESULT)


if __name__ == "__main__":
    unittest.main()
